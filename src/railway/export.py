import collections
import json
import math
from pathlib import Path
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components,dijkstra
from .common import save_csv,save_json,now
from .config import CITY_ORDER,ATTRIBUTION,DISTANCE_LABEL,STATION_IDENTITY_VERSION,CITY_STATION_MAX_METERS
from .graph import geometry_km,GEOD

def validate_path(graph,path,start,end,barriers=()):
    cursor=start; total=0.; visited=[start]
    for eid,a,b in path:
        e=graph.edges[eid]
        if a!=cursor or {a,b}!={e.a,e.b}: raise ValueError('Path has disconnected or incorrectly oriented edges')
        refs=e.refs if a==e.a else tuple(reversed(e.refs))
        if refs[0]!=a or refs[-1]!=b: raise ValueError('Edge OSM node geometry does not match endpoints')
        recalculated=geometry_km([graph.coords[n] for n in refs])
        if not math.isclose(recalculated,e.km,rel_tol=1e-11,abs_tol=1e-8):
            raise ValueError('Geodesic length differs from cached weight')
        visited.extend(refs[1:]); total+=e.km; cursor=b
    if cursor!=end: raise ValueError('Path ends at the wrong node')
    if set(visited[1:-1])&set(barriers): raise ValueError('City edge passes through a third selected station')
    return total

def path_feature(graph,path,props):
    nodes=[]
    for eid,a,b in path:
        e=graph.edges[eid]; refs=e.refs if a==e.a else tuple(reversed(e.refs))
        nodes.extend(refs if not nodes else refs[1:])
    return {'type':'Feature','properties':{**props,'osm_node_ids':nodes,
             'osm_way_ids':list(dict.fromkeys(graph.edges[eid].way_id for eid,_,_ in path)),
             'distance_definition':DISTANCE_LABEL,'attribution':ATTRIBUTION},
            'geometry':{'type':'LineString','coordinates':graph.path_points(path)}}

def feature_collection(features):
    return {'type':'FeatureCollection','attribution':ATTRIBUTION,'distance_definition':DISTANCE_LABEL,'features':features}

def city_graph_stats(records):
    ix={c:i for i,c in enumerate(CITY_ORDER)}; rows=[]; cols=[]; values=[]
    for r in records:
        a,b=ix[r['city_a']],ix[r['city_b']]
        rows.extend([a,b]); cols.extend([b,a]); values.extend([r['distance_km']]*2)
    mat=csr_matrix((values,(rows,cols)),shape=(34,34))
    count,labels=connected_components(mat,directed=False)
    degree=np.asarray((mat!=0).sum(axis=1)).ravel()
    components=[{'id':i,'cities':[c for j,c in enumerate(CITY_ORDER) if labels[j]==i]} for i in range(count)]
    # One requested direction only. No all-pairs distance matrix.
    route=dijkstra(mat,directed=False,indices=ix['广州'])[ix['兰州']]
    return {'node_count':34,'edge_count':len(records),'component_count':int(count),
            'components':components,'isolated_cities':[c for i,c in enumerate(CITY_ORDER) if degree[i]==0],
            'guangzhou_lanzhou_compressed_km':float(route) if math.isfinite(route) else None}

def suspicious_endpoints(graph,limit_m=100.,max_records=500):
    from pyproj import Transformer
    from scipy.spatial import cKDTree
    terminals=[n for n in graph.ids if len(graph.adj[n])==1]
    if not terminals: return []
    xy=np.array([graph.coords[n] for n in terminals])
    transformer=Transformer.from_crs('EPSG:4326','EPSG:4978',always_xy=True)
    x,y,z=transformer.transform(xy[:,0],xy[:,1],np.zeros(len(xy)))
    tree=cKDTree(np.column_stack([x,y,z])); candidates=[]
    for i,j in tree.query_pairs(limit_m):
        a,b=terminals[i],terminals[j]
        if graph.component(a)==graph.component(b): continue
        distance=float(GEOD.inv(*graph.coords[a],*graph.coords[b])[2])
        candidates.append({'node_a':a,'node_b':b,'distance_m':distance,
                           'component_a':graph.component(a),'component_b':graph.component(b),
                           'action':'diagnostic_only_not_joined'})
    return sorted(candidates,key=lambda x:x['distance_m'])[:max_records]

