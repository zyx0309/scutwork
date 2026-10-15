"""Two-pass streaming extraction. Only the relevant OSM subset enters SQLite."""
import collections
import json
import sqlite3
import unicodedata
from pathlib import Path
import osmium
from .common import now, save_json,native_osmium_filename
from .config import CITY_ORDER, CITY_ENGLISH

EXTRACT_VERSION=3

def normalized(s):
    text=unicodedata.normalize('NFKC',s).casefold().strip()
    for a,b in [('臺','台'),('車','车'),('龍','龙'),('烏','乌'),('魯','鲁'),('齊','齐'),('門','门')]:
        text=text.replace(a,b)
    return ''.join(c for c in text if c.isalnum())

def tag_names(tags):
    names=[]
    for k in ['name','name:zh','name:zh-Hans','name:zh-Hant','name:en','official_name','alt_name','short_name']:
        names.extend(tags.get(k,'').split(';'))
    return {normalized(s) for s in names if s}

def excluded_transport_mode(tags):
    """Explicit modes only: names such as 'airport railway' do not decide the mode."""
    if tags.get('station') in {'subway','light_rail','monorail','tram','funicular'}:
        return tags['station']
    for mode in ('subway','light_rail','monorail','tram','funicular'):
        if tags.get(mode)=='yes': return mode
    if tags.get('railway') in {'subway','light_rail','monorail','tram','tram_stop','funicular','subway_entrance'}:
        return tags['railway']
    return ''

def classify(tags):
    if tags.get('railway')!='rail': return 'exclude','not_rail'
    if excluded_transport_mode(tags): return 'exclude','explicit_non_heavy_rail_mode'
    if any(tags.get(k) in {'yes','rail'} for k in ['abandoned','disused','construction','proposed']):
        return 'exclude','inactive'
    if tags.get('usage') in {'industrial','military','test'}:
        return 'exclude','industrial_military_test'
    if tags.get('access') in {'no','private','military'}:
        return 'exclude','restricted_access'
    if tags.get('railway:traffic_mode')=='freight' or tags.get('passenger')=='no' or tags.get('usage')=='freight':
        return 'exclude','explicit_freight_only'
    service=tags.get('service','')
    if service in {'yard','siding','spur','crossover'}:
        return 'access_only',f'station_service_{service}'
    if service and service!='main':
        return 'exclude',f'unsupported_service_{service}'
    return 'main','usage_unknown' if not tags.get('usage') else f"usage_{tags['usage']}"

def connect(path):
    db=sqlite3.connect(path)
    db.execute('PRAGMA journal_mode=WAL'); db.execute('PRAGMA synchronous=NORMAL')
    db.execute('CREATE TABLE IF NOT EXISTS objects (type TEXT, id INTEGER, version INTEGER, source TEXT, data TEXT, PRIMARY KEY(type,id))')
    return db

class Store:
    def __init__(self,db):
        self.db=db; self.count=0; self.duplicates=collections.Counter(); self.conflicts=collections.Counter()

    def add(self,t,ident,version,source,data):
        payload=json.dumps(data,ensure_ascii=False,separators=(',',':'))
        row=self.db.execute('SELECT version,source,data FROM objects WHERE type=? AND id=?',(t,ident)).fetchone()
        if row:
            self.duplicates[t]+=1
            if row[2]!=payload or row[0]!=version: self.conflicts[t]+=1
            sources=sorted(set(row[1].split('|')+[source]))
            if version < row[0]:
                self.db.execute('UPDATE objects SET source=? WHERE type=? AND id=?',('|'.join(sources),t,ident))
                return
            source='|'.join(sources)
        self.db.execute('INSERT OR REPLACE INTO objects VALUES (?,?,?,?,?)',(t,ident,version,source,payload))
        self.count+=1
        if self.count%10000==0: self.db.commit()

