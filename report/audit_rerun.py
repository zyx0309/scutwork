"""Audit three post-fix uploads without mixing old edges/segments into the new run."""
import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'src'))
from railway.config import CITY_ORDER
from railway.stations import distance_m

def rows(path):
    with path.open(encoding='utf-8-sig',newline='') as stream: return list(csv.DictReader(stream))

def main():
    folder=ROOT/'rerun_20261015'; inputs=folder/'input'
    stations=rows(inputs/'city_stations.csv'); rejected=rows(inputs/'station_candidate_rejections.csv')
    quality=json.loads((inputs/'data_quality.json').read_text(encoding='utf-8-sig'))
    previous=rows(ROOT/'input/city_stations.csv')
    old_quality=json.loads((ROOT/'input/data_quality.json').read_text(encoding='utf-8-sig'))
    if [r['city'] for r in stations]!=CITY_ORDER: raise ValueError('City order differs')
    if quality['station_identity_policy']['version']!=2: raise ValueError('Not post-fix policy')
    indexed={r['city']:r for r in stations}
    anchored=[r for r in stations if r['component_id']!='']
    assert len(anchored)==quality['mapped_stations']
    assert [r['city'] for r in stations if r['match_status']=='spatial_match_needs_review']==quality['spatial_matches_pending_review']
    max_gap_error=0.0
    for r in anchored:
        gap=distance_m((float(r['station_longitude']),float(r['station_latitude'])),
                       (float(r['track_longitude']),float(r['track_latitude'])))
        max_gap_error=max(max_gap_error,abs(gap-float(r['match_distance_m'])))
        assert abs(gap-float(r['match_distance_m']))<=0.000501
        assert float(r['city_station_distance_m'])<=80000
    issues=[r for r in quality['station_issues'] if r['issue']=='station_identity_candidate_rejected']
    assert len(rejected)==len(issues)==quality['station_identity_policy']['rejected_candidate_count']
    keyed={(r['city'],r['osm_type'],str(r['osm_id'])):r for r in issues}
    assert len(keyed)==len(rejected)
    for r in rejected:
        issue=keyed[(r['city'],r['osm_type'],r['osm_id'])]
        assert r['reason']==issue['reason'] and r['station_name']==issue['station_name']
        assert json.loads(r['name_tags'])==issue['name_tags']
        assert r['matched_aliases']==';'.join(issue['matched_aliases'])
    for key,city in [('start_station','广州'),('end_station','兰州')]:
        station=quality['guangzhou_lanzhou'][key]; row=indexed[city]
        assert int(row['track_node_id'])==station['track_node_id']
        assert row['station_name']==station['station_name']
        assert row['osm_type']==station['osm_type'] and int(row['osm_id'])==station['osm_id']
    changed=[]
    for old,new in zip(previous,stations):
        fields=['station_name','osm_type','osm_id','track_node_id','component_id']
        difference={k:{'before':old[k],'after':new[k]} for k in fields if old[k]!=new[k]}
        if difference: changed.append({'city':new['city'],'changes':difference})
    fuzhou=indexed['福州']; fuzhou_component=int(fuzhou['component_id'])
    result={
        'scope':'Independent checks of three post-fix uploads; new city-edge CSV, segment CSV, full track geometry and raw PBF not received.',
        'input_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs.iterdir() if p.is_file()},
        'quality_generated_at_utc':quality['generated_at'],'city_order_matches':True,
        'table_anchor_count':len(anchored),'status_counts':dict(Counter(r['match_status'] for r in stations)),
        'rejection_count_independently_matched_to_quality':len(rejected),
        'rejection_reasons':dict(Counter(r['reason'] for r in rejected)),
        'station_track_geodesic_gap_max_rounding_error_m':max_gap_error,
        'all_selected_station_city_distance_values_under_80km':True,
        'city_distance_recomputed_here':False,
        'changed_selected_identities_and_anchors':changed,
        'fuzhou_current_candidate':fuzhou,'previous_fuzhou_fuzhou_misidentification_removed':fuzhou['station_name']!='浮洲' and fuzhou['osm_id']!='10658521',
        'fuzhou_heavy_rail_station_identity_fully_verified':False,
        'fuzhou_incident_component_gap_diagnostics':[r for r in quality['nearby_disconnected_endpoints_diagnostic_only'] if fuzhou_component in (r['component_a'],r['component_b'])],
        'reported_city_graph':quality['city_graph'],'reported_rail_graph':quality['rail_graph'],
        'new_edge_table_received_and_recomputed':False,'new_segment_table_received_and_recomputed':False,
        'reported_route_status':quality['guangzhou_lanzhou']['status'],
        'reported_route_total_km':quality['guangzhou_lanzhou'].get('total_km'),
        'reported_route_total_unchanged':quality['guangzhou_lanzhou'].get('total_km')==old_quality['guangzhou_lanzhou'].get('total_km'),
        'source_extraction_fingerprint_unchanged':quality['data_extraction']['fingerprint']==old_quality['data_extraction']['fingerprint'],
        'priority_spatial_reviews_over_100m':[{'city':r['city'],'distance_m':float(r['match_distance_m'])} for r in stations
             if r['match_status']=='spatial_match_needs_review' and float(r['match_distance_m'])>100],
        'raw_geometry_recomputed_here':False,
    }
    (folder/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Post-fix upload audit passed. Cross-strait identity error removed; local rail mode/topology remain unverified.')

if __name__=='__main__': main()
