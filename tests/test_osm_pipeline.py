"""Artificial, explicitly labelled fixtures. These do not establish real routes."""
import json
import math
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
import osmium
from osmium.osm import mutable
from railway.config import CITY_ORDER
from railway.download import validate_header
from railway.extract import classify
from railway.graph import Edge,RailGraph,geometry_km,build_edges,compress_cities,select_station_access
from railway.export import validate_path,segment_route
from railway.pipeline import local_inputs,run
from railway.stations import map_stations,station_aliases,name_evidence
from railway.common import native_osmium_filename

def fixture(raw):
    raw.mkdir(parents=True,exist_ok=True)
    positions={1:(113.,23.),2:(113.1,23.05),3:(113.2,23.),4:(113.3,23.),
               5:(113.1,23.01),6:(113.1,22.99),7:(113.1,23.11),10:(110.,35.),11:(110.1,35.)}
    with native_osmium_filename(raw/'china-latest.osm.pbf') as filename,osmium.SimpleWriter(filename) as writer:
        for n,(lon,lat) in positions.items():
            tags={}
            if n in {1,3,4}: tags={'railway':'station','name':{1:'广州站',3:'武汉站',4:'兰州站'}[n]}
            writer.add_node(mutable.Node(id=n,version=1,location=(lon,lat),tags=tags))
        for n,name in [(1001,'广州'),(1002,'武汉'),(1003,'兰州')]:
            coord=positions[{1001:1,1002:3,1003:4}[n]]
            writer.add_node(mutable.Node(id=n,version=1,location=coord,tags={'place':'city','name':name}))
        ways=[(100,[1,2,3],{'railway':'rail','usage':'main','name':'人工测试线'}),
              (101,[3,4],{'railway':'rail','usage':'main','name':'人工测试线'}),
              (102,[1,5,4],{'railway':'rail','service':'yard'}),
              (103,[1,4],{'railway':'subway'}),
              (104,[1,4],{'railway':'rail','passenger':'no'}),
              (105,[6,7],{'railway':'rail','usage':'main'}),
              (106,[10,11],{'railway':'rail'})]
        for ident,refs,tags in ways: writer.add_way(mutable.Way(id=ident,version=1,nodes=refs,tags=tags))
    with native_osmium_filename(raw/'taiwan-latest.osm.pbf') as filename,osmium.SimpleWriter(filename) as writer:
        writer.add_node(mutable.Node(id=1,version=1,location=positions[1],tags={'railway':'station','name':'广州站'}))
        writer.add_node(mutable.Node(id=2,version=2,location=positions[2]))
        writer.add_node(mutable.Node(id=3,version=1,location=positions[3],tags={'railway':'station','name':'武汉站'}))
        writer.add_way(mutable.Way(id=100,version=1,nodes=[1,2,3],tags={'railway':'rail','usage':'main','name':'人工测试线'}))

