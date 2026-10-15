"""Recompute result-table invariants without claiming raw-PBF geometry validation."""
import csv
import hashlib
import heapq
import json
import math
from collections import Counter,deque
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'src'))
from railway.config import CITY_ORDER

def csv_rows(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as f:
        return list(csv.DictReader(f))

def dijkstra_city(graph,source,target):
    dist={source:0.0}; parent={}; queue=[(0.0,source)]
    while queue:
        cost,u=heapq.heappop(queue)
        if cost!=dist[u]: continue
        if u==target: break
        for v,w in graph[u].items():
            if cost+w<dist.get(v,math.inf):
                dist[v]=cost+w; parent[v]=u
                heapq.heappush(queue,(cost+w,v))
    if target not in dist: return math.inf,[]
    path=[target]
    while path[-1]!=source: path.append(parent[path[-1]])
    return dist[target],list(reversed(path))

def verify(folder=ROOT/'input'):
    folder=Path(folder)
    q=json.loads((folder/'data_quality.json').read_text(encoding='utf-8-sig'))
    route=json.loads((folder/'guangzhou_lanzhou_status.json').read_text(encoding='utf-8-sig'))
    state=json.loads((folder/'run_status.json').read_text(encoding='utf-8-sig'))
    stations=csv_rows(folder/'city_stations.csv'); cities=csv_rows(folder/'cities.csv')
    edges=csv_rows(folder/'city_edges.csv'); segments=csv_rows(folder/'guangzhou_lanzhou_segments.csv')
    if state['status']!='completed_real_osm': raise ValueError('Input is not a completed national OSM run')
    if route!=q['guangzhou_lanzhou']: raise ValueError('Mixed route/quality versions')
    if [r['city'] for r in stations]!=CITY_ORDER or [r['city'] for r in cities]!=CITY_ORDER:
        raise ValueError('34-city order differs')
    graph={c:{} for c in CITY_ORDER}
    for e in edges:
        a,b=e['city_a'],e['city_b']; w=float(e['distance_km'])
        if a==b or a not in graph or b not in graph or not math.isfinite(w) or w<=0 or b in graph[a]:
            raise ValueError('Invalid or duplicate city edge')
        graph[a][b]=w; graph[b][a]=w
    components=[]; remaining=set(graph)
    while remaining:
        start=next(c for c in CITY_ORDER if c in remaining); visited={start}; queue=deque([start])
        while queue:
            for v in graph[queue.popleft()]:
                if v not in visited: visited.add(v); queue.append(v)
        remaining-=visited; components.append([c for c in CITY_ORDER if c in visited])
    distance,path=dijkstra_city(graph,'广州','兰州')
    total=math.fsum(float(r['distance_km']) for r in segments)
    continuity=all(a['end_track_node']==b['start_track_node'] for a,b in zip(segments,segments[1:]))
    endpoints=int(segments[0]['start_track_node'])==route['start_station']['track_node_id'] and int(segments[-1]['end_track_node'])==route['end_station']['track_node_id']
    cumulative=all(math.isclose(math.fsum(float(x['distance_km']) for x in segments[:i+1]),float(r['cumulative_km']),abs_tol=1e-8) for i,r in enumerate(segments))
    assert continuity and endpoints and cumulative
    assert math.isclose(distance,route['total_km'],abs_tol=1e-7)
    assert math.isclose(total,route['total_km'],abs_tol=1e-7)
    assert len(edges)==q['city_graph']['edge_count'] and len(components)==q['city_graph']['component_count']
    matches=[r for r in stations if r['city']=='福州']
    wrong=bool(matches and matches[0]['station_name']=='浮洲')
    result={'input_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()},
      'city_count':len(stations),'city_order_matches':True,'edge_count':len(edges),'invalid_edges':[],
      'duplicate_city_edges':[],'independently_recomputed_components':components,'component_count':len(components),
      'degree':{c:len(graph[c]) for c in CITY_ORDER},
      'mainland_component_is_complete_K27':len(components[0])==27 and all(len(graph[c])==26 for c in components[0]),
      'independent_city_graph_dijkstra_km':distance,'city_graph_dijkstra_city_sequence':path,
      'reported_base_graph_km':route['total_km'],'difference_from_reported_base_km':distance-route['total_km'],
      'algorithmically_mapped_stations':sum(r['component_id']!='' for r in stations),
      'station_status_counts':dict(Counter(r['match_status'] for r in stations)),
      'route_segment_count':len(segments),'segments_sum_km':total,'segment_sum_difference_km':total-route['total_km'],
      'adjacent_segment_track_nodes_continuous':continuity,'segment_endpoint_matches_route_anchors':endpoints,
      'cumulative_distance_consistent':cumulative,'confirmed_fuzhou_fuzhou_name_collision':wrong,
      'candidate_mappings_after_rejecting_known_error':sum(r['component_id']!='' for r in stations)-int(wrong),
      'raw_geodesic_recomputation_performed_here':False,
      'scope':'City graph and segment-table checks only; original track geometries and PBF have not been independently re-read here.'}
    if wrong:
        f=matches[0]
        result['confirmed_mapping_error']={'city':'福州','actual_matched_name':f['station_name'],'osm_id':f['osm_id'],
          'osm_type':f['osm_type'],'longitude':f['station_longitude'],'latitude':f['station_latitude'],'source':f['source'],
          'distance_from_OSM_city_place_m':next(x['distance_m'] for x in q['station_issues'] if x['city']=='福州')}
        result['rejected_fuzhou_mapping_has_city_degree_zero']=len(graph['福州'])==0
        assert len(graph['福州'])==0
    return result

if __name__=='__main__':
    audit=verify(Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'input')
    (ROOT/'independent_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Result-table audit completed; confirmed mapping errors are retained in the audit, not overwritten.')
