"""Single-process PDF preview worker; no OCR, no web-thread rendering."""
import fcntl
import logging
import signal
import shutil
import tempfile
import time
from .store import root,database
from .jobs import queue_schema
from . import oss
from .import_book import import_pdf

_stop=False
def stop(*_):
    global _stop
    _stop=True


def run_once():
    with database() as conn:
        queue_schema(conn)
        conn.execute('BEGIN IMMEDIATE')
        job=conn.execute("SELECT * FROM import_jobs WHERE status='queued' ORDER BY id LIMIT 1").fetchone()
        if not job:return False
        conn.execute("UPDATE import_jobs SET status='running',error='' WHERE id=?",(job['id'],))
    try:
        with tempfile.TemporaryDirectory(dir=root(),prefix='import-') as tmp:
            if shutil.disk_usage(root()).free<3*1024**3:raise ValueError('磁盘空间不足')
            path=__import__('pathlib').Path(tmp)/'source.pdf'
            oss.download(job['object_key'],path)
            def progress(page,total):
                with database() as conn:
                    conn.execute('UPDATE import_jobs SET page=?,total=? WHERE id=?',(page,total,job['id']))
            book_id,_=import_pdf(path,job['object_key'],job['title'],reading_only=True,progress=progress)
        with database() as conn:conn.execute("UPDATE import_jobs SET status='done',book_id=? WHERE id=?",(book_id,job['id']))
    except Exception:
        # Upstream exceptions may embed signed URLs/credentials; never expose their text.
        logging.error('Import job %s failed',job['id'])
        with database() as conn:conn.execute("UPDATE import_jobs SET status='failed',error='入库失败，请核对OSS读取权限、文件完整性、磁盘空间后重试。' WHERE id=?",(job['id'],))
    return True


def main():
    root().mkdir(parents=True,exist_ok=True)
    with (root()/'worker.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        # A killed worker may leave its temporary download; originals remain in OSS.
        for pending in root().glob('import-*'):
            if pending.is_dir() and not pending.is_symlink():shutil.rmtree(pending)
        with database() as conn:
            queue_schema(conn)
            conn.execute("UPDATE import_jobs SET status='queued',page=0,total=0 WHERE status='running'")
        signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
        while not _stop:
            if not run_once():time.sleep(3)


if __name__=='__main__':main()