class WaysRelations(osmium.SimpleHandler):
    def __init__(self,store,source,needed):
        super().__init__(); self.store=store; self.source=source; self.needed=needed; self.stats=collections.Counter()

    def way(self,w):
        tags=dict(w.tags); railway=tags.get('railway','')
        if railway not in {'rail','station','halt','platform'}: return
        refs=[n.ref for n in w.nodes]
        self.stats[f'way_{railway}']+=1
        if sum(v for k,v in self.stats.items() if k.startswith('way_'))%10000==0:
            print(f'{self.source}: retained {sum(v for k,v in self.stats.items() if k.startswith("way_")):,} railway/station ways',flush=True)
        self.needed.update(refs)
        self.store.add('w',w.id,w.version,self.source,{'tags':tags,'refs':refs})

    def relation(self,r):
        tags=dict(r.tags)
        if tags.get('public_transport') not in {'stop_area','stop_area_group'} and tags.get('route') not in {'train','railway'} and tags.get('railway')!='station':
            return
        self.store.add('r',r.id,r.version,self.source,{'tags':tags,'members':[(m.type,m.ref,m.role) for m in r.members]})
        self.stats['relevant_relations']+=1

class Nodes(osmium.SimpleHandler):
    def __init__(self,store,source,needed):
        super().__init__(); self.store=store; self.source=source; self.needed=needed
        self.count=0; self.bounds=[180.,90.,-180.,-90.]; self.place_count=0
        self.city_names={normalized(c) for c in CITY_ORDER+CITY_ENGLISH+[c+'市' for c in CITY_ORDER]}

    def node(self,n):
        self.count+=1
        if not n.location.valid(): return
        lon,lat=n.location.lon,n.location.lat
        self.bounds=[min(self.bounds[0],lon),min(self.bounds[1],lat),max(self.bounds[2],lon),max(self.bounds[3],lat)]
        tags=dict(n.tags)
        is_station=tags.get('railway') in {'station','halt','stop'} or (tags.get('public_transport')=='stop_position' and tags.get('train')=='yes')
        is_city=tags.get('place') in {'city','town'} and bool(self.city_names & tag_names(tags))
        if n.id in self.needed or is_station or is_city:
            self.store.add('n',n.id,n.version,self.source,{'lon':lon,'lat':lat,'tags':tags})
            if is_city: self.place_count+=1
        if self.count%1000000==0: print(f'{self.source}: streamed {self.count:,} nodes',flush=True)

def load_objects(db,t):
    for ident,version,source,data in db.execute('SELECT id,version,source,data FROM objects WHERE type=?',(t,)):
        yield ident,version,source,json.loads(data)

def extract(paths,cache_dir,source_manifest):
    cache_dir=Path(cache_dir); cache_dir.mkdir(parents=True,exist_ok=True)
    fingerprint={'extract_version':EXTRACT_VERSION,'inputs':{
        p.name:{'sha256':source_manifest[p.name.split('-')[0]]['sha256']} for p in paths}}
    meta_path=cache_dir/'extraction.json'; dest=cache_dir/'rail_subset.sqlite'
    if meta_path.exists() and dest.exists():
        metadata=json.loads(meta_path.read_text())
        if metadata.get('fingerprint')==fingerprint and metadata.get('parse_completed'):
            print('Using cached railway subset',flush=True); return dest,metadata
    temporary=cache_dir/'rail_subset.build.sqlite'
    for p in [temporary,Path(str(temporary)+'-wal'),Path(str(temporary)+'-shm')]:
        if p.exists(): p.unlink()
    db=connect(temporary); store=Store(db); needed=set(); file_stats={}
    try:
        for p in paths:
            print(f'Pass 1 ways/relations: {p.name}',flush=True)
            handler=WaysRelations(store,p.name,needed)
            with native_osmium_filename(p) as filename: handler.apply_file(filename)
            db.commit()
            file_stats[p.name]={'retained_way_relation_counts':dict(handler.stats)}
        for p in paths:
            print(f'Pass 2 coordinates/stations: {p.name}',flush=True)
            handler=Nodes(store,p.name,needed)
            with native_osmium_filename(p) as filename: handler.apply_file(filename)
            db.commit()
            file_stats[p.name].update(all_node_count=handler.count,actual_node_bounds=handler.bounds,
                                      matched_place_nodes=handler.place_count)
        metadata={'fingerprint':fingerprint,'parse_completed':True,'completed_at':now(),
                  'files':file_stats,'relevant_duplicate_objects':dict(store.duplicates),
                  'version_or_content_conflicts':dict(store.conflicts),
                  'deduplication':'OSM type + ID; highest version retained; identical-version conflicts logged; no spatial joining',
                  'sources':source_manifest,'required_rail_or_station_node_refs':len(needed)}
        db.execute('PRAGMA wal_checkpoint(TRUNCATE)'); db.close(); temporary.replace(dest)
        save_json(meta_path,metadata); return dest,metadata
    except Exception:
        db.close(); raise
