"""Filesystem backup behavior; Windows CMD itself is not available in cloud tests."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.launcher import backup_outputs


class OutputBackupTests(unittest.TestCase):
    def test_backup_preserves_outputs_and_leaves_inputs_and_cache(self):
        with tempfile.TemporaryDirectory(prefix='修正 测试 ') as directory:
            root=Path(directory)
            for filename,content in [('outputs/city_stations.csv',b'original result'),
                                     ('data/raw/china-latest.osm.pbf',b'not-a-real-pbf-fixture'),
                                     ('data/cache/rail_subset.sqlite',b'untouched cache'),
                                     ('.venv/keep.txt',b'untouched environment')]:
                path=root/filename;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            backup=backup_outputs(root)
            self.assertEqual((backup/'city_stations.csv').read_bytes(),b'original result')
            self.assertFalse((root/'outputs').exists())
            self.assertEqual((root/'data/cache/rail_subset.sqlite').read_bytes(),b'untouched cache')
            self.assertEqual((root/'.venv/keep.txt').read_bytes(),b'untouched environment')
            self.assertTrue((root/'data/raw/china-latest.osm.pbf').exists())
            self.assertIsNone(backup_outputs(root))


if __name__=='__main__': unittest.main()