class GeometryAndTopologyTests(unittest.TestCase):
    def test_polyline_not_endpoint_distance(self):
        p=[(113,23),(113.1,23.05),(113.2,23)]
        self.assertGreater(geometry_km(p),geometry_km([p[0],p[-1]]))

    def test_filtering(self):
        for tags in [{'railway':'subway'},{'railway':'construction'},{'railway':'rail','usage':'industrial'},
                     {'railway':'rail','passenger':'no'},{'railway':'rail','access':'private'},
                     {'railway':'rail','disused':'yes'}]:
            self.assertEqual(classify(tags)[0],'exclude')
        self.assertEqual(classify({'railway':'rail','service':'yard'})[0],'access_only')
        self.assertEqual(classify({'railway':'rail'}),('main','usage_unknown'))

    def test_crossing_is_not_connection(self):
        coords={1:(0,0),2:(2,0),3:(1,-1),4:(1,1)}
        ways=[(1,1,'fixture',{'tags':{'railway':'rail'},'refs':[1,2]}),
              (2,1,'fixture',{'tags':{'railway':'rail'},'refs':[3,4]})]
        edges,_=build_edges(ways,coords,set()); graph=RailGraph(edges,coords)
        self.assertEqual(graph.component_count,2)
        self.assertTrue(math.isinf(graph.shortest(1,4)[0]))

    def test_parallel_tracks_not_added(self):
        coords={1:(0,0),2:(.1,0),3:(.05,.1)}
        a=Edge(0,1,2,(1,2),geometry_km([coords[1],coords[2]]),100,1,{},'fixture','main')
        b=Edge(1,1,2,(1,3,2),geometry_km([coords[1],coords[3],coords[2]]),101,1,{},'fixture','main')
        graph=RailGraph([a,b],coords)
        self.assertEqual(len(graph.edges),2)
        self.assertAlmostEqual(graph.shortest(1,2)[0],a.km)

    def test_third_station_barrier(self):
        coords={1:(0,0),2:(.1,0),3:(.2,0)}
        edges=[Edge(0,1,2,(1,2),1,100,1,{},'fixture','main'),Edge(1,2,3,(2,3),1,101,1,{},'fixture','main')]
        records=compress_cities(RailGraph(edges,coords),{'A':1,'B':2,'C':3})
        self.assertEqual({frozenset((r['city_a'],r['city_b'])) for r in records},{frozenset(('A','B')),frozenset(('B','C'))})

    def test_station_access_not_yard_shortcut(self):
        coords={1:(0,0),2:(.1,.1),3:(.2,0),4:(.1,0)}
        edges=[Edge(0,1,2,(1,2),10,100,1,{},'fixture','main'),Edge(1,2,3,(2,3),10,101,1,{},'fixture','main'),
               Edge(2,1,4,(1,4),1,102,1,{},'fixture','access_only'),Edge(3,4,3,(4,3),2,103,1,{},'fixture','access_only')]
        graph,diag=select_station_access(edges,coords,[4])
        self.assertAlmostEqual(graph.shortest(1,3)[0],20)
        self.assertAlmostEqual(graph.shortest(4,1)[0],1)
        self.assertNotIn(3,graph.edges)

    def test_missing_shape_point_not_bridged(self):
        ways=[(1,1,'fixture',{'tags':{'railway':'rail'},'refs':[1,2,3]})]
        edges,quality=build_edges(ways,{1:(0,0),3:(1,0)},set())
        self.assertEqual(edges,[]); self.assertEqual(quality['missing_geometry_ways'][0]['count'],1)

    def test_invalid_html_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'invalid.osm.pbf'; p.write_text('<html>403 Forbidden</html>')
            with self.assertRaises(ValueError): validate_header(p)

    def test_local_missing_does_not_download(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d,patch('subprocess.run',side_effect=AssertionError('Network attempted')):
            with self.assertRaises(FileNotFoundError): local_inputs(Path(d),['china','taiwan'])

    def test_dated_local_pbf_is_used_offline(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            raw=Path(d)/'raw'; fixture(raw)
            (raw/'china-latest.osm.pbf').rename(raw/'china-261013.osm.pbf')
            (raw/'taiwan-latest.osm.pbf').rename(raw/'taiwan-20261013.osm.pbf')
            with patch('subprocess.run',side_effect=AssertionError('Network attempted')):
                paths,manifest=local_inputs(raw,['china','taiwan'])
            self.assertEqual([p.name for p in paths],['china-261013.osm.pbf','taiwan-20261013.osm.pbf'])
            self.assertEqual(manifest['china']['local_filename'],'china-261013.osm.pbf')

    def test_ambiguous_dated_local_files_are_not_guessed(self):
        with tempfile.TemporaryDirectory() as d:
            raw=Path(d)
            for name in ['china-261012.osm.pbf','china-261013.osm.pbf']: (raw/name).touch()
            with self.assertRaisesRegex(ValueError,'多个日期版'):
                local_inputs(raw,['china'])

    def test_canonical_local_filename_precedes_dated_file(self):
        with tempfile.TemporaryDirectory() as d:
            raw=Path(d)/'raw';fixture(raw)
            (raw/'china-261013.osm.pbf').write_bytes(b'not selected')
            paths,_=local_inputs(raw,['china'])
            self.assertEqual(paths[0].name,'china-latest.osm.pbf')

    def test_station_stop_area_and_snap_threshold(self):
        # A real topological relation in an artificial fixture beats spatial snapping.
        nodes=[(1,1,'fixture',{'lon':113.,'lat':23.,'tags':{'railway':'station','name':'广州站'}}),
               (2,1,'fixture',{'lon':113.01,'lat':23.,'tags':{'public_transport':'stop_position','train':'yes'}}),
               (3,1,'fixture',{'lon':113.02,'lat':23.,'tags':{}}),
               (4,1,'fixture',{'lon':114.,'lat':24.,'tags':{'railway':'station','name':'兰州站'}})]
        ways=[(100,1,'fixture',{'tags':{'railway':'rail'},'refs':[2,3]})]
        relations=[(200,1,'fixture',{'tags':{'public_transport':'stop_area','name':'广州站'},
                                    'members':[('n',1,''),('n',2,'stop')]})]
        rows,*_=map_stations(nodes,ways,relations)
        gz=next(r for r in rows if r['city']=='广州'); lz=next(r for r in rows if r['city']=='兰州')
        self.assertEqual(gz['track_node_id'],2); self.assertEqual(gz['match_method'],'OSM_stop_area_membership')
        self.assertEqual(lz['track_node_id'],''); self.assertEqual(lz['match_status'],'station_found_no_reliable_track_match')

    def test_bounded_spatial_match_remains_flagged(self):
        nodes=[(1,1,'fixture',{'lon':113.,'lat':23.,'tags':{'railway':'station','name':'广州站'}}),
               (2,1,'fixture',{'lon':113.0001,'lat':23.,'tags':{}}),
               (3,1,'fixture',{'lon':113.001,'lat':23.,'tags':{}})]
        ways=[(100,1,'fixture',{'tags':{'railway':'rail'},'refs':[2,3]})]
        rows,*_=map_stations(nodes,ways,[])
        row=next(r for r in rows if r['city']=='广州')
        self.assertEqual(row['track_node_id'],2); self.assertEqual(row['match_status'],'spatial_match_needs_review')

    def test_empty_rail_subset_preserves_isolated_nodes(self):
        graph=RailGraph([],{})
        self.assertEqual(graph.component_count,0)
        self.assertEqual(compress_cities(graph,{}),[])

class EndToEndFixtureTests(unittest.TestCase):
    def test_diagnostics_reads_cache_without_rerun_or_changing_results(self):
        from unittest.mock import patch
        import hashlib
        import zipfile
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from tools.station_diagnostics import diagnose
        with tempfile.TemporaryDirectory(prefix='诊断 测试 ') as directory:
            root=Path(directory);fixture(root/'data/raw')
            run(root/'data/raw',root/'data/cache',root/'outputs',make_plots=False,test_fixture=True)
            paths=list((root/'outputs').glob('*.csv'))+list((root/'outputs').glob('*.json'))+[root/'data/cache/rail_subset.sqlite']
            original={p:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
            with patch('osmium.SimpleHandler.apply_file',side_effect=AssertionError('Diagnostics rescanned PBF')), \
                 patch('pickle.load',side_effect=AssertionError('Diagnostics loaded nationwide graph')):
                bundle=diagnose(root)
            self.assertTrue(all(hashlib.sha256(p.read_bytes()).hexdigest()==digest for p,digest in original.items()))
            result=json.loads((root/'outputs/station_diagnostics.json').read_text())
            lanzhou=result['evidence']['兰州']
            self.assertEqual(lanzhou['selected_osm_object']['data']['tags']['railway'],'station')
            self.assertTrue(lanzhou['incident_rail_ways'])
            self.assertTrue(lanzhou['track_node_coordinates'])
            with zipfile.ZipFile(bundle) as archive:
                self.assertIsNone(archive.testzip())
                self.assertFalse(any(n.endswith(('.pbf','.pkl','.sqlite')) for n in archive.namelist()))

    def test_diagnostics_missing_cache_does_not_create_or_download_data(self):
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
        from tools.station_diagnostics import diagnose
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError): diagnose(Path(directory))
            self.assertFalse((Path(directory)/'data').exists())

    def test_old_station_graph_cache_rebuilt_but_extraction_reused(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); fixture(root/'raw')
            run(root/'raw',root/'cache',root/'outputs',make_plots=False,test_fixture=True)
            metadata=root/'cache/graph.json'
            old=json.loads(metadata.read_text()); old['fingerprint']['graph_version']=4
            old['fingerprint'].pop('station_identity',None)
            metadata.write_text(json.dumps(old),encoding='utf-8')
            with patch('railway.pipeline.map_stations',wraps=map_stations) as mapper, \
                 patch('railway.extract.WaysRelations.apply_file',side_effect=AssertionError('PBF rescanned despite valid subset')):
                q=run(root/'raw',root/'cache',root/'outputs',make_plots=False,test_fixture=True)
            self.assertEqual(mapper.call_count,1)
            self.assertEqual(q['mapped_stations'],3)
            self.assertIn('station_identity',json.loads(metadata.read_text())['fingerprint'])
            self.assertTrue((root/'outputs/station_candidate_rejections.csv').exists())

    def test_offline_pbf_to_exports_and_repeatable_cache(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory(prefix='铁路 测试 ') as d:
            root=Path(d); fixture(root/'data/raw')
            with patch('subprocess.run',side_effect=AssertionError('Offline input attempted a network request')):
                q=run(root/'data/raw',root/'cache',root/'outputs',make_plots=False,test_fixture=True)
            self.assertEqual(q['city_graph']['node_count'],34)
            self.assertTrue(q['city_order_verified']); self.assertEqual(q['mapped_stations'],3)
            self.assertEqual(q['city_graph']['edge_count'],2)
            self.assertEqual(q['guangzhou_lanzhou']['status'],'reachable')
            self.assertEqual(q['guangzhou_lanzhou']['selected_city_sequence'],['广州','武汉','兰州'])
            self.assertGreaterEqual(q['data_extraction']['relevant_duplicate_objects']['w'],1)
            self.assertGreaterEqual(q['data_extraction']['relevant_duplicate_objects']['n'],1)
            import sqlite3
            with sqlite3.connect(root/'cache/rail_subset.sqlite') as db:
                self.assertEqual(db.execute("SELECT version FROM objects WHERE type='n' AND id=2").fetchone()[0],2)
            self.assertEqual(q['run_status'],'synthetic_test_fixture_only_not_national_data')
            edges=json.loads((root/'outputs/edge_paths.geojson').read_text(encoding='utf-8'))
            self.assertEqual(len(edges['features']),2)
            for feature in edges['features']:
                self.assertAlmostEqual(geometry_km(feature['geometry']['coordinates']),feature['properties']['distance_km'],places=8)
            q2=run(root/'data/raw',root/'cache',root/'outputs',make_plots=False,test_fixture=True)
            self.assertAlmostEqual(q2['guangzhou_lanzhou']['total_km'],q['guangzhou_lanzhou']['total_km'])

    def test_unreachable_route_status_no_fabricated_path(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); fixture(root/'raw')
            # Remove the fixture's only corridor into the endpoint, leaving its OSM station unconnected.
            with native_osmium_filename(root/'raw/taiwan-new.osm.pbf') as filename,osmium.SimpleWriter(filename) as writer:
                writer.add_way(mutable.Way(id=101,version=2,nodes=[3,4],tags={'railway':'rail','passenger':'no'}))
                writer.add_way(mutable.Way(id=102,version=2,nodes=[1,5,4],tags={'railway':'rail','passenger':'no'}))
            (root/'raw/taiwan-latest.osm.pbf').unlink()
            (root/'raw/taiwan-new.osm.pbf').rename(root/'raw/taiwan-latest.osm.pbf')
            q=run(root/'raw',root/'cache',root/'outputs',make_plots=False,test_fixture=True)
            self.assertEqual(q['guangzhou_lanzhou']['status'],'unreachable')
            self.assertFalse((root/'outputs/guangzhou_lanzhou_path.geojson').exists())
            self.assertFalse((root/'outputs/guangzhou_lanzhou_segments.csv').exists())

class StationIdentityRegressionTests(unittest.TestCase):
    """Synthetic collision cases, not claims about unreceived live OSM name tags."""
    def node(self,ident,coord,**tags):
        return (ident,1,'synthetic_collision_fixture',{'lon':coord[0],'lat':coord[1],'tags':tags})

    def collision_data(self,wrong_name='浮洲'):
        nodes=[self.node(1,(119.29,26.08),railway='station',name='福州'),
               self.node(2,(119.2901,26.08)),self.node(3,(119.30,26.08)),
               self.node(10,(121.44476,25.00416)),self.node(11,(121.45,25.00416)),
               self.node(20,(119.29,26.07),place='city',name='福州市'),
               self.node(21,(121.44,25.0),place='city',name='浮洲',**{'name:en':'Fuzhou','capital':'yes','population':'99999999'})]
        ways=[(100,1,'fixture',{'tags':{'railway':'rail'},'refs':[2,3]}),
              (101,1,'fixture',{'tags':{'railway':'rail'},'refs':[10,11]})]
        relations=[(200,1,'fixture',{'tags':{'public_transport':'stop_area','name':wrong_name,'name:en':'Fuzhou Railway Station'},
                                    'members':[('n',10,'stop')]})]
        return nodes,ways,relations

    def test_fuzhou_chinese_conflict_beats_wrong_topology(self):
        rows,cities,_,_,issues=map_stations(*self.collision_data())
        row=next(r for r in rows if r['city']=='福州')
        self.assertEqual(row['osm_id'],1)
        self.assertEqual(row['track_node_id'],2)
        self.assertEqual(row['match_status'],'spatial_match_needs_review')
        self.assertEqual(row['identity_name_match'],'chinese_alias')
        self.assertEqual(next(r for r in cities if r['city']=='福州')['layout_osm_id'],20)
        rejected=[r for r in issues if r['issue']=='station_identity_candidate_rejected' and r['osm_id']==200]
        self.assertEqual(rejected[0]['reason'],'english_alias_conflicts_with_chinese_name')
        self.assertGreater(rejected[0]['city_station_distance_m'],80000)

    def test_distant_even_exact_chinese_name_is_rejected(self):
        rows,_,_,_,issues=map_stations(*self.collision_data(wrong_name='福州'))
        self.assertEqual(next(r for r in rows if r['city']=='福州')['osm_id'],1)
        self.assertTrue(any(r.get('reason')=='station_outside_city_distance_limit' for r in issues))

    def test_only_bad_identity_preserves_city_unmapped(self):
        nodes,ways,relations=self.collision_data(); nodes=[n for n in nodes if n[0]!=1]
        rows,cities,_,_,_=map_stations(nodes,ways,relations)
        row=next(r for r in rows if r['city']=='福州')
        self.assertEqual(row['match_status'],'station_identity_candidates_rejected')
        self.assertEqual(row['track_node_id'],'')
        self.assertEqual(len(cities),34)

    def test_chinese_name_precedes_nearby_english_only_on_track(self):
        nodes,ways,_=self.collision_data()
        nodes.append(self.node(4,(119.2902,26.08),railway='station',name='Fuzhou Railway Station'))
        ways.append((102,1,'fixture',{'tags':{'railway':'rail'},'refs':[3,4]}))
        rows,*_=map_stations(nodes,ways,[])
        self.assertEqual(next(r for r in rows if r['city']=='福州')['osm_id'],1)

    def test_english_only_needs_independent_city_context(self):
        nodes=[self.node(1,(119.29,26.08),railway='station',name='Fuzhou Railway Station'),
               self.node(2,(119.30,26.08))]
        ways=[(100,1,'fixture',{'tags':{'railway':'rail'},'refs':[1,2]})]
        rows,*_=map_stations(nodes,ways,[])
        self.assertEqual(next(r for r in rows if r['city']=='福州')['track_node_id'],'')
        nodes.append(self.node(20,(119.29,26.07),place='city',name='福州'))
        rows,*_=map_stations(nodes,ways,[])
        row=next(r for r in rows if r['city']=='福州')
        self.assertEqual(row['track_node_id'],1)
        self.assertEqual(row['identity_name_match'],'english_only_with_city_context')

    def test_train_station_chinese_suffix_and_traditional_names(self):
        for expected,actual in [('广州站','广州火车站'),('臺北車站','台北车站')]:
            score,_,reason=name_evidence({'name':actual},station_aliases({'name':expected}))
            self.assertEqual(score,2); self.assertEqual(reason,'')

if __name__=='__main__': unittest.main()
