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
from railway.stations import map_stations
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

if __name__=='__main__': unittest.main()
