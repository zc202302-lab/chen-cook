"""Old-runtime imports must not open a migrated, unsupported trigram table."""
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import fitz

from cooklib import store, worker
from cooklib.import_book import import_pdf
from cooklib.jobs import enqueue, get_job


class SQLiteCompatibilityTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = patch.dict(os.environ, COOK_DATA_DIR=tmp.name)
        env.start()
        self.addCleanup(env.stop)
        self.source = Path(tmp.name) / 'synthetic.pdf'
        with fitz.open() as doc:
            page = doc.new_page()
            page.insert_text((40, 60), 'Synthetic recipe: simmer vegetables for twenty minutes.')
            doc.set_toc([[1, 'Synthetic chapter', 1]])
            doc.save(self.source)

    def import_job(self):
        job = enqueue('ebooks/new.pdf', 'New synthetic book')
        def download(key, path):
            Path(path).write_bytes(self.source.read_bytes())
        with patch('cooklib.worker.oss.download', side_effect=download):
            self.assertTrue(worker.run_once())
        result = get_job(job)
        self.assertEqual(result['status'], 'done', result['error'])
        self.assertEqual((result['page'], result['total']), (1, 1))
        with store.database() as conn:
            self.assertEqual(len(store.search(conn, 'vegetables')), 1)
            self.assertEqual(conn.execute('SELECT title FROM book_contents WHERE book_id=?',
                                         (result['book_id'],)).fetchone()[0], 'Synthetic chapter')
        self.assertFalse(any(store.root().glob('import-*')))

    def test_fresh_catalogue_without_trigram_imports_and_searches(self):
        with patch.object(store, 'trigram_available', return_value=False):
            self.import_job()
            with store.database() as conn:
                self.assertIsNone(conn.execute("SELECT name FROM sqlite_master WHERE name='page_search'").fetchone())
                self.assertEqual(store.search(conn, 'absent'), [])

    def test_migrated_index_is_untouched_on_old_runtime(self):
        with store.database() as conn:
            conn.execute("INSERT INTO books VALUES(1,'Existing book','ebooks','ebooks/old.pdf','old',1)")
            conn.execute("INSERT INTO pages VALUES(1,1,'红烧肉配方 原有正文','pdf')")
            store.index_page(conn, '红烧肉配方 原有正文', 1, 1)
            before = list(conn.execute('SELECT * FROM page_search'))

        real_connect = sqlite3.connect
        def old_runtime_connect(*args, **kwargs):
            conn = real_connect(*args, **kwargs)
            def authorize(action, table, column, database, trigger):
                if table and table.startswith('page_search'):
                    return sqlite3.SQLITE_DENY
                return sqlite3.SQLITE_OK
            conn.set_authorizer(authorize)
            return conn

        with patch.object(store, 'trigram_available', return_value=False), \
                patch.object(store.sqlite3, 'connect', side_effect=old_runtime_connect):
            self.import_job()
            with store.database() as conn:
                self.assertEqual(store.search(conn, '红烧肉')[0]['title'], 'Existing book')
                self.assertEqual(store.search(conn, '原有')[0]['text'], '红烧肉配方 原有正文')

        # Returning to a supported runtime rebuilds the index from all canonical pages.
        with store.database() as conn:
            conn.execute('BEGIN IMMEDIATE')
            self.assertEqual(conn.execute('SELECT count(*) FROM books').fetchone()[0], 2)
            self.assertEqual(len(store.search(conn, 'vegetables')), 1)
            self.assertEqual(tuple(conn.execute('SELECT * FROM page_search WHERE book_id=1').fetchone()), tuple(before[0]))
            self.assertIsNone(conn.execute("SELECT 1 FROM search_state WHERE name='needs_rebuild'").fetchone())

    def test_probe_only_handles_missing_features(self):
        store.trigram_available.cache_clear()
        self.addCleanup(store.trigram_available.cache_clear)
        for message in ('no such tokenizer: trigram', 'no such module: fts5'):
            with patch.object(store.sqlite3, 'connect') as connect:
                connect.return_value.execute.side_effect = sqlite3.OperationalError(message)
                self.assertFalse(store.trigram_available())
                connect.return_value.close.assert_called_once()
            store.trigram_available.cache_clear()
        with patch.object(store.sqlite3, 'connect') as connect:
            connect.return_value.execute.side_effect = sqlite3.OperationalError('disk I/O error')
            with self.assertRaisesRegex(sqlite3.OperationalError, 'disk I/O error'):
                store.trigram_available()


if __name__ == '__main__':
    unittest.main()
