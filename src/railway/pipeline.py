import json
import os
import pickle
import sqlite3
from pathlib import Path
from .config import ROOT,RAW,CACHE,OUT,CITY_SPECS,CITY_ORDER,SOURCES
from .common import now,save_json,save_csv,sha256
from .download import validate_header,download
from .extract import extract,load_objects
from .stations import map_stations
from .graph import build_edges,select_station_access,compress_cities
from .export import write_outputs
from .plotting import plots

GRAPH_VERSION=4

def local_inputs(raw_dir,regions):
    """Local files never cause network requests, even when no manifest exists."""
    raw_dir=Path(raw_dir); paths=[raw_dir/f'{r}-latest.osm.pbf' for r in regions]
    manifest_file=raw_dir/'sources.json'
    manifest=json.loads(manifest_file.read_text(encoding='utf-8')) if manifest_file.exists() else {}
    for region,path in zip(regions,paths):
        if not path.is_file():
            raise FileNotFoundError(f'请将已下载的 {path.name} 放到 {raw_dir}；本地模式不会联网下载')
        print(f'[1/7] 检查本地 PBF 文件头及 SHA-256: {path.name} ({path.stat().st_size/1024**3:.2f} GiB)',flush=True)
        header=validate_header(path); checksum=sha256(path); previous=manifest.get(region,{})
        if previous.get('sha256') and previous['sha256']!=checksum:
            raise ValueError(f'{path.name} 与原有来源清单的 SHA-256 不一致；若明确更换数据版本，请先备份并删除 sources.json 后重新运行')
        manifest[region]={**previous,'source_url':SOURCES[region],'origin':previous.get('origin','user_supplied_local'),
                          'registered_at':now(),'size':path.stat().st_size,'sha256':checksum,
                          'verified_header':True,'upstream_checksum_status':previous.get('upstream_checksum_status','not_checked_offline'),
                          **header}
    save_json(manifest_file,manifest)
    return paths,manifest