def write_outputs(out,graph,station_rows,city_rows,city_edges,station_names,metadata,graph_quality,station_issues,access_info):
    out=Path(out); out.mkdir(parents=True,exist_ok=True)
    save_csv(out/'cities.csv',city_rows,list(city_rows[0]))
    save_csv(out/'city_stations.csv',station_rows,list(station_rows[0]))
    rejected=[r for r in station_issues if r['issue']=='station_identity_candidate_rejected']
    save_csv(out/'station_candidate_rejections.csv',[
        {**r,'matched_aliases':';'.join(r['matched_aliases']),
         'name_tags':json.dumps(r['name_tags'],ensure_ascii=False),
         'transport_tags':json.dumps(r.get('transport_tags',{}),ensure_ascii=False),
         'excluded_mode_stop_nodes':';'.join(str(n) for n in r.get('excluded_mode_stop_nodes',[]))} for r in rejected],
        ['city','reason','osm_type','osm_id','station_name','longitude','latitude',
         'city_station_distance_m','matched_aliases','name_tags','source','transport_tags','excluded_mode_stop_nodes'])
    anchors={r['city']:int(r['track_node_id']) for r in station_rows
             if r['track_node_id']!='' and int(r['track_node_id']) in graph.index}
    all_barriers=set(anchors.values()); features=[]; table=[]; maximum_edge_error=0.
    for i,edge in enumerate(city_edges,1):
        a,b=edge['city_a'],edge['city_b']; path=edge['path']
        checked=validate_path(graph,path,anchors[a],anchors[b],all_barriers-{anchors[a],anchors[b]})
        maximum_edge_error=max(maximum_edge_error,abs(checked-edge['distance_km']))
        if not math.isclose(checked,edge['distance_km'],rel_tol=1e-10,abs_tol=1e-7):
            raise ValueError('City edge length mismatch')
        eid=f'E{i:03d}'; edge['edge_id']=eid
        lines=list(dict.fromkeys(graph.edges[e].line for e,_,_ in path))
        source=sorted({graph.edges[e].source for e,_,_ in path})
        features.append(path_feature(graph,path,{'edge_id':eid,'city_a':a,'city_b':b,'distance_km':checked,
                                                'lines':lines,'sources':source}))
        table.append({'edge_id':eid,'city_a':a,'city_b':b,'distance_km':format(checked,'.12f'),
                      'lines':' | '.join(lines),'osm_way_ids':';'.join(str(x) for x in dict.fromkeys(graph.edges[e].way_id for e,_,_ in path)),
                      'source_extracts':' | '.join(source),'path_feature_id':eid,'distance_definition':DISTANCE_LABEL,
                      'edge_definition':'shortest rail geometry without passing another selected station; not a direct train claim'})
    save_csv(out/'city_edges.csv',table,['edge_id','city_a','city_b','distance_km','lines','osm_way_ids','source_extracts',
                                      'path_feature_id','distance_definition','edge_definition'])
    save_json(out/'edge_paths.geojson',feature_collection(features))
    # Full edge-level provenance supports independent geometric recomputation.
    all_features=[]
    for e in graph.edges.values():
        all_features.append({'type':'Feature','properties':{'graph_edge_id':e.id,'osm_way_id':e.way_id,'osm_version':e.version,
                         'source_extract':e.source,'osm_node_ids':list(e.refs),'length_km':e.km,'line':e.line,
                         'usage':e.tags.get('usage','unknown'),'service':e.tags.get('service',''),
                         'access':e.tags.get('access','unknown'),'kind':e.kind,'tags':e.tags},
                             'geometry':{'type':'LineString','coordinates':[graph.coords[n] for n in e.refs]}})
    save_json(out/'railway_tracks.geojson',feature_collection(all_features))
    station_features=[]
    for r in station_rows:
        if r['station_longitude']!='':
            station_features.append({'type':'Feature','properties':r,
                  'geometry':{'type':'Point','coordinates':[r['station_longitude'],r['station_latitude']]}})
    save_json(out/'representative_stations.geojson',feature_collection(station_features))
    stats=city_graph_stats(city_edges); counts=collections.Counter(graph.labels.tolist())
    route={'status':'unreachable','computed_at':now(),'start_city':'广州','end_city':'兰州',
           'start_station':next(r for r in station_rows if r['city']=='广州'),
           'end_station':next(r for r in station_rows if r['city']=='兰州'),
           'distance_definition':DISTANCE_LABEL,'attribution':ATTRIBUTION}
    path=[]; route_segments=[]
    if '广州' not in anchors or '兰州' not in anchors:
        route['reason']='A representative station lacks a reliable active railway graph anchor'
    else:
        start,end=anchors['广州'],anchors['兰州']; km,path=graph.shortest(start,end)
        route.update(start_component=graph.component(start),end_component=graph.component(end))
        if math.isfinite(km):
            actual=validate_path(graph,path,start,end)
            lower_bound=geometry_km([graph.coords[start],graph.coords[end]])
            if km+1e-6<lower_bound:
                raise ValueError('Railway path is shorter than the WGS84 endpoint geodesic lower bound')
            if not math.isclose(km,actual,rel_tol=1e-10,abs_tol=1e-7): raise ValueError('Route length mismatch')
            compressed=stats['guangzhou_lanzhou_compressed_km']
            if compressed is None or not math.isclose(km,compressed,rel_tol=1e-9,abs_tol=1e-6):
                raise ValueError('City graph and base railway shortest distances differ; investigate compression')
            path_nodes=[start]+[b for _,_,b in path]; inverse={n:c for c,n in anchors.items()}
            city_sequence=[inverse[n] for n in path_nodes if n in inverse]
            recognized=[{'osm_node_id':n,'station_name':station_names[n]} for n in path_nodes if n in station_names]
            route.update(status='reachable',total_km=km,selected_city_sequence=city_sequence,
                         recognized_stations=recognized,route_line_names=list(dict.fromkeys(graph.edges[e].line for e,_,_ in path)),
                         length_recomputed_km=actual,compressed_km=compressed,
                         endpoint_geodesic_lower_bound_km=lower_bound,
                         detour_ratio=km/lower_bound if lower_bound>0 else None,
                         station_spatial_matches_pending_review=[r['city'] for r in station_rows if r['city'] in city_sequence and r['match_status']=='spatial_match_needs_review'])
            route_segments=segment_route(graph,path,station_names)
            if not math.isclose(sum(r['distance_km'] for r in route_segments),km,rel_tol=1e-10,abs_tol=1e-7):
                raise ValueError('Route segments do not sum to route total')
            save_json(out/'guangzhou_lanzhou_path.geojson',feature_collection([path_feature(graph,path,route)]))
            save_csv(out/'guangzhou_lanzhou_segments.csv',route_segments,list(route_segments[0]))
        else:
            route['reason']='Selected station anchors lie in different OSM railway connected components; no artificial joins or ferry edges'
    if route['status']!='reachable':
        # Remove only stale route outputs from a previous successful run, never invent an empty route.
        for name in ['guangzhou_lanzhou_path.geojson','guangzhou_lanzhou_segments.csv']:
            p=out/name
            if p.exists(): p.unlink()
    save_json(out/'guangzhou_lanzhou_status.json',route)
    overlaps=[]
    files=list(metadata['files'].items())
    for i,(a,info_a) in enumerate(files):
        for b,info_b in files[i+1:]:
            x,y=info_a['actual_node_bounds'],info_b['actual_node_bounds']
            box=[max(x[0],y[0]),max(x[1],y[1]),min(x[2],y[2]),min(x[3],y[3])]
            overlaps.append({'file_a':a,'file_b':b,'bbox_overlap':box if box[0]<=box[2] and box[1]<=box[3] else None,
                             'note':'Bounding-box overlap is not proof of complete coverage; retained shared IDs are deduplicated'})
    quality={'run_status':'real_osm_processing_completed','generated_at':now(),'distance_definition':DISTANCE_LABEL,
             'city_order_verified':[r['city'] for r in city_rows]==CITY_ORDER,
             'city_graph':stats,'rail_graph':{'junction_node_count':len(graph.ids),'edge_count':len(graph.edges),
                         'component_count':int(graph.component_count),'largest_components':counts.most_common(20)},
             'mapped_stations':len(anchors),'topology_matched_stations':sum(r['match_status']=='topology_matched' for r in station_rows),
             'station_identity_policy':{'version':STATION_IDENTITY_VERSION,
                 'chinese_alias_priority':True,'english_conflicting_chinese_names_rejected':True,
                 'explicit_non_heavy_station_modes_rejected':True,'stop_area_member_modes_checked':True,
                 'max_city_station_m':CITY_STATION_MAX_METERS,'rejected_candidate_count':len(rejected),
                 'note':'Name and city proximity gates do not establish manual verification or passenger usability'},
             'spatial_matches_pending_review':[r['city'] for r in station_rows if r['match_status']=='spatial_match_needs_review'],
             'unmapped_stations':[r['city'] for r in station_rows if r['city'] not in anchors],
             'layout_coordinates_missing':[r['city'] for r in city_rows if r['longitude']==''],
             'data_extraction':metadata,'extract_bbox_overlaps':overlaps,
             'graph_filtering':graph_quality,'station_issues':station_issues,'auxiliary_station_access':access_info,
             'nearby_disconnected_endpoints_diagnostic_only':suspicious_endpoints(graph),
             'max_city_edge_length_error_km':maximum_edge_error,
             'unusually_short_city_edges_under_1km':[{'city_a':e['city_a'],'city_b':e['city_b'],'distance_km':e['distance_km']}
                                                    for e in city_edges if e['distance_km']<1],
             'all_city_paths_continuous_and_recomputed':True,'guangzhou_lanzhou':route,
             'limitations':['OSM coverage and railway tags may be incomplete; no global connectivity repair',
               'Unknown usage and access are retained with unknown labels; passenger use is not confirmed',
               'Undirected infrastructure graph ignores operating direction, schedules and restrictions',
               'Station spatial matching needs visual review; station building-to-track gap is not added to railway mileage',
               'Disconnected branches and railway ferries are not bridged',
               'Geometric track length is not official passenger mileage, tariff mileage or a verified train journey'],
             'attribution':ATTRIBUTION}
    save_json(out/'data_quality.json',quality)
    return quality,path

