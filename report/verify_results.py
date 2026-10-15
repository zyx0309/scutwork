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
    mode_wrong=False; diagnostic=None
    if (folder/'station_diagnostics.json').is_file():
        diagnostic=json.loads((folder/'station_diagnostics.json').read_text(encoding='utf-8-sig'))
        if diagnostic['source_quality_generated_at']!=q['generated_at'] or diagnostic['source_run_status']!=state:
            raise ValueError('Mixed diagnostic/results snapshots')
        fuzhou=diagnostic['evidence']['福州']
        anchor=fuzhou.get('selected_track_node')
        mode_wrong=bool(anchor and anchor['data']['tags'].get('subway')=='yes' and
                        str(anchor['osm_id'])==matches[0]['track_node_id'])
    result={'input_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()},
      'city_count':len(stations),'city_order_matches':True,'edge_count':len(edges),'invalid_edges':[],
      'duplicate_city_edges':[],'independently_recomputed_components':components,'component_count':len(components),
      'degree':{c:len(graph[c]) for c in CITY_ORDER},
      'largest_city_component_size':max(map(len,components)),
      'largest_city_component_is_complete':all(len(graph[c])==len(components[0])-1 for c in components[0]),
      'mainland_component_is_complete_K27':len(components[0])==27 and all(len(graph[c])==26 for c in components[0]),
      'independent_city_graph_dijkstra_km':distance,'city_graph_dijkstra_city_sequence':path,
      'reported_base_graph_km':route['total_km'],'difference_from_reported_base_km':distance-route['total_km'],
      'algorithmically_mapped_stations':sum(r['component_id']!='' for r in stations),
      'station_status_counts':dict(Counter(r['match_status'] for r in stations)),
      'route_segment_count':len(segments),'segments_sum_km':total,'segment_sum_difference_km':total-route['total_km'],
      'adjacent_segment_track_nodes_continuous':continuity,'segment_endpoint_matches_route_anchors':endpoints,
      'cumulative_distance_consistent':cumulative,'confirmed_fuzhou_fuzhou_name_collision':wrong,
      'confirmed_fuzhou_wrong_transport_mode':mode_wrong,
      'source_completed_at':state['completed_at'],
      'source_graph_version':state.get('graph_version'),'source_station_identity_version':state.get('station_identity_version'),
      'candidate_mappings_after_rejecting_known_error':sum(r['component_id']!='' for r in stations)-int(wrong or mode_wrong),
      'raw_geodesic_recomputation_performed_here':False,
      'scope':'City/segment tables and optional raw station diagnostics; complete track geometries and PBF have not been independently re-read here.'}
    # New exports retain the exact mode tags, including for stations without anchors.
    if state.get('station_identity_version',0)>=3:
        from pyproj import Geod
        from railway.extract import excluded_transport_mode
        geod=Geod(ellps='WGS84'); offsets={}; bad_modes=[]; incident={}
        for row in stations:
            if not row['track_node_id']: continue
            station_tags=json.loads(row['station_raw_tags']);track_tags=json.loads(row['track_node_raw_tags'])
            if excluded_transport_mode(station_tags) or excluded_transport_mode(track_tags):
                bad_modes.append(row['city'])
            _,_,offset=geod.inv(float(row['station_longitude']),float(row['station_latitude']),
                               float(row['track_longitude']),float(row['track_latitude']))
            if abs(offset-float(row['match_distance_m']))>0.000501:
                raise ValueError('Station offset does not match coordinates: '+row['city'])
            offsets[row['city']]=offset
        if bad_modes: raise ValueError('Explicit excluded transport mode on selected anchors: '+str(bad_modes))
        if diagnostic:
            if diagnostic['extraction_fingerprint']!=q['data_extraction']['fingerprint']:
                raise ValueError('Diagnostic extraction fingerprint differs')
            by_city={r['city']:r for r in stations}
            for city,evidence in diagnostic['evidence'].items():
                if evidence['selected_station_csv']!=by_city[city]:
                    raise ValueError('Diagnostic station row differs: '+city)
                anchor=by_city[city]['track_node_id']; ways=[]
                xy={n['osm_id']:(n['lon'],n['lat']) for n in evidence['track_node_coordinates']}
                for way in evidence['incident_rail_ways']:
                    refs=way['data']['refs']
                    if not anchor or int(anchor) not in refs: continue
                    if not all(n in xy for n in refs): raise ValueError('Missing diagnostic way coordinates')
                    length=math.fsum(geod.inv(*xy[a],*xy[b])[2] for a,b in zip(refs,refs[1:]))/1000
                    ways.append({'osm_way_id':way['osm_id'],'tags':way['data']['tags'],
                                 'full_polyline_length_recomputed_km':length})
                incident[city]=ways
        result.update({'selected_station_or_track_explicit_excluded_modes':bad_modes,
                       'independently_recomputed_station_offsets_m':offsets,
                       'selected_anchor_incident_way_checks':incident,
                       'diagnostic_polylines_recomputed_here':bool(diagnostic),
                       'raw_geodesic_recomputation_performed_here':bool(diagnostic),
                       'full_route_or_national_track_geodesic_recomputation_performed_here':False,
                       'scope':'City/segment tables, 30 station offsets, selected raw mode tags and local diagnostic way geometry. No national PBF or full city/route track geometry reread.'})
    if wrong:
        f=matches[0]
        result['confirmed_mapping_error']={'city':'福州','actual_matched_name':f['station_name'],'osm_id':f['osm_id'],
          'osm_type':f['osm_type'],'longitude':f['station_longitude'],'latitude':f['station_latitude'],'source':f['source'],
          'distance_from_OSM_city_place_m':next(x['distance_m'] for x in q['station_issues'] if x['city']=='福州')}
        result['rejected_fuzhou_mapping_has_city_degree_zero']=len(graph['福州'])==0
        assert len(graph['福州'])==0
    if mode_wrong:
        f=matches[0];anchor=diagnostic['evidence']['福州']['selected_track_node']
        result['confirmed_mapping_error']={'issue':'excluded_transport_mode_stop_used_as_heavy_rail_representative',
            'city':'福州','matched_station_object_type':f['osm_type'],'matched_station_object_id':f['osm_id'],
            'track_node_id':anchor['osm_id'],'actual_track_node_tags':anchor['data']['tags']}
        result['rejected_fuzhou_mapping_has_city_degree_zero']=len(graph['福州'])==0
        assert len(graph['福州'])==0
    return result

if __name__=='__main__':
    folder=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/'input'
    audit=verify(folder)
    (folder.resolve().parent/'independent_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Result-table audit completed; confirmed mapping errors are retained in the audit, not overwritten.')
