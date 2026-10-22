"""Synthetic PDFs only: index integrity, literal Chinese search, source-page mapping and access."""
import io
import os
import tempfile
import time
import unittest
from unittest.mock import patch

import fitz
from fastapi.testclient import TestClient
from app import create_app

TOKEN='synthetic-catalogue-key'


def synthetic_pdf(scanned=False):
    doc=fitz.open()
    for text in ('合成封面', '卤水配方与保存知识', '鱼锅的制作说明', '卤水保管注意事项'):
        p=doc.new_page(width=420,height=594)
        if not scanned:
            p.insert_text((45,100), text*3, fontname='china-s', fontsize=18)
    if not scanned:
        doc.set_toc([[1,'卤水配方',2],[1,'鱼锅制作',3]])
    data=doc.tobytes();doc.close();return data


class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'COOK_SYNC_TOKEN':TOKEN})
        self.env.start()
        self.client=TestClient(create_app(self.temp.name))
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None,None,None);self.env.stop();self.temp.cleanup()

    def upload(self, scanned=False):
        self.uploaded_bytes=synthetic_pdf(scanned)
        r=self.client.post('/api/library/upload',headers={'x-sync-token':TOKEN},
            files={'file':('synthetic.pdf',self.uploaded_bytes)},data={'category':'烹饪杂志','year':'2026','issue':'测试期'})
        self.assertEqual(r.status_code,200,r.text)
        bid=r.json()['id']
        for _ in range(100):
            book=self.client.get('/api/library/books/'+bid).json()
            if book['status'] not in ('queued','indexing'):return book
            time.sleep(.02)
        self.fail('index did not complete')

    def test_toc_fulltext_and_precise_original_page(self):
        b=self.upload();bid=b['id']
        self.assertEqual(b['status'],'ready',b)
        self.assertEqual(b['articles'][1]['end'],4)
        r=self.client.get('/api/library/search',params={'q':'保管注意事项'}).json()
        self.assertEqual(r['total'],1)
        self.assertEqual(r['items'][0]['page'],4)
        self.assertEqual(r['items'][0]['title'],'鱼锅制作')
        self.assertEqual(self.client.get('/api/library/search',params={'q':'卤水','category':'菜谱书'}).json()['total'],0)
        self.assertGreater(self.client.get('/api/library/search',params={'q':'卤水'}).json()['total'],0)
        self.assertEqual(self.client.get('/api/library/search',params={'q':'%'}).json()['total'],0)
        self.assertEqual(self.client.get('/api/library/books/'+bid+'/page/99').status_code,404)
        image=self.client.get('/api/library/books/'+bid+'/page/2?width=400')
        self.assertEqual(image.headers['content-type'],'image/png')
        source=self.client.get('/api/library/books/'+bid+'/original')
        self.assertTrue(source.content.startswith(b'%PDF'))

    def test_access_duplicate_recoverable_delete_and_search(self):
        self.assertEqual(self.client.post('/api/library/upload',files={'file':('x.pdf',b'bad')}).status_code,403)
        b=self.upload();bid=b['id'];headers={'x-sync-token':TOKEN}
        self.assertEqual(self.client.post('/api/library/upload',headers=headers,files={'file':('x.pdf',self.uploaded_bytes)}).status_code,409)
        self.assertEqual(self.client.delete('/api/library/books/'+bid).status_code,403)
        self.assertEqual(self.client.delete('/api/library/books/'+bid,headers={**headers,'origin':'https://another.example'}).status_code,403)
        self.assertEqual(self.client.delete('/api/library/books/'+bid,headers=headers).status_code,200)
        self.assertEqual(self.client.get('/api/library/search?q=卤水').json()['total'],0)
        self.assertEqual(self.client.get('/api/library/books/'+bid+'/original').status_code,404)
        self.assertEqual(len(self.client.get('/api/library/books?trash=true').json()),1)
        self.assertEqual(self.client.post('/api/library/books/'+bid+'/restore',headers=headers).status_code,200)
        self.assertGreater(self.client.get('/api/library/search?q=卤水').json()['total'],0)

    def test_scan_status_and_manual_article_index(self):
        b=self.upload(scanned=True);bid=b['id']
        self.assertEqual(b['status'],'needs_ocr')
        self.assertEqual(b['empty_pages'],4)
        headers={'x-sync-token':TOKEN}
        self.assertEqual(self.client.put('/api/library/books/'+bid+'/catalogue',headers=headers,json=[{'title':'合成文章','start':2,'end':8}]).status_code,400)
        self.assertEqual(self.client.put('/api/library/books/'+bid+'/catalogue',headers=headers,json=[{'title':'合成文章','start':2,'end':4}]).status_code,200)
        r=self.client.get('/api/library/search?q=合成文章').json()
        self.assertEqual(r['total'],1)
        self.assertEqual(r['items'][0]['start'],2)
        self.assertEqual(r['items'][0]['kind'],'manual')


if __name__=='__main__':unittest.main()
