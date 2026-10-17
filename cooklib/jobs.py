"""Durable local queue; only a separate, resource-limited worker processes PDFs."""
import sqlite3
from .store import database
from .oss import valid_key


def queue_schema(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS import_jobs(id INTEGER PRIMARY KEY,object_key TEXT NOT NULL,title TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'queued',page INTEGER NOT NULL DEFAULT 0,total INTEGER NOT NULL DEFAULT 0,book_id INTEGER,error TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_active_import ON import_jobs(object_key) WHERE status IN ('queued','running')")


def enqueue(key,title):
    if not valid_key(key) or not title.strip() or len(title)>300:raise ValueError('书刊名称或文件路径不正确')
    with database() as conn:
        queue_schema(conn)
        existing=conn.execute("SELECT id FROM import_jobs WHERE object_key=? AND status IN ('queued','running')",(key,)).fetchone()
        if existing:return existing['id']
        try:return conn.execute('INSERT INTO import_jobs(object_key,title) VALUES(?,?)',(key,title.strip())).lastrowid
        except sqlite3.IntegrityError:
            return conn.execute("SELECT id FROM import_jobs WHERE object_key=? AND status IN ('queued','running')",(key,)).fetchone()['id']


def get_job(job_id):
    with database() as conn:
        queue_schema(conn)
        return conn.execute('SELECT * FROM import_jobs WHERE id=?',(job_id,)).fetchone()
