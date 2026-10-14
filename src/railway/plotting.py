import os
from pathlib import Path
import numpy as np

def setup_font():
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib import font_manager
    choices=['Microsoft YaHei','SimHei','Noto Sans CJK SC','Noto Sans CJK JP','SimSun','Arial Unicode MS']
    available={f.name for f in font_manager.fontManager.ttflist}
    for name in choices:
        if name in available:
            matplotlib.rcParams['font.family']=[name]; break
    else:
        raise RuntimeError('Chinese font missing. On Windows install Microsoft YaHei; on Linux install Noto Sans CJK.')
    matplotlib.rcParams['axes.unicode_minus']=False
    matplotlib.rcParams['svg.fonttype']='path'
    return matplotlib

def label_cities(ax,coordinates,fontsize=9):
    # Move labels, never node coordinates. White outlines keep Chinese readable.
    import matplotlib.patheffects as pe
    offsets={'北京':(-22,15),'天津':(14,-4),'上海':(14,-6),'南京':(-24,10),
             '杭州':(10,-16),'香港':(18,-14),'澳门':(-25,-15),'广州':(-8,14),
             '成都':(-20,10),'重庆':(12,-5),'西宁':(-28,12),'兰州':(14,6),
             '台北':(12,6),'福州':(-16,10),'石家庄':(-35,-6),'武汉':(8,-12)}
    for city,point in coordinates.items():
        text=ax.annotate(city,point,xytext=offsets.get(city,(7,7)),textcoords='offset points',fontsize=fontsize,
                         zorder=10,color='#a32222' if city in {'广州','兰州'} else '#142936')
        text.set_path_effects([pe.withStroke(linewidth=3,foreground='white')])

def decorate(ax,title):
    from .config import ATTRIBUTION
    ax.set_title(title,fontsize=14,pad=15)
    ax.set_xlabel('经度（布局用途）'); ax.set_ylabel('纬度（布局用途）')
    ax.grid(alpha=.2)
    ax.text(0,-.11,ATTRIBUTION,transform=ax.transAxes,fontsize=7,color='#555555')

def save_figure(fig,path):
    import matplotlib.pyplot as plt
    path=Path(path)
    fig.savefig(path.with_suffix('.png'),dpi=220,bbox_inches='tight')
    fig.savefig(path.with_suffix('.svg'),bbox_inches='tight')
    plt.close(fig)

