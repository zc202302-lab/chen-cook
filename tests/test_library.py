import os
import re
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import fitz
from fastapi.testclient import TestClient
from cooklib.auth import hash_password
from cooklib.store import database,root
from cooklib.import_book import import_pdf
from cooklib.web import create_app
from cooklib.jobs import enqueue,get_job
from cooklib import worker,oss

class LibraryTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.password='123';cls.hashed=hash_password(cls.password)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.env=patch.dict(os.environ,COOK_DATA_DIR=self.tmp.name,COOK_PASSWORD_HASH=self.hashed,COOK_SESSION_SECRET='test-secret-'*5,COOK_SECURE_COOKIE='0')
        self.env.start();self.addCleanup(self.env.stop)
        self.network=patch('cooklib.web.oss.list_sources',return_value=([],''));self.network.start();self.addCleanup(self.network.stop)
        self.client=TestClient(create_app());self.client.__enter__();self.addCleanup(self.client.__exit__,None,None,None)
    def token(self,path='/login'):
        return re.search(r'name="csrf" value="([^"]+)"',self.client.get(path).text)[1]
    def login(self):
        self.client.post('/login',data={'csrf':self.token(),'password':self.password})
    def fixture(self):
        source=Path(self.tmp.name)/'test.pdf'
        with fitz.open() as doc:
            for _ in range(3):doc.new_page()
            doc.set_toc([[1,'P8 测试章节',2]]);doc.save(source)
        return source
    def test_auth_csrf_private_images(self):
        self.assertEqual(self.client.get('/books/1/images/1',follow_redirects=False).status_code,303)
        self.assertEqual(self.client.post('/login',data={'password':self.password}).status_code,403)
        self.login();self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.post('/settings',data={}).status_code,403)
        cookie=self.client.cookies['chen_cook_session']
        self.client.cookies.set('chen_cook_session',cookie+'tamper')
        self.assertEqual(self.client.get('/jobs',follow_redirects=False).status_code,303)
    def test_reading_and_atomic_directory(self):
        book_id,_=import_pdf(self.fixture(),'magazines/test.pdf','测试<script>书',reading_only=True)
        self.login()
        detail=self.client.get(f'/books/{book_id}').text
        self.assertIn('P8 测试章节',detail);self.assertIn('&lt;script&gt;',detail)
        self.assertEqual(self.client.get(f'/books/{book_id}/images/2').status_code,200)
        token=self.token(f'/books/{book_id}/contents')
        response=self.client.post(f'/books/{book_id}/contents',data={'csrf':token,'title':'bad','page':'4'})
        self.assertEqual(response.status_code,400)
        self.assertIn('P8 测试章节',self.client.get(f'/books/{book_id}').text)
        response=self.client.post(f'/books/{book_id}/contents',data={'csrf':token,'title':'网页新章节','page':'3'})
        self.assertEqual(response.status_code,200);self.assertIn('网页新章节',response.text)
        self.assertEqual(self.client.get(f'/books/{book_id}/pages/4').status_code,404)
    def test_directory_file_upload_is_atomic_and_csrf_protected(self):
        book_id,_=import_pdf(self.fixture(),'ebooks/toc.pdf','目录样书',reading_only=True)
        self.login();url=f'/books/{book_id}/contents/file'
        data=b'[{"title":"Uploaded chapter","page":3}]'
        self.assertEqual(self.client.post(url,files={'file':('toc.json',data)}).status_code,403)
        token=self.token(f'/books/{book_id}/contents')
        response=self.client.post(url,data={'csrf':token},files={'file':('toc.json',data)})
        self.assertEqual(response.status_code,200);self.assertIn('Uploaded chapter',response.text)
        response=self.client.post(url,data={'csrf':token},files={'file':('bad.json',b'[{"title":"bad","page":999}]')})
        self.assertEqual(response.status_code,400)
        self.assertIn('Uploaded chapter',self.client.get(f'/books/{book_id}').text)
    def test_reader_is_dedicated_and_empty_directory_is_actionable(self):
        book_id,_=import_pdf(self.fixture(),'ebooks/reader.pdf','测试<script>书',reading_only=True)
        url=f'/books/{book_id}/pages/1'
        self.assertEqual(self.client.get(url,follow_redirects=False).status_code,303)
        self.assertEqual(self.client.get('/reader.css',follow_redirects=False).status_code,303)
        self.login()
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertIn('/reader.css',response.text)
        self.assertIn('class="reader-topbar"',response.text)
        self.assertNotIn('class="site-header"',response.text)
        self.assertIn('&lt;script&gt;',response.text)
        self.assertIn('已是首页',response.text)
        with database() as conn:conn.execute('DELETE FROM book_contents WHERE book_id=?',(book_id,))
        response=self.client.get(url)
        self.assertIn('这本书尚未录入章节目录',response.text)
        self.assertIn('录入 / 导入目录',response.text)
        self.assertEqual(self.client.get('/reader.css').status_code,200)
    def test_comfort_is_private_escaped_and_preserves_original(self):
        book_id,_=import_pdf(self.fixture(),'ebooks/comfort.pdf','文字版',reading_only=True)
        endpoint=f'/books/{book_id}/flow/1'
        self.assertEqual(self.client.get(endpoint,follow_redirects=False).status_code,303)
        self.login()
        text='步骤1加入150\n克。\n步骤2 <script>alert(1)</script>'
        with database() as conn:conn.execute('UPDATE pages SET text=?,method=? WHERE book_id=? AND page=1',(text,'ocr:test',book_id))
        response=self.client.get(f'/books/{book_id}/pages/1?mode=comfort')
        self.assertEqual(response.status_code,200)
        self.assertIn('&lt;script&gt;',response.text);self.assertNotIn('<script>alert(1)',response.text)
        self.assertIn('加入150克',response.text)
        self.assertIn('id="font-larger"',response.text)
        self.assertNotIn('id="page-image"',response.text)
        self.assertIn('?mode=comfort',response.text)
        payload=self.client.get(endpoint).json()
        self.assertEqual(payload['page'],1);self.assertTrue(payload['blocks'])
        self.assertEqual(self.client.get(f'/books/{book_id}/flow/4').status_code,404)
        self.assertEqual(self.client.get(f'/books/{book_id}/pages/1?mode=invalid').status_code,400)
        with database() as conn:self.assertEqual(conn.execute('SELECT text FROM pages WHERE book_id=? AND page=1',(book_id,)).fetchone()['text'],text)
        self.assertIn('id="page-image"',self.client.get(f'/books/{book_id}/pages/1').text)
    def test_durable_import_and_credentials_not_echoed(self):
        source=self.fixture();self.login();token=self.token('/settings')
        self.client.post('/settings',data={'csrf':token,'bucket':'test-bucket','access_id':'private-id','access_secret':'private-secret'})
        self.assertNotIn('private-secret',self.client.get('/settings').text)
        self.assertEqual(oss.settings_path().stat().st_mode & 0o777,0o600)
        job=enqueue('ebooks/test.pdf','任务书');self.assertEqual(job,enqueue('ebooks/test.pdf','重复'))
        def download(key,path):Path(path).write_bytes(source.read_bytes())
        with patch('cooklib.worker.oss.download',side_effect=download):self.assertTrue(worker.run_once())
        self.assertEqual(get_job(job)['status'],'done')
        self.assertEqual(get_job(job)['page'],3)
        self.assertFalse(any(root().glob('import-*')))
        self.assertEqual(self.client.get(f'/jobs/{job}').status_code,200)
    def test_failure_does_not_expose_upstream_secret(self):
        job=enqueue('ebooks/bad.pdf','bad')
        with patch('cooklib.worker.oss.download',side_effect=RuntimeError('SECRET_TOKEN_URL')):worker.run_once()
        self.assertEqual(get_job(job)['status'],'failed')
        self.assertNotIn('SECRET_TOKEN_URL',get_job(job)['error'])
        with database() as conn:self.assertEqual(conn.execute('SELECT count(*) FROM books').fetchone()[0],0)
    def test_chunked_body_limit(self):
        response=self.client.post('/login',content=iter([b'x'*70000,b'y'*70000]))
        self.assertEqual(response.status_code,413)

if __name__=='__main__':unittest.main()
