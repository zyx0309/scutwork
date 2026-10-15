"""Bundle the report, unchanged uploaded tables and runnable source; never bundle PBFs."""
import hashlib
import argparse
import json
import zipfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
INPUT_NAMES = (
    'cities.csv', 'city_stations.csv', 'city_edges.csv', 'data_quality.json',
    'RESULTS.md', 'run_status.json', 'guangzhou_lanzhou_status.json',
    'guangzhou_lanzhou_segments.csv',
)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--report-root',type=Path,default=ROOT)
    args=parser.parse_args();document_root=args.report_root.resolve()
    document_root.relative_to(PROJECT)
    inputs = document_root / 'input'
    quality = json.loads((inputs / 'data_quality.json').read_text(encoding='utf-8-sig'))
    state=json.loads((inputs/'run_status.json').read_text(encoding='utf-8-sig'))
    diagnosed=(inputs/'station_diagnostics.json').is_file()
    input_files=sorted(p for p in inputs.rglob('*') if p.is_file())
    now = datetime.now(timezone.utc)
    manifest = {
        'generated_at_utc': now.isoformat(),
        'generated_at_beijing': now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        'analysis_code_commit': 'a27a4e833922ef6dd0f138316452ac92c9daffe5' if diagnosed else 'd3a115234a288b57fd46955fb758a882a261f723',
        'result_graph_version':state.get('graph_version'),'result_station_identity_version':state.get('station_identity_version'),
        'bundled_mode_fix_requires_national_rerun':diagnosed,
        'repository': 'https://github.com/zyx0309/scutwork',
        'uploaded_result_files_independently_hashed_here': {
            p.relative_to(inputs).as_posix(): {'bytes': p.stat().st_size, 'sha256': sha256(p)} for p in input_files
        },
        'original_pbf_provenance_copied_from_user_run_not_rehashed_here':
            quality['data_extraction']['sources'],
        'independent_verification_scope': 'Exported city graph and segment tables only; no national PBF or full track geometry reread.',
        'known_confirmed_issue': ('Fuzhou selected stop 9521844144 has subway=yes; train station 6999105218 is a distinct object. Wrong-mode anchor rejected in derived audit, original input retained.' if diagnosed else 'Fuzhou city is misidentified as Fuzhou/浮洲 station in Taiwan. Rejected only in the derived audit; original input bytes retained.'),
        'national_run_repeated_after_fix': False,
        'national_run_after_initial_name_fix':diagnosed,
        'national_run_after_latest_mode_fix':False,
        'full_track_geometry_received_here': False,
        'actual_route_png_received':diagnosed,
        'map_attribution': '© OpenStreetMap contributors / ODbL 1.0',
        'font': {
            'name': 'Noto Sans SC', 'license': 'SIL Open Font License 1.1',
            'source_url': 'https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/Variable/TTF/Subset/NotoSansSC-VF.ttf',
            'download_sha256': 'd68bafcb48a2707749396aa12bbbd833cb70401f3a9a689fd2902c7e0d295964',
            'full_font_files_bundled': False, 'subset_embedded_in_pdf': True,
        },
    }
    (document_root / 'SOURCE_MANIFEST.json').write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    files = []
    for folder in ('src', 'tests', 'tools'):
        files.extend(p for p in (PROJECT / folder).rglob('*')
                     if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc')
    project_files = (
        '.gitignore', 'README.md', 'WINDOWS_GUIDE.md', '开始使用.txt', 'requirements.txt',
        'DATA_LICENSE.md', 'LICENSE', 'install.bat', 'run.bat',
        'install_windows.bat', 'run_windows.bat', 'test_windows.bat', 'data/raw/README.txt',
        'outputs/CLOUD_VALIDATION.md', 'outputs/cloud_validation.json', 'outputs/run_status.json',
    )
    files.extend(PROJECT / name for name in project_files)
    if diagnosed:
        files=[p for p in files if p.relative_to(PROJECT).parts[0]!='outputs']
        files.extend(PROJECT/name for name in ('STATION_MODE_FIX_GUIDE.md','STATION_DIAGNOSTICS_GUIDE.md',
                    'STATION_FIX_GUIDE.md','run_fixed.bat','run_mode_fixed.bat','diagnose_stations.bat'))
    report_files = (
        '.gitignore', 'README.md', 'requirements.txt', 'verify_results.py',
        'build_report.py', 'package_submission.py', 'SOURCE_MANIFEST.json',
        'independent_audit.json', 'audited_city_stations.csv', 'mst_display_edges.csv',
        'fonts/OFL.txt', 'deliverables/AI_Railway_Report_Audited.docx',
        'deliverables/AI_Railway_Report_Audited.pdf', 'deliverables/AI_Railway_Report_Audited.md',
    )
    if diagnosed:
        files.extend(ROOT/name for name in ('README.md','.gitignore','requirements.txt','verify_results.py',
                     'build_report.py','package_submission.py','fonts/OFL.txt'))
        files.extend(document_root/name for name in ('README.md','SOURCE_MANIFEST.json','independent_audit.json',
                     'audited_city_stations.csv','mst_display_edges.csv','deliverables/AI_Railway_Report_Audited.docx',
                     'deliverables/AI_Railway_Report_Audited.pdf','deliverables/AI_Railway_Report_Audited.md'))
    else:
        files.extend(ROOT / name for name in report_files)
    files.extend(input_files)
    files.extend(p for p in (document_root / 'figures').iterdir() if p.suffix in ('.png', '.svg'))
    files = sorted(set(files))
    if any(not p.is_file() for p in files):
        raise FileNotFoundError([str(p) for p in files if not p.is_file()])
    for p in files:
        relative = p.relative_to(PROJECT)
        if any(part in ('.git', '.venv', '.cache', 'logs', '__pycache__') for part in relative.parts):
            raise ValueError(f'Forbidden archive member: {relative}')
        if p.suffix in ('.pbf', '.pkl', '.sqlite', '.ttf', '.pyc', '.zip'):
            raise ValueError(f'Forbidden archive type: {relative}')
    target = document_root / 'deliverables/AI_Railway_Submission.zip'
    temporary = target.with_suffix('.zip.tmp')
    content_manifest = document_root / 'deliverables/SUBMISSION_CONTENTS.sha256'
    content_manifest.write_text(''.join(
        f'{sha256(p)}  {p.relative_to(PROJECT).as_posix()}\n' for p in files), encoding='utf-8')
    with zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for p in files + [content_manifest]:
            archive.write(p, 'OSM_Railway_Project/' + p.relative_to(PROJECT).as_posix())
        for directory in ('data/raw/', 'data/cache/', 'logs/', 'outputs/figures/', 'outputs/submission/'):
            archive.writestr('OSM_Railway_Project/' + directory, b'')
    with zipfile.ZipFile(temporary) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC check failed')
        for p in files:
            archived = archive.read('OSM_Railway_Project/' + p.relative_to(PROJECT).as_posix())
            if hashlib.sha256(archived).hexdigest() != sha256(p):
                raise ValueError(f'Archived contents differ: {p.name}')
    temporary.replace(target)
    target.with_suffix('.zip.sha256').write_text(f'{sha256(target)}  {target.name}\n', encoding='utf-8')
    print(f'Submission ZIP validated: {len(files)} source/data/report files, {target.stat().st_size:,} bytes')


if __name__ == '__main__':
    main()
