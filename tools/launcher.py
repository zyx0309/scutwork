"""Stream subprocess output to the console AND a UTF-8 log; no shell quoting."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

def backup_outputs(root=ROOT):
    """Rename prior outputs on the same disk; leave PBFs, caches and venv untouched."""
    root=Path(root); outputs=root/'outputs'
    if not outputs.exists(): return None
    backups=root/'backups'; backups.mkdir(exist_ok=True)
    target=backups/f'outputs_{datetime.now():%Y%m%d_%H%M%S_%f}'
    outputs.rename(target)
    return target

def execute(command,log,environment):
    print('执行：'+' '.join(str(s) for s in command),flush=True)
    process=subprocess.Popen(command,cwd=ROOT,env=environment,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                             text=True,encoding='utf-8',errors='replace',bufsize=1)
    for line in process.stdout:
        log.write(line); log.flush()
        try:
            print(line,end='',flush=True)
        except UnicodeEncodeError:
            sys.stdout.buffer.write(line.encode(sys.stdout.encoding or 'utf-8',errors='replace'))
            sys.stdout.buffer.flush()
    return process.wait()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--install',action='store_true')
    parser.add_argument('--test',action='store_true')
    parser.add_argument('--diagnose-stations',action='store_true')
    parser.add_argument('--backup-outputs',action='store_true',help='Move previous outputs to backups before the default local rerun')
    args,remaining=parser.parse_known_args()
    if args.diagnose_stations and (args.install or args.test or args.backup_outputs or remaining):
        parser.error('--diagnose-stations cannot be combined with processing or installation options')
    if args.backup_outputs and (args.install or args.test or any(a.split('=',1)[0]=='--output-dir' for a in remaining)):
        parser.error('--backup-outputs is for the default processing output directory only')
    logs=ROOT/'logs'; logs.mkdir(exist_ok=True)
    log_path=logs/f"{'install' if args.install else 'tests' if args.test else 'diagnostics' if args.diagnose_stations else 'run'}_{datetime.now():%Y%m%d_%H%M%S}.log"
    environment=os.environ.copy()
    environment.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1')
    try:
        with log_path.open('w',encoding='utf-8') as log:
            log.write(f'Project root: {ROOT}\nPython: {sys.version}\n')
            print(f'项目目录：{ROOT}\n运行日志：{log_path}',flush=True)
            if args.backup_outputs:
                backup=backup_outputs()
                if backup:
                    message=f'旧成果已移动备份至：{backup}；data、缓存与虚拟环境保留。'
                    print(message,flush=True); log.write(message+'\n'); log.flush()
            if args.install:
                commands=[[sys.executable,'-m','pip','install','--disable-pip-version-check','-r',str(ROOT/'requirements.txt')],
                          [sys.executable,'-m','pip','check']]
            elif args.test:
                commands=[[sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v']]
            elif args.diagnose_stations:
                commands=[[sys.executable,'-u',str(ROOT/'tools/station_diagnostics.py')]]
            else:
                commands=[[sys.executable,'-u',str(ROOT/'src/run.py'),*remaining]]
            for command in commands:
                code=execute(command,log,environment)
                if code:
                    print(f'\n命令失败（退出码 {code}）；日志：{log_path}',flush=True)
                    return code
        print(f'\n已完成。日志：{log_path}',flush=True); return 0
    except Exception:
        import traceback
        error=traceback.format_exc()
        with log_path.open('a',encoding='utf-8') as log: log.write(error)
        print(error,file=sys.stderr); print(f'错误已保存：{log_path}',flush=True); return 1

if __name__=='__main__':
    raise SystemExit(main())
