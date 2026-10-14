"""Stream subprocess output to the console AND a UTF-8 log; no shell quoting."""
import argparse
from datetime import datetime
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]

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
    args,remaining=parser.parse_known_args()
    logs=ROOT/'logs'; logs.mkdir(exist_ok=True)
    log_path=logs/f"{'install' if args.install else 'tests' if args.test else 'run'}_{datetime.now():%Y%m%d_%H%M%S}.log"
    environment=os.environ.copy()
    environment.update(PYTHONUTF8='1',PYTHONIOENCODING='utf-8',PYTHONUNBUFFERED='1')
    try:
        with log_path.open('w',encoding='utf-8') as log:
            log.write(f'Project root: {ROOT}\nPython: {sys.version}\n')
            print(f'项目目录：{ROOT}\n运行日志：{log_path}',flush=True)
            if args.install:
                commands=[[sys.executable,'-m','pip','install','--disable-pip-version-check','-r',str(ROOT/'requirements.txt')],
                          [sys.executable,'-m','pip','check']]
            elif args.test:
                commands=[[sys.executable,'-m','unittest','discover','-s',str(ROOT/'tests'),'-v']]
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
