"""Topology follows OSM IDs. Shape points are retained in every edge geometry."""
import collections
import heapq
import math
from dataclasses import dataclass
import numpy as np
from pyproj import Geod
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components, dijkstra
from .extract import classify

GEOD=Geod(ellps='WGS84')

def geometry_km(points):
    if len(points)<2: return 0.0
    a=np.asarray(points,dtype=float)
    _,_,meters=GEOD.inv(a[:-1,0],a[:-1,1],a[1:,0],a[1:,1])
    return float(np.sum(meters)/1000.0)

@dataclass
class Edge:
    id: int
    a: int
    b: int
    refs: tuple
    km: float
    way_id: int
    version: int
    tags: dict
    source: str
    kind: str

    @property
    def line(self):
        return self.tags.get('name:zh') or self.tags.get('name') or self.tags.get('railway:ref') or self.tags.get('ref') or '未标注线路名'

class RailGraph:
    def __init__(self,edges,coords):
        self.edges={e.id:e for e in edges}; self.coords=coords
        self.ids=sorted({n for e in edges for n in (e.a,e.b)})
        self.index={n:i for i,n in enumerate(self.ids)}
        self.adj=collections.defaultdict(list); best={}
        for e in edges:
            self.adj[e.a].append((e.b,e.km,e.id)); self.adj[e.b].append((e.a,e.km,e.id))
            if e.a==e.b: continue  # Geometry retained; positive self-loop cannot improve a path.
            for a,b in [(e.a,e.b),(e.b,e.a)]:
                key=(self.index[a],self.index[b])
                if key not in best or e.km<best[key][0]: best[key]=(e.km,e.id)
        self.best_edge={key:value[1] for key,value in best.items()}
        if best:
            row,col=zip(*best)
            self.matrix=csr_matrix(([v[0] for v in best.values()],(row,col)),shape=(len(self.ids),len(self.ids)))
        else:
            self.matrix=csr_matrix((0,0))
        self.component_count,self.labels=connected_components(self.matrix,directed=False)

    def shortest(self,a,b):
        if a not in self.index or b not in self.index: return math.inf,[]
        dist,parent=dijkstra(self.matrix,directed=False,indices=self.index[a],return_predecessors=True)
        target=self.index[b]
        if not math.isfinite(dist[target]): return math.inf,[]
        sequence=[]; current=target
        while current!=self.index[a]:
            previous=int(parent[current])
            if previous<0: raise RuntimeError('Broken scipy predecessor chain')
            sequence.append((self.best_edge[(previous,current)],self.ids[previous],self.ids[current]))
            current=previous
        return float(dist[target]),list(reversed(sequence))

    def component(self,n):
        return int(self.labels[self.index[n]]) if n in self.index else None

    def path_points(self,path):
        result=[]
        for eid,a,b in path:
            e=self.edges[eid]
            refs=e.refs if a==e.a else tuple(reversed(e.refs))
            points=[self.coords[n] for n in refs]
            if result and result[-1]!=points[0]: raise ValueError('Non-continuous path geometry')
            result.extend(points if not result else points[1:])
        return result

def build_edges(ways,coords,split_nodes):
    counts=collections.Counter()
    included=[]; filter_counts=collections.Counter(); missing=[]
    for ident,version,source,data in ways:
        kind,reason=classify(data['tags']); filter_counts[f'{kind}:{reason}']+=1
        if kind=='exclude': continue
        refs=data['refs']
        absent=[n for n in refs if n not in coords]
        if absent:
            missing.append({'way_id':ident,'missing_nodes':absent[:20],'count':len(absent)})
            continue  # Never bridge missing shape points with a straight line.
        counts.update(refs); included.append((ident,version,source,data,kind))
    junctions={n for n,c in counts.items() if c>1}|set(split_nodes)
    edges=[]; zero=[]
    for ident,version,source,data,kind in included:
        refs=data['refs']
        if len(refs)<2: continue
        start=0
        for end in range(1,len(refs)):
            if refs[end] in junctions or end==len(refs)-1:
                part=tuple(refs[start:end+1]); km=geometry_km([coords[n] for n in part])
                if km<=0:
                    zero.append({'way_id':ident,'start_node':part[0],'end_node':part[-1]})
                else:
                    edges.append(Edge(len(edges),part[0],part[-1],part,km,ident,version,data['tags'],source,kind))
                start=end
    return edges,{'filter_counts':dict(filter_counts),'missing_geometry_ways':missing,'zero_length_runs':zero}

def select_station_access(edges,coords,station_nodes):
    """Retain only necessary auxiliary access paths, never station-yard shortcuts."""
    main=[e for e in edges if e.kind=='main']; auxiliary=[e for e in edges if e.kind=='access_only']
    main_nodes={n for e in main for n in (e.a,e.b)}
    adj=collections.defaultdict(list)
    for e in auxiliary:
        adj[e.a].append((e.b,e.km,e.id)); adj[e.b].append((e.a,e.km,e.id))
    keep=set(); diagnostics=[]
    for start in sorted(set(station_nodes)):
        if start in main_nodes: continue
        heap=[(0.,start)]; dist={start:0.}; parent={}; end=None
        while heap:
            cost,u=heapq.heappop(heap)
            if cost!=dist[u]: continue
            if u in main_nodes: end=u; break
            for v,w,eid in adj[u]:
                if cost+w<dist.get(v,math.inf):
                    dist[v]=cost+w; parent[v]=(u,eid); heapq.heappush(heap,(cost+w,v))
        if end is None:
            diagnostics.append({'track_node':start,'status':'no_mainline_access'}); continue
        cursor=end; used=[]
        while cursor!=start:
            previous,eid=parent[cursor]; keep.add(eid); used.append(eid); cursor=previous
        diagnostics.append({'track_node':start,'status':'auxiliary_access_retained','length_km':dist[end],
                            'edge_ids':list(reversed(used)),'mainline_node':end})
    selected=main+[e for e in auxiliary if e.id in keep]
    return RailGraph(selected,coords),diagnostics

def compress_cities(graph,anchors):
    """Search stops at every other representative anchor; these are barriers.

    No 34x34 all-pairs matrix is constructed or returned.
    """
    if len(set(anchors.values()))!=len(anchors):
        raise ValueError('Two selected stations share one anchor; investigate before merging cities')
    inverse={node:city for city,node in anchors.items()}; records={}
    for source,start in anchors.items():
        print(f'城市边搜索：{source}（不穿过其他代表站）',flush=True)
        heap=[(0.,start)]; dist={start:0.}; parent={}; settled=set()
        while heap:
            cost,u=heapq.heappop(heap)
            if u in settled: continue
            settled.add(u)
            if u!=start and u in inverse:
                target=inverse[u]; key=tuple(sorted((source,target)))
                if key not in records:
                    path=[]; cursor=u
                    while cursor!=start:
                        previous,eid=parent[cursor]; path.append((eid,previous,cursor)); cursor=previous
                    records[key]={'city_a':source,'city_b':target,'distance_km':cost,'path':list(reversed(path))}
                continue
            for v,w,eid in graph.adj[u]:
                if cost+w<dist.get(v,math.inf):
                    dist[v]=cost+w; parent[v]=(u,eid); heapq.heappush(heap,(cost+w,v))
    return list(records.values())
