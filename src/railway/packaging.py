"""Distribute source and results without raw PBFs, caches, venvs or credentials."""
import zipfile
from pathlib import Path

def package_project(root,target,include_outputs=True):
    root=Path(root).resolve(); target=Path(target).resolve(); target.parent.mkdir(parents=True,exist_ok=True)
    included=[]
    dirs=['src','tests','tools']+(['outputs'] if include_outputs else [])
    files=['README.md','WINDOWS_GUIDE.md','STATION_FIX_GUIDE.md','STATION_DIAGNOSTICS_GUIDE.md','diagnose_stations.bat','开始使用.txt','requirements.txt','install.bat','run.bat','run_fixed.bat','install_windows.bat','run_windows.bat',
           'test_windows.bat','DATA_LICENSE.md','LICENSE','data/raw/README.txt','.gitignore']
    for directory in dirs:
        for p in (root/directory).rglob('*'):
            if not p.is_file(): continue
            relative=p.relative_to(root)
            if '__pycache__' in relative.parts or 'submission' in relative.parts or p.suffix in {'.pyc','.pbf','.zip'}:
                continue
            included.append(p)
    included.extend(root/p for p in files if (root/p).is_file())
    # Tiny provenance manifests may be delivered; large raw map objects never are.
    if include_outputs and (root/'outputs/run_status.json').exists():
        provenance=root/'data/raw/sources.json'
        if provenance.exists(): included.append(provenance)
    temporary=target.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in sorted(set(included)):
            archive.write(p,'OSM_Railway_Project/'+p.relative_to(root).as_posix())
        for directory in ['data/raw/','data/cache/','outputs/figures/','outputs/submission/','logs/']:
            archive.writestr('OSM_Railway_Project/'+directory,b'')
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None: raise ValueError('ZIP integrity check failed')
        if any(n.endswith('.pbf') for n in archive.namelist()): raise ValueError('Raw PBF accidentally included')
    temporary.replace(target)
    return target
