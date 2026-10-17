import importlib.util
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('migration',ROOT/'scripts/migrate_library.py')
migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)

class MigrationTest(unittest.TestCase):
    def test_copy_preserves_old_and_never_overwrites_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'old';source.mkdir();target=Path(tmp)/'new'
            with sqlite3.connect(source/'catalogue.sqlite3') as conn:
                conn.execute('CREATE TABLE private_data(value TEXT)');conn.execute("INSERT INTO private_data VALUES('retained')")
            before=(source/'catalogue.sqlite3').read_bytes()
            preview=source/'previews'/'hash'/'1.jpg';preview.parent.mkdir(parents=True);preview.write_bytes(b'private-image')
            migration.migrate(source,target)
            self.assertEqual(before,(source/'catalogue.sqlite3').read_bytes())
            self.assertEqual((target/'previews'/'hash'/'1.jpg').read_bytes(),b'private-image')
            with sqlite3.connect(target/'catalogue.sqlite3') as conn:conn.execute("UPDATE private_data SET value='new-owner-edit'")
            migration.migrate(source,target)
            with sqlite3.connect(target/'catalogue.sqlite3') as conn:self.assertEqual(conn.execute('SELECT value FROM private_data').fetchone()[0],'new-owner-edit')
    def test_no_assistant_dependencies_or_public_bind(self):
        for file in (ROOT/'cooklib').rglob('*.py'):
            self.assertNotIn('from app ',file.read_text());self.assertNotIn('import app.',file.read_text())
        unit=(ROOT/'deploy/chen-cook.service').read_text()
        self.assertIn('--host 172.19.0.1 --port 8020',unit)
        self.assertNotIn('8010',unit)
        proxy=(ROOT/'deploy/Caddyfile.cook').read_text()
        self.assertIn('cook.ziboxiaozhushou.cn',proxy);self.assertIn('172.19.0.1:8020',proxy)

if __name__=='__main__':unittest.main()
