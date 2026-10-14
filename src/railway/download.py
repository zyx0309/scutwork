"""Resumable HTTPS download with upstream MD5 and real PBF validation."""
import json
import hashlib
import struct
import subprocess
from pathlib import Path
import osmium
from .config import RAW, SOURCES
from .common import now, save_json, sha256,native_osmium_filename

def validate_header(path):
    with Path(path).open('rb') as f:
        first=f.read(4)
        if len(first)!=4 or not (0 < struct.unpack('>I',first)[0] <= 65536):
            raise ValueError('Invalid PBF BlobHeader length (possibly HTML or incomplete download)')
    with native_osmium_filename(path) as filename,osmium.io.Reader(filename) as reader:
        header=reader.header()
        boxes=[]
        b=header.box()
        if b.valid():
            boxes.append([b.bottom_left.lon,b.bottom_left.lat,b.top_right.lon,b.top_right.lat])
        return {'generator':header.get('generator'),
                'replication_timestamp':header.get('osmosis_replication_timestamp'),
                'header_bounds':boxes}

def download(regions=('china','taiwan')):
    RAW.mkdir(parents=True,exist_ok=True)
    manifest_path=RAW/'sources.json'
    manifest=json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    failures=[]
    for region in regions:
        url=SOURCES[region]; target=RAW/f'{region}-latest.osm.pbf'
        known=manifest.get(region,{})
        if target.exists():
            try:
                header=validate_header(target)
                checksum=sha256(target)
                if known.get('sha256') and checksum!=known['sha256']:
                    raise ValueError('Local PBF differs from recorded checksum; move sources.json aside only after investigation')
                manifest[region]={**known,'source_url':url,'size':target.stat().st_size,
                                  'sha256':checksum,'verified_header':True,**header}
                if not known:
                    manifest[region].update(origin='user_supplied_local',registered_at=now(),
                                            upstream_checksum_status='not_checked_offline')
                save_json(manifest_path,manifest)
                print(f'Using local PBF (no network): {target}; full parsing occurs during extraction',flush=True)
                continue
            except Exception as e:
                failures.append({'region':region,'url':url,'error':f'Existing file rejected: {e}'})
                continue
        partial=target.with_suffix(target.suffix+'.part')
        if target.exists() and not partial.exists():
            # Do not overwrite an existing unknown file. Verify it against upstream first.
            candidate=target
        else:
            candidate=partial
            cmd=['curl','-fL','--retry','3','--retry-delay','2','--connect-timeout','25',
                 '--max-time','7200','-C','-','-o',str(partial),url]
            print(f'Downloading {url} (resume supported)',flush=True)
            p=subprocess.run(cmd,capture_output=True,text=True)
            if p.returncode:
                failures.append({'region':region,'url':url,'exit_code':p.returncode,'error':p.stderr[-3000:]})
                continue
        try:
            p=subprocess.run(['curl','-fL','--retry','3','--connect-timeout','25','--max-time','90',url+'.md5'],
                             capture_output=True,text=True,check=True)
            expected=p.stdout.strip().split()[0].lower()
            if len(expected)!=32 or any(c not in '0123456789abcdef' for c in expected):
                raise ValueError('Invalid upstream MD5 sidecar')
            h=hashlib.md5()
            with candidate.open('rb') as f:
                for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
            if h.hexdigest()!=expected:
                raise ValueError('Upstream MD5 mismatch; file retained, not accepted. Check latest-file rotation.')
            header=validate_header(candidate)
            if candidate!=target: candidate.replace(target)
            manifest[region]={'source_url':url,'downloaded_at':now(),'size':target.stat().st_size,
                              'upstream_md5':expected,'sha256':sha256(target),'verified':True,**header}
            save_json(manifest_path,manifest)
            print(f'Verified PBF: {region}, {target.stat().st_size} bytes',flush=True)
        except Exception as e:
            failures.append({'region':region,'url':url,'error':str(e)})
    save_json(RAW/'download_status.json',{'checked_at':now(),'sources':manifest,'failures':failures})
    if failures:
        raise RuntimeError('PBF download/verification failed; see data/raw/download_status.json')
    return manifest