def segment_route(graph,path,station_names):
    """Split at named railway stops and line changes; unnamed lines split by OSM way."""
    groups=[]; group=[]; previous_key=None
    for item in path:
        eid,a,b=item; e=graph.edges[eid]
        key=e.line if e.line!='未标注线路名' else ('unnamed_way',e.way_id)
        if group and (key!=previous_key or a in station_names):
            groups.append(group); group=[]
        group.append(item); previous_key=key
    if group: groups.append(group)
    rows=[]; cumulative=0.
    for i,part in enumerate(groups,1):
        a,b=part[0][1],part[-1][2]; km=sum(graph.edges[e].km for e,_,_ in part); cumulative+=km
        rows.append({'segment_id':i,'start_track_node':a,'end_track_node':b,
                     'start_station':station_names.get(a,''),'end_station':station_names.get(b,''),
                     'line':graph.edges[part[0][0]].line,'distance_km':km,'cumulative_km':cumulative,
                     'osm_way_ids':';'.join(str(n) for n in dict.fromkeys(graph.edges[e].way_id for e,_,_ in part)),
                     'graph_edge_ids':';'.join(str(e) for e,_,_ in part),
                     'split_rule':'named_stop_or_line_change; unnamed_line_split_by_OSM_way',
                     'distance_definition':DISTANCE_LABEL})
    return rows
