"""Representatives are explicit stations, not merged city-centre points."""
import collections
import json
import math
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
from .config import CITY_SPECS, CITY_ENGLISH, SNAP_METERS, CITY_STATION_MAX_METERS
from .extract import normalized, tag_names, classify,excluded_transport_mode
from .graph import GEOD

TO_ECEF=Transformer.from_crs('EPSG:4326','EPSG:4978',always_xy=True)

def distance_m(a,b):
    return float(GEOD.inv(a[0],a[1],b[0],b[1])[2])

def station_aliases(tags):
    aliases=tag_names(tags)
    for s in list(aliases):
        for suffix in ['铁路车站','火车站','铁路站','车站','站','railwaystation','trainstation','station']:
            if s.endswith(suffix): aliases.add(s[:-len(suffix)])
    return aliases

def has_han(text):
    return any('\u3400' <= ch <= '\u9fff' or '\U00020000' <= ch <= '\U000323af' for ch in text)

def name_evidence(tags,expected):
    """Chinese name evidence precedes romanization; conflicting Chinese names veto it."""
    names=station_aliases(tags); matched=names & expected
    if any(has_han(name) for name in matched): return 2,sorted(matched),''
    if not matched: return 0,[],''
    if any(has_han(name) for name in names):
        return 0,sorted(matched),'english_alias_conflicts_with_chinese_name'
    return 1,sorted(matched),''

def station_type(tags):
    return not excluded_transport_mode(tags) and tags.get('train')!='no'

