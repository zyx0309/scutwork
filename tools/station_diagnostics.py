"""Read local SQLite railway evidence without PBF rescans, network or graph loading."""
import csv
import json
from pathlib import Path
import sqlite3
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from railway.config import CITY_SPECS
from railway.stations import station_aliases,name_evidence,distance_m
from railway.extract import classify
from railway.common import save_json,now

FOCUS={'福州','南京','海口','西安','乌鲁木齐','兰州','西宁','天津','贵阳'}

def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as stream:
        return list(csv.DictReader(stream))

def diagnose(root=ROOT):
    root=Path(root); out=root/'outputs'; cache=root/'data/cache'
    dbpath=cache/'rail_subset.sqlite'
    if not dbpath.is_file():
        raise FileNotFoundError(f'未找到本地提取缓存 {dbpath}；本工具不会重新扫描 PBF。请在原项目目录使用。')
    stations=read_csv(out/'city_stations.csv'); cities=read_csv(out/'cities.csv')
    quality=json.loads((out/'data_quality.json').read_text(encoding='utf-8-sig'))
    metadata=json.loads((cache/'extraction.json').read_text(encoding='utf-8-sig'))
    if not metadata.get('parse_completed') or metadata.get('fingerprint')!=quality.get('data_extraction',{}).get('fingerprint'):
        raise ValueError('提取缓存与这次结果的来源指纹不一致，拒绝混合不同数据版本。')
    state=json.loads((out/'run_status.json').read_text(encoding='utf-8-sig'))
    if state.get('status') not in {'completed_real_osm','completed_test_fixture'}:
        raise ValueError('最近一次运行尚未完成；保留失败日志，不将残留文件打包为已完成结果。')
    expected={city:station_aliases({'alt_name':';'.join(aliases)}) for city,_,aliases in CITY_SPECS if city in FOCUS}
    layouts={r['city']:(float(r['longitude']),float(r['latitude'])) for r in cities
             if r['longitude'] and r['latitude']}
    evidence={r['city']:{'selected_station_csv':r,'name_candidates':[],
                       'related_station_relations':[],'incident_rail_ways':[]} for r in stations if r['city'] in FOCUS}
    # SQLite read-only URI handles Unicode, spaces and Windows drive letters.
    db=sqlite3.connect(dbpath.resolve().as_uri()+'?mode=ro',uri=True)
    db.execute('PRAGMA query_only=ON')
    def object_record(kind,ident):
        result=db.execute('SELECT version,source,data FROM objects WHERE type=? AND id=?',(kind,int(ident))).fetchone()
        if result is None: return None
        version,source,data=result
        return {'osm_type':kind,'osm_id':int(ident),'version':version,'source':source,'data':json.loads(data)}
    interest={}
    def follow_node(node,city): interest.setdefault(int(node),set()).add(city)
    try:
        print('[1/4] 读取代表站原始对象和轨道锚点（只读 SQLite）',flush=True)
        for city,record in evidence.items():
            row=record['selected_station_csv']
            record['selected_osm_object']=object_record(row['osm_type'][0],row['osm_id']) if row['osm_id'] else None
            record['selected_track_node']=object_record('n',row['track_node_id']) if row['track_node_id'] else None
            if row['track_node_id']: follow_node(row['track_node_id'],city)
            if row['osm_type']=='node': follow_node(row['osm_id'],city)
        print('[2/4] 查找同名站候选和完整站场标签（不读取 PBF）',flush=True)
        # Most shape nodes have no names. SQLite streams only named objects into Python.
        query="SELECT type,id,version,source,data FROM objects WHERE data LIKE '%name%'"
        selected_keys={city:(r['selected_station_csv']['osm_type'][:1],r['selected_station_csv']['osm_id']) for city,r in evidence.items()}
        for kind,ident,version,source,payload in db.execute(query):
            data=json.loads(payload); tags=data['tags']
            is_station=tags.get('railway') in {'station','halt','stop'}
            is_relation=kind=='r' and (tags.get('public_transport')=='stop_area' or tags.get('railway')=='station')
            if not (is_station or is_relation): continue
            record={'osm_type':kind,'osm_id':ident,'version':version,'source':source,'data':data}
            for city,aliases in expected.items():
                score,matched,reason=name_evidence(tags,aliases)
                if not score and not reason: continue
                candidate={**record,'name_match_score':score,'matched_aliases':matched,'identity_rejection_reason':reason}
                if kind=='n' and city in layouts:
                    candidate['distance_from_city_m']=distance_m((data['lon'],data['lat']),layouts[city])
                evidence[city]['name_candidates'].append(candidate)
                if kind=='n': follow_node(ident,city)
                if kind=='r':
                    for member_type,ref,role in data.get('members',[]):
                        if member_type=='n' and role.startswith('stop'): follow_node(ref,city)
        # Include unnamed stop areas containing a chosen station/anchor as well.
        for ident,version,source,payload in db.execute("SELECT id,version,source,data FROM objects WHERE type='r'"):
            data=json.loads(payload);tags=data['tags']
            if tags.get('public_transport') not in {'stop_area','stop_area_group'} and tags.get('railway')!='station': continue
            affected=set()
            for kind,ref,role in data.get('members',[]):
                if kind=='n': affected.update(interest.get(ref,set()))
                for city,key in selected_keys.items():
                    if key==(kind,str(ref)): affected.add(city)
            for city in affected:
                evidence[city]['related_station_relations'].append({'osm_type':'r','osm_id':ident,'version':version,'source':source,'data':data})
                for kind,ref,role in data.get('members',[]):
                    if kind=='n' and role.startswith('stop'): follow_node(ref,city)
        print('[3/4] 单遍读取缓存中的线路，找锚点/停靠节点所在 way（不加载全国图）',flush=True)
        for count,(ident,version,source,payload) in enumerate(db.execute("SELECT id,version,source,data FROM objects WHERE type='w'"),1):
            data=json.loads(payload);affected=set()
            for node in data['refs']: affected.update(interest.get(node,set()))
            if affected:
                kind,reason=classify(data['tags'])
                record={'osm_type':'w','osm_id':ident,'version':version,'source':source,
                        'filter_class':kind,'filter_reason':reason,'data':data}
                for city in affected: evidence[city]['incident_rail_ways'].append(record)
            if count%50000==0: print(f'已检查缓存线路 {count:,} 条',flush=True)
        for city,record in evidence.items():
            node_ids=set()
            for way in record['incident_rail_ways']: node_ids.update(way['data']['refs'])
            for candidate in record['name_candidates']:
                if candidate['osm_type']=='w': node_ids.update(candidate['data']['refs'])
            record['track_node_coordinates']=[]
            nodes=sorted(node_ids)
            for start in range(0,len(nodes),500):
                chunk=nodes[start:start+500]
                marks=','.join('?' for _ in chunk)
                for ident,payload in db.execute(f"SELECT id,data FROM objects WHERE type='n' AND id IN ({marks})",chunk):
                    data=json.loads(payload)
                    record['track_node_coordinates'].append({'osm_id':ident,**data})
            component=record['selected_station_csv']['component_id']
            record['nearby_disconnected_endpoints']=[] if not component else [r for r in quality.get('nearby_disconnected_endpoints_diagnostic_only',[])
                if int(component) in (r['component_a'],r['component_b'])]
    finally:
        db.close()
    print('[4/4] 保存原始标签证据并打包小型复核附件',flush=True)
    result={'generated_at':now(),'source_quality_generated_at':quality.get('generated_at'),
            'extraction_fingerprint':metadata['fingerprint'],
            'source_run_status':state,'focus_cities':list(evidence),
            'scope':'Read-only local extraction SQLite; no PBF scan, network, graph pickle load, station remap or route recomputation.',
            'limitations':'Only objects retained by the original extraction are available. Missing excluded transit ways cannot be reconstructed here. Candidate and topology evidence are not automatic manual acceptance.',
            'evidence':evidence}
    save_json(out/'station_diagnostics.json',result)
    names=['cities.csv','city_stations.csv','city_edges.csv','station_candidate_rejections.csv','data_quality.json','run_status.json','RESULTS.md',
           'guangzhou_lanzhou_status.json','guangzhou_lanzhou_segments.csv','station_diagnostics.json',
           'figures/station_checks_detail.png','figures/guangzhou_lanzhou_route.png']
    selected=[out/name for name in names if (out/name).is_file()]
    target=out/'submission/Station_Diagnostics.zip';target.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in selected: archive.write(p,'Station_Diagnostics/'+p.relative_to(out).as_posix())
        archive.writestr('Station_Diagnostics/SCOPE.txt','Only local cache evidence and current small outputs. No PBF or national cache included. No railway connections or station mappings were changed.\n')
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None: raise ValueError('Diagnostic ZIP CRC error')
    print(f'诊断包：{target}\n大小：{target.stat().st_size/1024**2:.2f} MiB；原始 PBF 和缓存未改变。',flush=True)
    if target.stat().st_size>30*1024**2:
        print('诊断包超过 30 MiB，请先上传 station_diagnostics.json 及 CSV/JSON 小文件；图片可单独发送。',flush=True)
    return target

if __name__=='__main__':
    diagnose()
