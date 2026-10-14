import csv
import hashlib
import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

def now():
    return datetime.now(timezone.utc).isoformat()

def save_json(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp')
    with tmp.open('w',encoding='utf-8') as f:
        json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
    tmp.replace(path)

def save_csv(path, rows, fields):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(rows)

def sha256(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''): h.update(chunk)
    return h.hexdigest()

@contextmanager
def native_osmium_filename(path):
    """Use an ASCII basename for C++ I/O even if the containing Windows path is Chinese.

    This application reads files sequentially. Python changes the working directory
    using native Unicode APIs; libosmium then opens the fixed ASCII PBF basename.
    Always restore the directory, including when parsing fails.
    """
    path=Path(path).resolve(); previous=Path.cwd()
    os.chdir(path.parent)
    try:
        yield path.name
    finally:
        os.chdir(previous)