def run(raw_dir=RAW,cache_dir=CACHE,out=OUT,with_guangdong=False,make_plots=True,test_fixture=False):
    out=Path(out); cache_dir=Path(cache_dir); out.mkdir(parents=True,exist_ok=True); cache_dir.mkdir(parents=True,exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR',str(cache_dir/'matplotlib'))
    os.environ.setdefault('XDG_CACHE_HOME',str(cache_dir/'font_cache'))
    Path(os.environ['MPLCONFIGDIR']).mkdir(parents=True,exist_ok=True)
    regions=['china','taiwan']+(['guangdong'] if with_guangdong else [])
    # Mark a new run before doing work; failures cannot masquerade as a previous success.
    save_json(out/'run_status.json',{'status':'running','started_at':now(),'test_fixture':test_fixture})
    paths,manifest=local_inputs(raw_dir,regions)
    if test_fixture:
        for region in regions:
            manifest[region].update(origin='synthetic_test_fixture',source_url='not_applicable_synthetic_test_fixture')
        save_json(Path(raw_dir)/'sources.json',manifest)
    print('[2/7] 流式提取铁路、车站、布局节点和站场关系（两遍扫描，使用磁盘缓存）',flush=True)
    subset,metadata=extract(paths,cache_dir,manifest)
    for region in regions: manifest[region]['full_pbf_parse_completed']=True
    save_json(Path(raw_dir)/'sources.json',manifest)
    fingerprint={'graph_version':GRAPH_VERSION,'extraction':metadata['fingerprint'],'representatives':CITY_SPECS}
    graph_cache=cache_dir/'graph.pkl'; cache_meta=cache_dir/'graph.json'
    can_reuse=False
    if graph_cache.exists() and cache_meta.exists():
        stored=json.loads(cache_meta.read_text())
        can_reuse=json.dumps(stored['fingerprint'],sort_keys=True)==json.dumps(fingerprint,sort_keys=True)
    if can_reuse:
        print('[3/7] 使用已缓存的轨道图和车站映射',flush=True)
        with graph_cache.open('rb') as f:
            graph,station_rows,city_rows,station_names,issues,graph_quality,access_info=pickle.load(f)
    else:
        print('[3/7] 建立车站映射和 WGS84 轨道拓扑',flush=True)
        db=sqlite3.connect(subset)
        nodes=list(load_objects(db,'n')); ways=list(load_objects(db,'w')); relations=list(load_objects(db,'r')); db.close()
        station_rows,city_rows,coords,station_names,issues=map_stations(nodes,ways,relations)
        selected=[int(r['track_node_id']) for r in station_rows if r['track_node_id']!='']
        edges,graph_quality=build_edges(ways,coords,set(selected)|set(station_names))
        graph,access_info=select_station_access(edges,coords,selected)
        for r in station_rows:
            if r['track_node_id']!='':
                node=int(r['track_node_id']); component=graph.component(node)
                r['component_id']=component if component is not None else ''
                if component is None:
                    r['match_status']='track_match_without_mainline_access'
                    r['note']+='; matched track has no permitted connection to a mainline'
        payload=(graph,station_rows,city_rows,station_names,issues,graph_quality,access_info)
        with graph_cache.with_suffix('.tmp').open('wb') as f: pickle.dump(payload,f,protocol=pickle.HIGHEST_PROTOCOL)
        graph_cache.with_suffix('.tmp').replace(graph_cache); save_json(cache_meta,{'fingerprint':fingerprint})
        del nodes,ways,relations,edges,coords
    anchors={r['city']:int(r['track_node_id']) for r in station_rows if r['track_node_id']!='' and int(r['track_node_id']) in graph.index}
    print(f"[4/7] 构建城市压缩图（{len(anchors)}/34 个代表站已接入；只搜索到下一个代表站）",flush=True)
    city_edges=compress_cities(graph,anchors)
    city_index={city:i for i,city in enumerate(CITY_ORDER)}
    city_edges.sort(key=lambda e:(city_index[e['city_a']],city_index[e['city_b']]))
    print(f'[5/7] 导出 {len(city_edges)} 条城市边；计算广州 → 兰州并重新核验所有路径长度',flush=True)
    quality,path=write_outputs(out,graph,station_rows,city_rows,city_edges,station_names,metadata,graph_quality,issues,access_info)
    save_csv(out/'city_edge_distances.csv',[{'edge_id':e['edge_id'],'city_a':e['city_a'],'city_b':e['city_b'],
              'distance_km':format(e['distance_km'],'.12f')} for e in city_edges],['edge_id','city_a','city_b','distance_km'])
    if test_fixture:
        quality['run_status']='synthetic_test_fixture_only_not_national_data'
        quality['data_quality_note']='Artificial unit-test PBF; no real-world route result is established'
        save_json(out/'data_quality.json',quality)
    if make_plots:
        print('[6/7] 生成中文网络图和车站检查图（PNG + SVG）',flush=True)
        plots(out,graph,city_rows,station_rows,city_edges,path,quality)
    else:
        print('[6/7] 本次明确跳过绘图（不作为完整交付）',flush=True)
    route=quality['guangzhou_lanzhou']
    text=summary_text(quality)
    (out/'RESULTS.md').write_text(text,encoding='utf-8')
    save_json(out/'run_status.json',{'status':'completed_test_fixture' if test_fixture else 'completed_real_osm',
                                   'completed_at':now(),'data_quality_file':'data_quality.json',
                                   'route_status':route['status'],'plotting_executed':make_plots})
    print('[7/7] 文件与质量检查完成',flush=True); print(text,flush=True)
    return quality

def summary_text(q):
    g=q['city_graph']; route=q['guangzhou_lanzhou']; label='基于 OSM 铁路线形计算的几何里程'
    text=f"# 处理结果\n\n数据状态：{q['run_status']}。\n\n"
    text+=f"代表站接入：{q['mapped_stations']}/34；城市边：{g['edge_count']}；城市连通分量：{g['component_count']}。\n\n"
    text+='孤立城市：'+('、'.join(g['isolated_cities']) or '无')+'。\n\n'
    if route['status']=='reachable':
        text+=f"广州至兰州：可达，{route['total_km']:.6f} km（{label}）。\n\n"
        text+='选定代表站对应城市序列：'+' → '.join(route['selected_city_sequence'])+'。\n\n'
    else:
        text+='广州至兰州：不可达。原因：'+route['reason']+'。\n\n'
    text+='待人工检查的空间匹配：'+('、'.join(q['spatial_matches_pending_review']) or '无')+'。\n\n'
    text+='轨道筛选、覆盖、去重、缺失形状点与可疑断点见 `data_quality.json`。线路和用途未知不表示已确认可用于客运。\n'
    if q.get('data_quality_note'): text+='\n'+q['data_quality_note']+'\n'
    return text
