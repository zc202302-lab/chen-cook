"""Separate SQLite catalogue; never opens the assistant business database."""
from contextlib import contextmanager
from functools import lru_cache
import os
from pathlib import Path
import sqlite3


@lru_cache(maxsize=1)
def trigram_available():
    """Probe the Python runtime, without opening or changing the user's catalogue."""
    conn = sqlite3.connect(':memory:')
    try:
        conn.execute("CREATE VIRTUAL TABLE probe USING fts5(text,tokenize='trigram')")
        return True
    except sqlite3.OperationalError as error:
        if str(error) in {'no such tokenizer: trigram', 'no such module: fts5'}:
            return False
        raise
    finally:
        conn.close()


def index_page(conn, text, book_id, page):
    # Old SQLite must never open even an existing trigram virtual table.
    if trigram_available():
        conn.execute('INSERT INTO page_search(text,book_id,page) VALUES(?,?,?)',
                     (text, book_id, page))
    else:
        conn.execute("INSERT OR REPLACE INTO search_state VALUES('needs_rebuild',1)")


def root():
    return Path(os.environ.get('COOK_DATA_DIR', '/var/lib/chen-cook')).expanduser()


@contextmanager
def database():
    folder = root()
    folder.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(folder / 'catalogue.sqlite3', timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA foreign_keys=ON')
        conn.execute('CREATE TABLE IF NOT EXISTS books(id INTEGER PRIMARY KEY,title TEXT NOT NULL,kind TEXT NOT NULL CHECK(kind IN (\'ebooks\',\'magazines\')),object_key TEXT UNIQUE NOT NULL,sha256 TEXT UNIQUE NOT NULL,pages INTEGER NOT NULL)')
        conn.execute('CREATE TABLE IF NOT EXISTS pages(book_id INTEGER REFERENCES books(id),page INTEGER,text TEXT NOT NULL,method TEXT NOT NULL,PRIMARY KEY(book_id,page))')
        conn.execute('CREATE TABLE IF NOT EXISTS book_contents(book_id INTEGER REFERENCES books(id),position INTEGER,title TEXT NOT NULL,page INTEGER NOT NULL,level INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(book_id,position))')
        conn.execute('CREATE TABLE IF NOT EXISTS search_state(name TEXT PRIMARY KEY,value INTEGER NOT NULL)')
        # Preserve migrated trigram tables on old SQLite; pages is the source of truth.
        if trigram_available():
            conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS page_search USING fts5(text,book_id UNINDEXED,page UNINDEXED,tokenize='trigram')")
            if conn.execute("SELECT 1 FROM search_state WHERE name='needs_rebuild'").fetchone():
                # If SQLite is upgraded later, include books imported in fallback mode.
                conn.execute('DELETE FROM page_search')
                conn.execute('INSERT INTO page_search(text,book_id,page) SELECT text,book_id,page FROM pages')
                conn.execute("DELETE FROM search_state WHERE name='needs_rebuild'")
                conn.commit()  # Finish maintenance before callers start their transaction.
        yield conn
        conn.commit()
    except BaseException:
        conn.rollback()
        raise
    finally:
        conn.close()


def search(conn, query):
    query = query.strip()
    if not query:
        return []
    if len(query) > 100:
        raise ValueError('搜索词最多100字')
    if len(query) < 3 or not trigram_available():
        return conn.execute('SELECT b.title,b.id,p.page,p.text FROM pages p JOIN books b ON b.id=p.book_id WHERE instr(p.text,?)>0 ORDER BY b.id,p.page LIMIT 101', (query,)).fetchall()
    return conn.execute('SELECT b.title,b.id,p.page,p.text FROM page_search s JOIN books b ON b.id=s.book_id JOIN pages p ON p.book_id=s.book_id AND p.page=s.page WHERE page_search MATCH ? ORDER BY rank LIMIT 101', ('"' + query.replace('"', '""') + '"',)).fetchall()
