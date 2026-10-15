"""Build a small overlay update with no raw data, outputs, caches or venv."""
import hashlib
import argparse
from pathlib import Path
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--mode-fix',action='store_true');args=parser.parse_args()
    files=[]
    for directory in ('src','tools','tests'):
        files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file()
                     and '__pycache__' not in p.parts and (p.suffix=='.py' or ('fixtures' in p.parts and p.suffix=='.json')))
    files.extend(ROOT/name for name in (
        '.gitignore','README.md','WINDOWS_GUIDE.md','STATION_FIX_GUIDE.md',
        'requirements.txt','LICENSE','DATA_LICENSE.md','install.bat','install_windows.bat',
        'run.bat','run_windows.bat','run_fixed.bat','test_windows.bat','开始使用.txt'))
    if args.mode_fix:
        files.extend(ROOT/name for name in ('STATION_MODE_FIX_GUIDE.md','STATION_DIAGNOSTICS_GUIDE.md','run_mode_fixed.bat','diagnose_stations.bat'))
    label='Station_Mode_Fix' if args.mode_fix else 'Station_Matching_Fix'
    target=ROOT/'updates'/f'{label}.zip'; target.parent.mkdir(exist_ok=True)
    files=sorted(set(files))
    for p in files:
        if not p.is_file(): raise FileNotFoundError(p)
        if p.relative_to(ROOT).parts[0] in ('data','outputs','backups','.venv','report'):
            raise ValueError('Unexpected update member')
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(ROOT).as_posix()+'\n' for p in files)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for p in files: archive.write(p,label+'/'+p.relative_to(ROOT).as_posix())
        archive.writestr(label+'/UPDATE_CONTENTS.sha256',manifest)
    with zipfile.ZipFile(target) as archive:
        if archive.testzip() is not None: raise ValueError('ZIP CRC check failed')
        for p in files:
            if archive.read(label+'/'+p.relative_to(ROOT).as_posix())!=p.read_bytes():
                raise ValueError('ZIP bytes differ from source')
    target.with_suffix('.zip.sha256').write_text(hashlib.sha256(target.read_bytes()).hexdigest()+'  '+target.name+'\n',encoding='utf-8')
    print(f'Update archive validated: {len(files)} files, {target.stat().st_size:,} bytes; no PBF, venv, cache, report or outputs.')

if __name__=='__main__': main()
