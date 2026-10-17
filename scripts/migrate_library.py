"""Copy private data using SQLite backup; never delete/change the old library."""
from pathlib import Path
import shutil
import sqlite3

def migrate(source,target):
    if not (source/'catalogue.sqlite3').is_file():
        print('未发现旧样书库，新站使用空书库')
    elif (target/'catalogue.sqlite3').exists():
        print('新站已有书库，保留现有数据，不覆盖')
    else:
        target.mkdir(parents=True,exist_ok=True)
        for directory in ('previews','ocr-audit'):
            if (source/directory).is_dir():shutil.copytree(source/directory,target/directory,dirs_exist_ok=True)
        temporary=target/'catalogue.migrating.sqlite3'
        with sqlite3.connect('file:'+str(source/'catalogue.sqlite3')+'?mode=ro',uri=True) as old,sqlite3.connect(temporary) as new:
            old.backup(new)
            assert new.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        temporary.replace(target/'catalogue.sqlite3')
        print('已复制旧样书数据库和阅读预览；原库未改变')


if __name__=='__main__':
    migrate(Path('/opt/chen-assistant/data/cooking-library'),Path('/var/lib/chen-cook'))
