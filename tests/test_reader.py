import base64
import io
import json
import os
import tempfile
import unittest
import zipfile
import struct
import zlib
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
from app import create_app

BID='a'*24
TOKEN='synthetic-test-token'
DETAIL_TEXT='步骤1熬制汤料1.取骨料1200克，加入清水2.5升。2.加入盐12克，煮30分钟。3.过滤汤料。\n步骤2调制卤水将香料加入汤中，煮15分钟。\n应用方法1.用0.5%的盐水处理食材。2.洗净后焯水。3.煮熟捞出。制作味汁取红油20克，加入酱油5克。'

def synthetic_png():
    width,height=400,220
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    raw=b''.join(b'\0'+bytes((80+y//4,130+y//8,90))*width for y in range(height))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b'')


def package(extra=None,catalog=False):
    book=dict(id=BID,title='合成阅读样书',page_count=1,revision=1,status='done',pages=[dict(page=1,blocks=[
        dict(id='title',kind='heading',page=1,level=1,reviewed=False,text='合成菜谱'),
        dict(id='body',kind='text',page=1,reviewed=False,text='合成原料说明\n应随屏幕自然换行。'),
        dict(id='image',kind='image',page=1,reviewed=False,src='photo.png',caption='合成配图'),
        dict(id='steps',kind='heading',page=1,level=2,reviewed=False,text='制作步骤'),
        dict(id='method',kind='text',page=1,reviewed=False,text='1.准备食材。\n2.按顺序处理。'),dict(id='detail',kind='text',page=1,reviewed=False,text=DETAIL_TEXT)])])
    if catalog:
        raw='合成菜谱··05\n另一道菜··08'
        book['pages'][0]['blocks'].insert(0,dict(id='catalog',kind='text',page=1,role='catalog',text=raw,
          catalog=dict(text_snapshot=raw,rows=[dict(title='合成菜谱',printed_page='05',target_id='title',raw='合成菜谱··05'),dict(title='另一道菜',printed_page='08',raw='另一道菜··08')])))
    data=io.BytesIO()
    with zipfile.ZipFile(data,'w') as z:
        z.writestr('book.json',json.dumps(book,ensure_ascii=False))
        z.writestr('assets/photo.png',synthetic_png())
        if extra:z.writestr(extra,b'not allowed')
    return data.getvalue()


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.env=patch.dict(os.environ,{'COOK_SYNC_TOKEN':TOKEN,'COOK_REVISION':'test-revision'})
        self.env.start();self.client=TestClient(create_app(self.root));self.client.__enter__()
    def tearDown(self):
        self.client.__exit__(None,None,None);self.env.stop();self.temp.cleanup()
    def upload(self,content=None,key=TOKEN):
        return self.client.post('/api/import',files={'file':('book.zip',content or package())},headers={'x-sync-token':key})

    def test_desktop_release_manifest_and_checksum(self):
        import hashlib
        manifest=self.client.get('/api/releases/latest')
        self.assertEqual(manifest.status_code,200)
        self.assertEqual(manifest.headers['cache-control'],'no-store')
        info=manifest.json();self.assertEqual(info['version'],'0.5.2')
        archive=self.client.get('/api/releases/'+info['url'])
        self.assertEqual(archive.status_code,200)
        self.assertEqual(hashlib.sha256(archive.content).hexdigest(),info['sha256'])
        with zipfile.ZipFile(io.BytesIO(archive.content)) as z:
            self.assertTrue({'app.py','engine.py','desktop.py','launcher.py','version.json','web/app.js'}.issubset(z.namelist()))
            self.assertFalse(any(n.startswith(('data/','runtime/')) or n.lower().endswith('.pdf') for n in z.namelist()))
        self.assertEqual(self.client.get('/api/releases/anything.txt').status_code,404)

    def test_delete_requires_key_and_preserves_reader_progress_on_restore(self):
        self.upload();self.client.put('/api/progress/'+BID,json={'block_id':'title','bookmarks':['title']})
        self.assertEqual(self.client.delete('/api/books/'+BID).status_code,403)
        headers={'x-sync-token':TOKEN}
        deleted=self.client.delete('/api/books/'+BID,headers=headers);self.assertEqual(deleted.status_code,200,deleted.text)
        tid=deleted.json()['trash_id'];self.assertEqual(self.client.get('/api/books/'+BID).status_code,404)
        self.assertEqual(self.client.get('/api/trash').status_code,403)
        self.assertEqual(len(self.client.get('/api/trash',headers=headers).json()),1)
        self.assertEqual(self.client.post('/api/trash/'+tid+'/restore',headers=headers).status_code,200)
        self.assertEqual(self.client.get('/api/progress/'+BID).json()['bookmarks'],['title'])
        tid=self.client.delete('/api/books/'+BID,headers=headers).json()['trash_id']
        self.assertEqual(self.client.delete('/api/trash/'+tid,headers=headers).status_code,200)
        self.assertEqual(self.client.get('/api/trash',headers=headers).json(),[])

    def test_delete_rejects_cross_origin_even_with_key(self):
        self.upload()
        self.assertEqual(self.client.delete('/api/books/'+BID,headers={'x-sync-token':TOKEN,'origin':'https://untrusted.invalid'}).status_code,403)
        self.assertEqual(len(self.client.get('/api/books').json()),1)

    def test_reader_assets_revalidate_after_upgrade(self):
        response=self.client.get('/')
        self.assertEqual(response.headers['cache-control'],'no-cache')
        self.assertIn('/app.js?v=0.5.2',response.text)
        for path in ('/app.js?v=0.5.2','/style.css?v=0.5.2'):
            self.assertEqual(self.client.get(path).headers['cache-control'],'no-cache')

    def test_health_and_role(self):
        self.assertEqual(self.client.get('/health').json()['revision'],'test-revision')
        self.assertEqual(self.client.get('/api/config').json()['mode'],'server')
        for path in ('/api/jobs','/api/pick','/api/quit','/api/update/install'):
            self.assertIn(self.client.post(path).status_code,(404,405))

    def test_upload_read_and_search(self):
        self.assertEqual(self.upload().status_code,200)
        self.assertEqual(len(self.client.get('/api/books').json()),1)
        book=self.client.get('/api/books/'+BID).json()
        self.assertEqual(book['pages'][0]['blocks'][1]['text'],'合成原料说明\n应随屏幕自然换行。')
        self.assertEqual(self.client.get('/api/books/'+BID+'/assets/photo.png').status_code,200)
        self.assertEqual(self.client.get('/api/search?q=合成原料').json()[0]['block_id'],'body')

    def test_catalog_metadata_survives_import(self):
        self.assertEqual(self.upload(package(catalog=True)).status_code,200)
        block=self.client.get('/api/books/'+BID).json()['pages'][0]['blocks'][0]
        self.assertEqual(block['catalog']['rows'][0]['target_id'],'title')
        self.assertEqual(block['text'],'合成菜谱··05\n另一道菜··08')

    def test_progress_and_bookmarks(self):
        self.upload();state=dict(block_id='steps',bookmarks=['title'])
        self.assertEqual(self.client.put('/api/progress/'+BID,json=state).status_code,200)
        self.assertEqual(self.client.get('/api/progress/'+BID).json(),state)

    def test_import_requires_key_and_same_origin(self):
        self.assertEqual(self.upload(key='wrong').status_code,403)
        response=self.client.post('/api/import',files={'file':('x.zip',package())},headers={'x-sync-token':TOKEN,'Origin':'https://unrelated.example'})
        self.assertEqual(response.status_code,403)

    def test_reject_originals_and_traversal(self):
        for name in ('original.pdf','../escape','assets/../../escape'):
            self.assertEqual(self.upload(package(name)).status_code,400)
        self.assertEqual(self.client.get('/api/books').json(),[])

    def test_duplicate_does_not_replace_book(self):
        self.assertEqual(self.upload().status_code,200)
        self.assertEqual(self.upload().status_code,400)
        self.assertEqual(len(self.client.get('/api/books').json()),1)

    def test_old_files_are_untouched(self):
        old=self.root.parent/('old-'+self.root.name+'.sqlite3');old.write_bytes(b'legacy data')
        try:
            self.upload();self.assertEqual(old.read_bytes(),b'legacy data')
        finally:old.unlink()

    def test_auto_generated_key_is_private_and_persistent(self):
        with patch.dict(os.environ,{'COOK_SYNC_TOKEN':''}):
            d=self.root/'separate';create_app(d);first=(d/'sync-token').read_text();create_app(d)
            self.assertEqual((d/'sync-token').read_text(),first)
            self.assertEqual((d/'sync-token').stat().st_mode&0o777,0o600)

if __name__=='__main__':unittest.main()

