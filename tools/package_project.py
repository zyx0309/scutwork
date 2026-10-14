import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from railway.packaging import package_project

if __name__=='__main__':
    print(package_project(ROOT,ROOT/'outputs/submission/OSM_Railway_Project_Windows.zip'))
