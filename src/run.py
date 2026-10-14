"""Cross-platform command-line entry point; local PBF processing is the default."""
import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime
from railway.config import ROOT,RAW,CACHE,OUT

def main():
    p=argparse.ArgumentParser(description='真实 OSM 铁路几何网络分析（默认只读本地PBF，不联网）')
    p.add_argument('--download',action='store_true',help='Explicitly download missing PBFs over HTTPS; not needed for local files')
    p.add_argument('--with-guangdong',action='store_true',help='Also use data/raw/guangdong-latest.osm.pbf')
    p.add_argument('--raw-dir',type=Path,default=RAW)
    p.add_argument('--cache-dir',type=Path,default=CACHE)
    p.add_argument('--output-dir',type=Path,default=OUT)
    p.add_argument('--no-plots',action='store_true',help='Only for troubleshooting; normal delivery requires plots')
    p.add_argument('--test-fixture',action='store_true',help=argparse.SUPPRESS)
    args=p.parse_args()
    logs=ROOT/'logs'; logs.mkdir(exist_ok=True)
    error_log=logs/f"errors_{datetime.now():%Y%m%d_%H%M%S}.log"
    logging.basicConfig(filename=error_log,level=logging.ERROR,encoding='utf-8',
                        format='%(asctime)s %(levelname)s %(message)s')
    try:
        if args.download:
            if args.raw_dir.resolve()!=RAW.resolve():
                raise ValueError('--download only supports the default data/raw directory')
            from railway.download import download
            download(['china','taiwan']+(['guangdong'] if args.with_guangdong else []))
        from railway.pipeline import run
        run(args.raw_dir,args.cache_dir,args.output_dir,args.with_guangdong,not args.no_plots,test_fixture=args.test_fixture)
        from railway.packaging import package_project
        archive=package_project(ROOT,args.output_dir/'submission/OSM_Railway_Results.zip')
        print(f'成果 ZIP（不含原始 PBF）：{archive}',flush=True)
        return 0
    except Exception as e:
        logging.exception('OSM processing failed')
        from railway.common import save_json,now
        save_json(args.output_dir/'run_status.json',{'status':'failed','at':now(),'error':str(e),'error_log':str(error_log),
                                                   'note':'Any older outputs belong to prior runs; this run is not complete'})
        print(f'\n处理失败：{e}\n完整错误日志：{error_log}\n本次未完成，请先查看日志，不要将旧文件当作本次成果。',file=sys.stderr,flush=True)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
