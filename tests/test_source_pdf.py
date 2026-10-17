import io
import os
import re
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from fastapi.testclient import TestClient
from cooklib.auth import hash_password
from cooklib.store import database
from cooklib.web import create_app


class OriginalPDFTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.hashed=hash_password('test')
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        env=patch.dict(os.environ,COOK_DATA_DIR=tmp.name,COOK_PASSWORD_HASH=self.hashed,COOK_SESSION_SECRET='source-pdf-test-'*4,COOK_SECURE_COOKIE='0')
        env.start();self.addCleanup(env.stop)
        with database() as conn:conn.execute('INSERT INTO books VALUES(1,?,?,?,?,?)',('原书','ebooks','ebooks/original.pdf','a'*64,5))
        self.data=b'%PDF-1.7\n'+bytes(range(256))*2048+b'\n%%EOF'
        self.responses=[];self.bucket=Mock()
        self.bucket.head_object.return_value=SimpleNamespace(content_length=len(self.data),etag='abc123',last_modified=1700000000)
        def get(key,byte_range=None,headers=None):
            start,end=byte_range if byte_range else (0,len(self.data)-1)
            result=io.BytesIO(self.data[start:end+1]);self.responses.append(result);return result
        self.bucket.get_object.side_effect=get
        for mock in [patch('cooklib.oss.bucket_client',return_value=self.bucket),patch('cooklib.oss.configured',return_value=True)]:
            mock.start();self.addCleanup(mock.stop)
        self.client=TestClient(create_app());self.client.__enter__();self.addCleanup(self.client.__exit__,None,None,None)
        self.url='/books/1/source.pdf'
    def login(self):
        token=re.search(r'name="csrf" value="([^"]+)"',self.client.get('/login').text)[1]
        self.client.post('/login',data={'csrf':token,'password':'test'})
    def test_auth_and_original_bytes_and_head(self):
        self.assertEqual(self.client.get(self.url,follow_redirects=False).status_code,303)
        self.bucket.head_object.assert_not_called()
        self.login()
        head=self.client.head(self.url)
        self.assertEqual(head.status_code,200);self.assertEqual(head.content,b'')
        self.assertEqual(head.headers['content-length'],str(len(self.data)))
        self.bucket.get_object.assert_not_called()
        response=self.client.get(self.url)
        self.assertEqual(response.content,self.data)
        self.assertEqual(response.headers['content-type'],'application/pdf')
        self.assertTrue(response.headers['content-disposition'].startswith('inline;'))
        self.assertEqual(response.headers['accept-ranges'],'bytes')
        self.assertEqual(response.headers['cache-control'],'no-store')
        self.assertTrue(all(r.closed for r in self.responses))
    def test_ranges_and_if_range(self):
        self.login();size=len(self.data)
        for value,start,end in [('bytes=0-4',0,4),('bytes=5-',5,size-1),('bytes=-8',size-8,size-1),('bytes=10-99999999',10,size-1)]:
            response=self.client.get(self.url,headers={'Range':value})
            self.assertEqual(response.status_code,206,value)
            self.assertEqual(response.content,self.data[start:end+1])
            self.assertEqual(response.headers['content-range'],f'bytes {start}-{end}/{size}')
        response=self.client.get(self.url,headers={'Range':'bytes=0-4','If-Range':'"old"'})
        self.assertEqual(response.status_code,200);self.assertEqual(response.content,self.data)
        response=self.client.get(self.url,headers={'Range':'bytes=0-4','If-Range':'"abc123"'})
        self.assertEqual(response.status_code,206)
        for invalid in ['bytes=99999999-','bytes=5-2','bytes=-0','bytes=','bytes=0-2,5-8','not-a-range']:
            response=self.client.get(self.url,headers={'Range':invalid})
            self.assertEqual(response.status_code,416,invalid)
            self.assertEqual(response.headers['content-range'],f'bytes */{size}')
    def test_errors_are_generic_and_source_is_main_entry(self):
        self.login()
        detail=self.client.get('/books/1').text
        self.assertIn('href="/books/1/source.pdf">开始阅读',detail)
        self.assertNotIn('舒适阅读 · 文字版',detail)
        self.bucket.head_object.side_effect=RuntimeError('PRIVATE_SIGNED_URL')
        response=self.client.get(self.url)
        self.assertEqual(response.status_code,502);self.assertNotIn('PRIVATE_SIGNED_URL',response.text)
        self.assertEqual(self.client.get('/books/999/source.pdf').status_code,404)
        with patch('cooklib.oss.configured',return_value=False):
            response=self.client.get(self.url,follow_redirects=False)
            self.assertEqual(response.status_code,303);self.assertEqual(response.headers['location'],'/settings')