def plots(out,graph,cities,stations,city_edges,route_path,quality):
    setup_font()
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    out=Path(out)/'figures'; out.mkdir(parents=True,exist_ok=True)
    def finish(fig,path):
        if quality['run_status'].startswith('synthetic_test_fixture'):
            fig.suptitle('人工测试样例 — 非真实全国铁路结果',fontsize=15,color='#b02020')
        save_figure(fig,path)
    xy={r['city']:(float(r['longitude']),float(r['latitude'])) for r in cities if r['longitude']!=''}
    missing=[r['city'] for r in cities if r['longitude']=='']
    isolated=set(quality['city_graph']['isolated_cities'])
    display_edges=city_edges
    dense=len(city_edges)>60
    if dense:
        # A reproducible minimum spanning forest is a display simplification only.
        parent={r['city']:r['city'] for r in cities}
        def find(x):
            while parent[x]!=x: x=parent[x]
            return x
        display_edges=[]
        for edge in sorted(city_edges,key=lambda e:(e['distance_km'],e['edge_id'])):
            a,b=find(edge['city_a']),find(edge['city_b'])
            if a!=b: parent[a]=b; display_edges.append(edge)
    from .common import save_json
    save_json(out/'display_rules.json',{'complete_figure':'city_network','annotated_figure':'city_network_edge_ids',
               'annotated_display_rule':'minimum_spanning_forest_by_geometric_km' if dense else 'all_city_edges',
               'dense_threshold':60,'annotated_edge_ids':[e['edge_id'] for e in display_edges],
               'full_edge_count':len(city_edges),'computation_graph_modified':False})
    for annotated in [False,True]:
        fig,ax=plt.subplots(figsize=(16,11))
        for e in display_edges if annotated else city_edges:
            if e['city_a'] not in xy or e['city_b'] not in xy: continue
            a,b=xy[e['city_a']],xy[e['city_b']]
            ax.plot([a[0],b[0]],[a[1],b[1]],color='#5387a4',alpha=.45,lw=.8)
            if annotated:
                ax.text((a[0]+b[0])/2,(a[1]+b[1])/2,e['edge_id'],fontsize=6,color='#31566a',
                        bbox={'facecolor':'white','alpha':.75,'edgecolor':'none','pad':.3})
        for c,point in xy.items():
            color='#d43b3b' if c in {'广州','兰州'} else '#efab37' if c in isolated else '#226683'
            ax.scatter(*point,s=72 if c in {'广州','兰州'} else 40,c=color,zorder=5,
                       edgecolors='#3a3a3a',linewidths=.5)
        label_cities(ax,xy)
        decorate(ax,'34 个省级行政区代表城市铁路连接图'+('（展示用最小生成森林及边编号）' if annotated and dense else '（边编号）' if annotated else ''))
        ax.text(0,-.06,'边权沿真实 OSM 铁路线形计算，单位 km；抽象连边不表示直达列车。橙色为孤立节点。',
                transform=ax.transAxes,fontsize=9)
        if annotated:
            ax.text(0,-.085,'编号及距离（km）见 city_edge_distances.csv；'+('本图仅展示最小生成森林，完整图及计算网络未删边。' if dense else '完整连接表未做删边。'),transform=ax.transAxes,fontsize=8)
        if missing:
            ax.text(.02,.02,'未获得布局坐标（保留节点）：'+ '、'.join(missing),transform=ax.transAxes,
                    fontsize=9,bbox={'facecolor':'white','alpha':.9,'edgecolor':'#aaaaaa'})
        finish(fig,out/('city_network_edge_ids' if annotated else 'city_network'))
    geometries=[[graph.coords[n] for n in e.refs] for e in graph.edges.values()]
    boxes=np.array([[min(p[0] for p in geo),min(p[1] for p in geo),max(p[0] for p in geo),max(p[1] for p in geo)]
                    for geo in geometries],dtype=float).reshape((-1,4))
    def nearby(xmin,ymin,xmax,ymax):
        indices=np.flatnonzero((boxes[:,0]<=xmax)&(boxes[:,2]>=xmin)&(boxes[:,1]<=ymax)&(boxes[:,3]>=ymin))
        return [geometries[i] for i in indices]
    fig,ax=plt.subplots(figsize=(16,11))
    ax.add_collection(LineCollection(geometries,colors='#547c93',linewidths=.35,alpha=.55))
    sx={r['city']:(r['station_longitude'],r['station_latitude']) for r in stations if r['station_longitude']!=''}
    for r in stations:
        if r['station_longitude']=='': continue
        point=(r['station_longitude'],r['station_latitude'])
        ax.scatter(*point,s=28,c='#ce4038',zorder=5)
        if r['track_node_id']!='':
            anchor=(r['track_longitude'],r['track_latitude'])
            ax.plot([point[0],anchor[0]],[point[1],anchor[1]],'--',color='#f2a13a',lw=1)
    ax.autoscale(); label_cities(ax,sx); decorate(ax,'底层铁路实际线形与代表车站检查图')
    ax.text(0,-.06,'橙色虚线仅表示车站定位与轨道节点的匹配偏移，不是新增铁路边。',transform=ax.transAxes,fontsize=9)
    finish(fig,out/'railway_station_check')
    # Detailed 34-panel checks expose wrong-track snaps hidden in the national view.
    fig,axes=plt.subplots(7,5,figsize=(20,25))
    for ax,r in zip(axes.flat,stations):
        ax.set_title(f"{r['order']:02d} {r['city']} | {r['requested_station'] or '无重铁代表站'}",fontsize=9)
        if r['station_longitude']=='':
            ax.text(.1,.5,r['match_status'],transform=ax.transAxes,fontsize=7); ax.set_axis_off(); continue
        lon,lat=float(r['station_longitude']),float(r['station_latitude'])
        local=nearby(lon-.025,lat-.018,lon+.025,lat+.018)
        ax.add_collection(LineCollection(local,colors='#567b90',linewidths=.7))
        ax.scatter(lon,lat,c='#d1392d',s=30,label='车站定位')
        if r['track_node_id']!='':
            x,y=r['track_longitude'],r['track_latitude']; ax.scatter(x,y,c='#eab72c',s=22,label='轨道节点')
            ax.plot([lon,x],[lat,y],'--',color='#c7982d',lw=.8)
        ax.set_xlim(lon-.025,lon+.025); ax.set_ylim(lat-.018,lat+.018)
        ax.tick_params(labelsize=6); ax.grid(alpha=.2)
        ax.text(.02,.01,f"{r['match_method']}\n偏移 {r['match_distance_m'] or '未匹配'} m",transform=ax.transAxes,fontsize=6,
                bbox={'facecolor':'white','alpha':.8,'edgecolor':'none'})
    axes.flat[-1].set_axis_off(); fig.tight_layout()
    finish(fig,out/'station_checks_detail')
    if route_path:
        fig,ax=plt.subplots(figsize=(14,11))
        points=np.asarray(graph.path_points(route_path))
        xmin,ymin=points.min(axis=0)-1; xmax,ymax=points.max(axis=0)+1
        local=nearby(xmin,ymin,xmax,ymax)
        ax.add_collection(LineCollection(local,colors='#aab8bf',linewidths=.4,alpha=.5))
        ax.plot(points[:,0],points[:,1],c='#d22e34',lw=2,zorder=4)
        labels={r['city']:(r['track_longitude'],r['track_latitude']) for r in stations
                if r['city'] in quality['guangzhou_lanzhou']['selected_city_sequence']}
        for point in labels.values(): ax.scatter(*point,s=48,c='#d22e34',edgecolors='white',zorder=6)
        label_cities(ax,labels,fontsize=11); ax.set_xlim(xmin,xmax); ax.set_ylim(ymin,ymax)
        decorate(ax,f"广州站 → 兰州站：最短几何铁路路径 {quality['guangzhou_lanzhou']['total_km']:.3f} km")
        ax.text(0,-.065,'无向基础设施最短路径；忽略方向、运营与时刻表，不等于可乘坐列车行程。',transform=ax.transAxes,fontsize=9)
        finish(fig,out/'guangzhou_lanzhou_route')
    else:
        for suffix in ['.png','.svg']:
            stale=out/('guangzhou_lanzhou_route'+suffix)
            if stale.exists(): stale.unlink()
