from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'data/raw'
CACHE = ROOT / 'data/cache'
OUT = ROOT / 'outputs'
SOURCES = {
    'china': 'https://download.geofabrik.de/asia/china-latest.osm.pbf',
    'taiwan': 'https://download.geofabrik.de/asia/taiwan-latest.osm.pbf',
    'guangdong': 'https://download.geofabrik.de/asia/china/guangdong-latest.osm.pbf',
}
# Labels only: geographical layout coordinates must come from actual OSM nodes.
CITY_SPECS = [
 ('北京','北京市',['北京站','Beijing Railway Station']),
 ('天津','天津市',['天津站','Tianjin Railway Station']),
 ('上海','上海市',['上海站','Shanghai Railway Station']),
 ('重庆','重庆市',['重庆北站','Chongqing North Railway Station']),
 ('石家庄','河北省',['石家庄站','Shijiazhuang Railway Station']),
 ('太原','山西省',['太原站','Taiyuan Railway Station']),
 ('呼和浩特','内蒙古自治区',['呼和浩特站','Hohhot Railway Station']),
 ('沈阳','辽宁省',['沈阳站','Shenyang Railway Station']),
 ('长春','吉林省',['长春站','Changchun Railway Station']),
 ('哈尔滨','黑龙江省',['哈尔滨站','Harbin Railway Station']),
 ('南京','江苏省',['南京站','Nanjing Railway Station']),
 ('杭州','浙江省',['杭州站','Hangzhou Railway Station']),
 ('合肥','安徽省',['合肥站','Hefei Railway Station']),
 ('福州','福建省',['福州站','Fuzhou Railway Station']),
 ('南昌','江西省',['南昌站','Nanchang Railway Station']),
 ('济南','山东省',['济南站','Jinan Railway Station']),
 ('郑州','河南省',['郑州站','Zhengzhou Railway Station']),
 ('武汉','湖北省',['武汉站','Wuhan Railway Station']),
 ('长沙','湖南省',['长沙站','Changsha Railway Station']),
 ('广州','广东省',['广州站','Guangzhou Railway Station']),
 ('南宁','广西壮族自治区',['南宁站','Nanning Railway Station']),
 ('海口','海南省',['海口站','Haikou Railway Station']),
 ('成都','四川省',['成都东站','Chengdu East Railway Station']),
 ('贵阳','贵州省',['贵阳站','Guiyang Railway Station']),
 ('昆明','云南省',['昆明站','Kunming Railway Station']),
 ('拉萨','西藏自治区',['拉萨站','Lhasa Railway Station']),
 ('西安','陕西省',['西安站','Xi’an Railway Station',"Xi'an Railway Station"]),
 ('兰州','甘肃省',['兰州站','Lanzhou Railway Station']),
 ('西宁','青海省',['西宁站','Xining Railway Station']),
 ('银川','宁夏回族自治区',['银川站','Yinchuan Railway Station']),
 ('乌鲁木齐','新疆维吾尔自治区',['乌鲁木齐站','Urumqi Railway Station']),
 ('台北','台湾省',['臺北車站','台北車站','台北车站','Taipei Main Station']),
 ('香港','香港特别行政区',['香港西九龍站','香港西九龙站','香港西九龍','Hong Kong West Kowloon']),
 ('澳门','澳门特别行政区',[]),
]
CITY_ORDER = [r[0] for r in CITY_SPECS]
CITY_ENGLISH = ['Beijing','Tianjin','Shanghai','Chongqing','Shijiazhuang','Taiyuan','Hohhot',
 'Shenyang','Changchun','Harbin','Nanjing','Hangzhou','Hefei','Fuzhou','Nanchang','Jinan',
 'Zhengzhou','Wuhan','Changsha','Guangzhou','Nanning','Haikou','Chengdu','Guiyang','Kunming',
 'Lhasa',"Xi'an",'Lanzhou','Xining','Yinchuan','Urumqi','Taipei','Hong Kong','Macau']
ATTRIBUTION = '© OpenStreetMap contributors; ODbL 1.0; https://www.openstreetmap.org/copyright'
DISTANCE_LABEL = '基于 OSM 铁路线形计算的几何里程（km）'
SNAP_METERS = 150.0