def map_stations(nodes,ways,relations):
    coords={ident:(data['lon'],data['lat']) for ident,_,_,data in nodes}
    node_tags={ident:data['tags'] for ident,_,_,data in nodes}
    main_refs=set(); access_refs=set()
    for _,_,_,data in ways:
        kind,_=classify(data['tags'])
        if kind=='main': main_refs.update(n for n in data['refs'] if n in coords)
        if kind=='access_only': access_refs.update(n for n in data['refs'] if n in coords)
    all_refs=main_refs|access_refs
    track_ids=np.array(sorted(all_refs),dtype=np.int64)
    track_xyz=None; tree=None
    if len(track_ids):
        xy=np.array([coords[int(n)] for n in track_ids])
        x,y,z=TO_ECEF.transform(xy[:,0],xy[:,1],np.zeros(len(xy)))
        track_xyz=np.column_stack([x,y,z]); tree=cKDTree(track_xyz)
    candidates={}
    for ident,version,source,data in nodes:
        tags=data['tags']
        if tags.get('railway') in {'station','halt'}:
            candidates[('n',ident)]={'osm_type':'node','osm_id':ident,'version':version,'source':source,
                                    'coord':coords[ident],'tags':tags,'geometry_method':'OSM_node'}
    for ident,version,source,data in ways:
        tags=data['tags']
        if tags.get('railway') in {'station','halt'}:
            points=[coords[n] for n in data['refs'] if n in coords]
            if points:
                coord=tuple(np.mean(points,axis=0))
                candidates[('w',ident)]={'osm_type':'way','osm_id':ident,'version':version,'source':source,
                                        'coord':coord,'tags':tags,'geometry_method':'station_way_vertex_centroid'}
    association=collections.defaultdict(set)
    station_names_on_track={}
    for ident,version,source,data in relations:
        tags=data['tags']; members=data['members']
        if tags.get('public_transport')!='stop_area' and tags.get('railway')!='station': continue
        raw_stops=[ref for t,ref,role in members if t=='n' and ref in coords and role.startswith('stop')]
        stops=[ref for ref in raw_stops if ref in all_refs and station_type(node_tags[ref])]
        excluded_stops=[ref for ref in raw_stops if not station_type(node_tags[ref])]
        mode_rejection='excluded_stop_area_transport_mode' if not station_type(tags) else \
            'stop_area_only_has_excluded_transport_stops' if excluded_stops and not stops else ''
        if not mode_rejection:
            for t,ref,role in members:
                if (t,ref) in candidates and station_type(candidates[(t,ref)]['tags']):
                    association[(t,ref)].update(stops)
        # A named stop-area itself can identify a station without a station building object.
        if (stops or (raw_stops and mode_rejection)) and any(k.startswith('name') for k in tags):
            location_stop=(stops or raw_stops)[0]
            train_evidence=any(node_tags[n].get('train')=='yes' for n in stops) or any(
                (t,ref) in candidates and station_type(candidates[(t,ref)]['tags']) and candidates[(t,ref)]['tags'].get('train')=='yes'
                for t,ref,role in members)
            candidates[('r',ident)]={'osm_type':'relation','osm_id':ident,'version':version,'source':source,
                                    'coord':coords[location_stop],'tags':tags,'geometry_method':'stop_area_rail_stop',
                                    'mode_rejection':mode_rejection,'excluded_mode_stop_nodes':excluded_stops,
                                    'train_evidence':train_evidence}
            if not mode_rejection: association[('r',ident)].update(stops)
        name=tags.get('name:zh') or tags.get('name')
        if name and not mode_rejection:
            for stop in stops: station_names_on_track[stop]=name
    for n,tags in node_tags.items():
        if n in all_refs and tags.get('railway') in {'station','halt','stop'} and station_type(tags):
            name=tags.get('name:zh') or tags.get('name')
            if name: station_names_on_track[n]=name
    rows=[]; city_rows=[]; issues=[]
    place_nodes=[item for item in nodes if item[3]['tags'].get('place') in {'city','town'}]
    for order,(city,region,aliases) in enumerate(CITY_SPECS,1):
        place_matches=[]
        city_names={normalized(city),normalized(city+'市'),normalized(CITY_ENGLISH[order-1])}
        for ident,_,source,data in place_nodes:
            tags=data['tags']
            evidence,_,_=name_evidence(tags,city_names)
            if evidence:
                population=tags.get('population','0').replace(',','')
                pop=int(population) if population.isdigit() else 0
                place_matches.append((evidence,int(tags.get('capital') in {'yes','2','4'}),pop,ident,source,data))
        city_row={'order':order,'city':city,'region':region,'longitude':'','latitude':'',
                  'layout_osm_type':'','layout_osm_id':'','layout_source':'','layout_status':'not_found'}
        if place_matches:
            _,_,_,ident,source,data=max(place_matches,key=lambda r:(r[0],r[1],r[2],-r[3]))
            city_row.update(longitude=data['lon'],latitude=data['lat'],layout_osm_type='node',
                            layout_osm_id=ident,layout_source=f'OSM place node; {source}',layout_status='OSM_place')
        row={'order':order,'city':city,'requested_station':aliases[0] if aliases else '',
             'station_name':'','osm_type':'','osm_id':'','station_longitude':'','station_latitude':'',
             'track_node_id':'','track_longitude':'','track_latitude':'','match_distance_m':'',
             'match_method':'','match_status':'no_matching_station','component_id':'',
             'selection_basis':'明确选定主要重铁站；精确站名匹配，不合并同城其他车站',
             'source':'','note':'','identity_name_match':'','identity_matched_aliases':'',
             'identity_source_tags':'','city_station_distance_m':'','identity_status':'',
             'station_transport_evidence':'','station_raw_tags':'','track_node_raw_tags':''}
        expected=station_aliases({'alt_name':';'.join(aliases)})
        matches=[]; identity_candidates=[]
        found_station=False; rejected_station=False
        for key,candidate in candidates.items():
            if not expected: continue
            evidence,matched_aliases,rejection=name_evidence(candidate['tags'],expected)
            if not evidence and not rejection: continue
            offset=distance_m(candidate['coord'],(city_row['longitude'],city_row['latitude'])) if place_matches else None
            if not rejection and (candidate.get('mode_rejection') or not station_type(candidate['tags'])):
                rejection=candidate.get('mode_rejection') or 'excluded_station_transport_mode'
            if not rejection and offset is not None and offset>CITY_STATION_MAX_METERS:
                rejection='station_outside_city_distance_limit'
            if not rejection and evidence==1 and not place_matches:
                rejection='english_only_station_without_OSM_city_context'
            if rejection:
                rejected_station=True
                issues.append({'city':city,'issue':'station_identity_candidate_rejected','reason':rejection,
                    'osm_type':candidate['osm_type'],'osm_id':candidate['osm_id'],'source':candidate['source'],
                    'station_name':candidate['tags'].get('name:zh') or candidate['tags'].get('name',''),
                    'longitude':candidate['coord'][0],'latitude':candidate['coord'][1],
                    'city_station_distance_m':offset,'matched_aliases':matched_aliases,
                    'name_tags':{k:v for k,v in candidate['tags'].items() if 'name' in k},
                    'transport_tags':candidate['tags'],'excluded_mode_stop_nodes':candidate.get('excluded_mode_stop_nodes',[])})
                continue
            train_score=2 if candidate['tags'].get('train')=='yes' or candidate.get('train_evidence') else 1
            identity_candidates.append((evidence,train_score,key,candidate,matched_aliases,offset))
            found_station=True; anchor=None; method=''; confidence=0
            if key[0]=='n' and key[1] in all_refs:
                anchor=key[1]; method='station_node_on_track'; confidence=3
            else:
                stops=association.get(key,set())
                if stops:
                    anchor=min(stops,key=lambda n:(n not in main_refs,distance_m(candidate['coord'],coords[n]),n))
                    method='OSM_stop_area_membership'; confidence=2
                elif tree is not None:
                    xyz=TO_ECEF.transform(candidate['coord'][0],candidate['coord'][1],0)
                    indices=tree.query_ball_point(xyz,SNAP_METERS)
                    if indices:
                        eligible=[int(track_ids[i]) for i in indices if station_type(node_tags[int(track_ids[i])])]
                        if eligible:
                            anchor=min(eligible,key=lambda n:(distance_m(candidate['coord'],coords[n]),n))
                            method='bounded_nearest_OSM_track_node'; confidence=1
            if anchor is not None:
                gap=distance_m(candidate['coord'],coords[anchor])
                # Relation membership does not need a spatial threshold; it is explicit OSM evidence.
                if method=='bounded_nearest_OSM_track_node' and gap>SNAP_METERS: continue
                matches.append((evidence,train_score,confidence,anchor in main_refs,-gap,key,candidate,anchor,method,matched_aliases,offset))
        if identity_candidates:
            strongest_identity=max((r[0],r[1]) for r in identity_candidates)
            matches=[r for r in matches if (r[0],r[1])==strongest_identity]
        if matches:
            evidence,train_score,confidence,_,neg_gap,key,candidate,anchor,method,matched_aliases,offset=max(
                matches,key=lambda r:(r[0],r[1],r[2],r[3],r[4],-r[5][1]))
            name=candidate['tags'].get('name:zh') or candidate['tags'].get('name') or aliases[0]
            row.update(station_name=name,osm_type=candidate['osm_type'],osm_id=candidate['osm_id'],
                       station_longitude=candidate['coord'][0],station_latitude=candidate['coord'][1],
                       track_node_id=anchor,track_longitude=coords[anchor][0],track_latitude=coords[anchor][1],
                       match_distance_m=round(-neg_gap,3),match_method=method,source=candidate['source'],
                       match_status='topology_matched' if confidence>1 else 'spatial_match_needs_review',
                       note=f"Station location: {candidate['geometry_method']}; identity/track need review; passenger operation not confirmed",
                       identity_name_match='chinese_alias' if evidence==2 else 'english_only_with_city_context',
                       identity_matched_aliases=';'.join(matched_aliases),
                       identity_source_tags=json.dumps({k:v for k,v in candidate['tags'].items() if 'name' in k},ensure_ascii=False),
                       city_station_distance_m=round(offset,3) if offset is not None else '',
                       station_transport_evidence='explicit_train_tag_or_station_member' if train_score==2 else 'mode_unknown_needs_review',
                       station_raw_tags=json.dumps(candidate['tags'],ensure_ascii=False),
                       track_node_raw_tags=json.dumps(node_tags[anchor],ensure_ascii=False),
                       identity_status='name_and_city_proximity_checked_not_manual_verification' if offset is not None else 'chinese_name_only_city_context_missing_needs_review')
            if confidence==1:
                issues.append({'city':city,'issue':'bounded_spatial_match_requires_visual_review','distance_m':-neg_gap})
            if confidence>1 and -neg_gap>2000:
                issues.append({'city':city,'issue':'explicit_topology_membership_has_large_location_offset','distance_m':-neg_gap})
            if not place_matches:
                issues.append({'city':city,'issue':'station_identity_has_no_OSM_city_context_requires_review'})
            elif evidence==1:
                issues.append({'city':city,'issue':'english_only_station_identity_requires_review'})
            if not place_matches:
                city_row.update(longitude=candidate['coord'][0],latitude=candidate['coord'][1],
                                layout_osm_type=candidate['osm_type'],layout_osm_id=candidate['osm_id'],
                                layout_source=candidate['source'],layout_status='station_layout_fallback_not_city_center')
        elif found_station:
            evidence,train_score,key,candidate,matched_aliases,offset=max(identity_candidates,
                key=lambda r:(r[0],r[1],-(r[5] if r[5] is not None else math.inf),-r[2][1]))
            row.update(station_name=candidate['tags'].get('name:zh') or candidate['tags'].get('name') or aliases[0],
                osm_type=candidate['osm_type'],osm_id=candidate['osm_id'],source=candidate['source'],
                station_longitude=candidate['coord'][0],station_latitude=candidate['coord'][1],
                match_status='station_found_no_reliable_track_match',note=f'Station identified but no permitted explicit stop or actual track node within {SNAP_METERS:g} m; no anchor invented',
                identity_name_match='chinese_alias' if evidence==2 else 'english_only_with_city_context',
                identity_matched_aliases=';'.join(matched_aliases),
                identity_source_tags=json.dumps({k:v for k,v in candidate['tags'].items() if 'name' in k},ensure_ascii=False),
                city_station_distance_m=round(offset,3) if offset is not None else '',
                identity_status='station_identified_track_unmatched_needs_review',
                station_transport_evidence='explicit_train_tag_or_station_member' if train_score==2 else 'mode_unknown_needs_review',
                station_raw_tags=json.dumps(candidate['tags'],ensure_ascii=False))
        elif rejected_station:
            row.update(match_status='station_identity_candidates_rejected',
                       identity_status='no_identity_candidate_passed',
                       note='Name/city identity gate rejected all candidates; see station_candidate_rejections.csv; no substitute invented')
        if not aliases:
            row.update(match_status='no_heavy_rail_representative_selected',note='澳门轻轨不在 railway=rail 筛选口径内；不添加虚拟大陆连接')
        rows.append(row); city_rows.append(city_row)
    return rows,city_rows,coords,station_names_on_track,issues
