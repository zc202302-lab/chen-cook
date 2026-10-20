"""Chen Cook reading service. All PDF conversion stays on the desktop."""
import hmac
import os
import secrets
import tempfile
import threading
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from storage import ASSET, ID, LOCK, atomic_json, import_book, public_book, read_json, trash_book, list_trash, restore_book, purge_book


def create_app(data=None):
    root=Path(data or os.environ.get('COOK_READER_DATA','/var/lib/chen-cook/reader')).resolve()
    books=root/'books';books.mkdir(parents=True,exist_ok=True)
    token=os.environ.get('COOK_SYNC_TOKEN','')
    if not token:
        path=root/'sync-token'
        try:
            fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as stream:stream.write(secrets.token_urlsafe(32))
        except FileExistsError:pass
        token=path.read_text().strip()
        if not token:raise RuntimeError('同步密钥文件为空，请在服务器修复后重启')
    version=read_json(Path(__file__).parent/'version.json')['version']
    revision=os.environ.get('COOK_REVISION','development')
    app=FastAPI(title='灶间书房 · 阅读端',docs_url=None,redoc_url=None)
    app.state.root=root

    def directory(bid):
        if not ID.fullmatch(bid):raise HTTPException(404,'书籍不存在')
        path=books/bid
        if not (path/'book.json').is_file():raise HTTPException(404,'书籍不存在')
        return path

    @app.middleware('http')
    async def protect(request,call_next):
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            if origin and urlsplit(origin).netloc.lower()!=request.headers.get('host','').lower():
                return JSONResponse({'detail':'不接受跨站写入请求'},403)
        result=await call_next(request)
        if request.url.path in ('/','/index.html','/app.js','/style.css'):
            result.headers['Cache-Control']='no-cache'
        result.headers['X-Content-Type-Options']='nosniff'
        result.headers['Referrer-Policy']='same-origin'
        result.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        return result

    @app.get('/health')
    def health():return dict(ok=True,service='chen-cook',mode='reader',version=version,revision=revision)

    @app.get('/api/config')
    def config():return dict(mode='server',version=version,desktop=False,revision=revision)

    @app.get('/api/books')
    def listing():
        result=[]
        for path in books.glob('*/book.json'):
            b=read_json(path);blocks=[x for pg in b['pages'] for x in pg['blocks']]
            result.append(dict(id=b['id'],title=b['title'],pages=len(b['pages']),page_count=b.get('page_count',0),
                pending=sum(not x.get('reviewed') for x in blocks),status=b.get('status','done'),
                cover=next((x['src'] for x in blocks if x['kind']=='image'),None)))
        return result

    @app.delete('/api/books/{bid}')
    def delete_converted_book(bid:str,request:Request):
        if not hmac.compare_digest(request.headers.get('x-sync-token',''),token):raise HTTPException(403,'请输入网站同步密钥后管理书库')
        directory(bid)
        with LOCK:
            
            try:result=trash_book(root,bid)
            except ValueError as exc:raise HTTPException(409,str(exc))
            
        return result

    @app.get('/api/trash')
    def deleted_books(request:Request):
        if not hmac.compare_digest(request.headers.get('x-sync-token',''),token):raise HTTPException(403,'请输入网站同步密钥后管理书库')
        with LOCK:return list_trash(root)

    @app.post('/api/trash/{tid}/restore')
    def restore_converted_book(tid:str,request:Request):
        if not hmac.compare_digest(request.headers.get('x-sync-token',''),token):raise HTTPException(403,'请输入网站同步密钥后管理书库')
        with LOCK:
            try:result=restore_book(root,tid)
            except ValueError as exc:raise HTTPException(409,str(exc))
            
        return result

    @app.delete('/api/trash/{tid}')
    def purge_converted_book(tid:str,request:Request):
        if not hmac.compare_digest(request.headers.get('x-sync-token',''),token):raise HTTPException(403,'请输入网站同步密钥后管理书库')
        try:purge_book(root,tid)
        except ValueError as exc:raise HTTPException(404,str(exc))
        return {'ok':True}

    @app.get('/api/books/{bid}')
    def book(bid:str):return public_book(read_json(directory(bid)/'book.json'))

    @app.get('/api/books/{bid}/assets/{name}')
    def asset(bid:str,name:str):
        d=directory(bid)
        if not ASSET.fullmatch(name) or not (d/'assets'/name).is_file():raise HTTPException(404)
        return FileResponse(d/'assets'/name)

    @app.post('/api/import')
    def receive(request:Request,file:UploadFile=File(...)):
        if not hmac.compare_digest(request.headers.get('x-sync-token',''),token):raise HTTPException(403,'同步密钥不正确')
        with tempfile.TemporaryFile() as stream:
            size=0
            while chunk:=file.file.read(1024*1024):
                size+=len(chunk)
                if size>1024**3:raise HTTPException(413,'单个阅读包不能超过 1GB')
                stream.write(chunk)
            stream.seek(0)
            try:
                with LOCK:book=import_book(stream,books)
            except (ValueError,KeyError,TypeError,zipfile.BadZipFile) as exc:raise HTTPException(400,str(exc))
        return dict(id=book['id'],title=book['title'])

    @app.get('/api/search')
    def search(q:str=''):
        q=q.strip()
        if len(q)<2:return []
        matches=[]
        for path in books.glob('*/book.json'):
            b=read_json(path)
            for page in b['pages']:
                for block in page['blocks']:
                    text=block.get('text',block.get('caption',''));pos=text.lower().find(q.lower())
                    if pos>=0:matches.append(dict(book_id=b['id'],title=b['title'],block_id=block['id'],snippet=text[max(0,pos-25):pos+100]))
                    if len(matches)>=100:return matches
        return matches

    @app.get('/api/progress/{bid}')
    def progress(bid:str):
        directory(bid);p=root/'progress'/f'{bid}.json'
        return read_json(p) if p.exists() else {}

    @app.put('/api/progress/{bid}')
    def save_progress(bid:str,body:dict):
        directory(bid);block=body.get('block_id','');marks=body.get('bookmarks',[])
        if not isinstance(block,str) or len(block)>64 or not isinstance(marks,list) or len(marks)>1000 or any(not isinstance(x,str) or len(x)>64 for x in marks):
            raise HTTPException(400,'阅读进度格式错误')
        with LOCK:
            directory(bid)
            atomic_json(root/'progress'/f'{bid}.json',dict(block_id=block,bookmarks=marks))
        return {'ok':True}

    @app.get('/api/releases/latest')
    def latest():
        path=Path(__file__).parent/'releases'/'latest.json'
        if not path.is_file():path=root/'releases'/'latest.json'
        if not path.is_file():raise HTTPException(404,'尚未发布桌面更新')
        return FileResponse(path,headers={'Cache-Control':'no-store'})

    @app.get('/api/releases/{name}')
    def release(name:str):
        import re
        if not re.fullmatch(r'cook-reader-\d+\.\d+\.\d+\.zip',name):raise HTTPException(404)
        path=Path(__file__).parent/'releases'/name
        if not path.is_file():path=root/'releases'/name
        if not path.is_file():raise HTTPException(404)
        return FileResponse(path)

    app.mount('/',StaticFiles(directory=Path(__file__).parent/'web',html=True),name='web')
    return app

