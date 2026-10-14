"""Representatives are explicit stations, not merged city-centre points."""
import collections
import math
import numpy as np
from pyproj import Transformer
from scipy.spatial import cKDTree
from .config import CITY_SPECS, CITY_ENGLISH, SNAP_METERS
from .extract import normalized, tag_names, classify
from .graph import GEOD

TO_ECEF=Transformer.from_crs('EPSG:4326','EPSG:4978',always_xy=True)

def distance_m(a,b):
    return float(GEOD.inv(a[0],a[1],b[0],b[1])[2])

def station_aliases(tags):
    aliases=tag_names(tags)
    for s in list(aliases):
        if s.endswith('车站'): aliases.add(s[:-2])
        if s.endswith('站'): aliases.add(s[:-1])
        for suffix in ['railwaystation','trainstation','station']:
            if s.endswith(suffix): aliases.add(s[:-len(suffix)])
    return aliases

def station_type(tags):
    return tags.get('station') not in {'subway','light_rail','monorail','tram'} and tags.get('railway')!='tram_stop'

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
        if tags.get('railway') in {'station','halt'} and station_type(tags):
            candidates[('n',ident)]={'osm_type':'node','osm_id':ident,'version':version,'source':source,
                                    'coord':coords[ident],'tags':tags,'geometry_method':'OSM_node'}
    for ident,version,source,data in ways:
        tags=data['tags']
        if tags.get('railway') in {'station','halt'} and station_type(tags):
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
        stops=[ref for t,ref,role in members if t=='n' and ref in all_refs and role.startswith('stop')]
        for t,ref,role in members:
            if (t,ref) in candidates: association[(t,ref)].update(stops)
        # A named stop-area itself can identify a station without a station building object.
        if stops and station_type(tags) and any(k.startswith('name') for k in tags):
            candidates[('r',ident)]={'osm_type':'relation','osm_id':ident,'version':version,'source':source,
                                    'coord':coords[stops[0]],'tags':tags,'geometry_method':'stop_area_rail_stop'}
            association[('r',ident)].update(stops)
        name=tags.get('name:zh') or tags.get('name')
        if name:
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
            if tags.get('place') in {'city','town'} and tag_names(tags)&city_names:
                population=tags.get('population','0').replace(',','')
                pop=int(population) if population.isdigit() else 0
                place_matches.append((int(tags.get('capital') in {'yes','2','4'}),pop,ident,source,data))
        city_row={'order':order,'city':city,'region':region,'longitude':'','latitude':'',
                  'layout_osm_type':'','layout_osm_id':'','layout_source':'','layout_status':'not_found'}
        if place_matches:
            _,_,ident,source,data=max(place_matches,key=lambda r:(r[0],r[1],-r[2]))
            city_row.update(longitude=data['lon'],latitude=data['lat'],layout_osm_type='node',
                            layout_osm_id=ident,layout_source=f'OSM place node; {source}',layout_status='OSM_place')
        row={'order':order,'city':city,'requested_station':aliases[0] if aliases else '',
             'station_name':'','osm_type':'','osm_id':'','station_longitude':'','station_latitude':'',
             'track_node_id':'','track_longitude':'','track_latitude':'','match_distance_m':'',
             'match_method':'','match_status':'no_matching_station','component_id':'',
             'selection_basis':'明确选定主要重铁站；精确站名匹配，不合并同城其他车站',
             'source':'','note':''}
        expected=station_aliases({'alt_name':';'.join(aliases)})
        matches=[]
        found_station=False
        for key,candidate in candidates.items():
            if not expected or not (station_aliases(candidate['tags'])&expected): continue
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
                        eligible=[int(track_ids[i]) for i in indices]
                        anchor=min(eligible,key=lambda n:(distance_m(candidate['coord'],coords[n]),n))
                        method='bounded_nearest_OSM_track_node'; confidence=1
            if anchor is not None:
                gap=distance_m(candidate['coord'],coords[anchor])
                # Relation membership does not need a spatial threshold; it is explicit OSM evidence.
                if method=='bounded_nearest_OSM_track_node' and gap>SNAP_METERS: continue
                matches.append((confidence,anchor in main_refs,-gap,key,candidate,anchor,method))
        if matches:
            confidence,_,neg_gap,key,candidate,anchor,method=max(matches,key=lambda r:(r[0],r[1],r[2],-r[3][1]))
            name=candidate['tags'].get('name:zh') or candidate['tags'].get('name') or aliases[0]
            row.update(station_name=name,osm_type=candidate['osm_type'],osm_id=candidate['osm_id'],
                       station_longitude=candidate['coord'][0],station_latitude=candidate['coord'][1],
                       track_node_id=anchor,track_longitude=coords[anchor][0],track_latitude=coords[anchor][1],
                       match_distance_m=round(-neg_gap,3),match_method=method,source=candidate['source'],
                       match_status='topology_matched' if confidence>1 else 'spatial_match_needs_review',
                       note=f"Station location: {candidate['geometry_method']}; usage/passenger operation not confirmed")
            if confidence==1:
                issues.append({'city':city,'issue':'bounded_spatial_match_requires_visual_review','distance_m':-neg_gap})
            if confidence>1 and -neg_gap>2000:
                issues.append({'city':city,'issue':'explicit_topology_membership_has_large_location_offset','distance_m':-neg_gap})
            if place_matches:
                offset=distance_m(candidate['coord'],(city_row['longitude'],city_row['latitude']))
                if offset>80000:
                    issues.append({'city':city,'issue':'selected_station_more_than_80km_from_OSM_city_place','distance_m':offset})
            if not place_matches:
                city_row.update(longitude=candidate['coord'][0],latitude=candidate['coord'][1],
                                layout_osm_type=candidate['osm_type'],layout_osm_id=candidate['osm_id'],
                                layout_source=candidate['source'],layout_status='station_layout_fallback_not_city_center')
        elif found_station:
            row.update(match_status='station_found_no_reliable_track_match',note=f'No explicit stop or track node within {SNAP_METERS:g} m')
        if not aliases:
            row.update(match_status='no_heavy_rail_representative_selected',note='澳门轻轨不在 railway=rail 筛选口径内；不添加虚拟大陆连接')
        rows.append(row); city_rows.append(city_row)
    return rows,city_rows,coords,station_names_on_track,issues
