"""Standalone private book library; never imports the assistant application."""
import os
import json
from pathlib import Path
import secrets
from fastapi import FastAPI,Request,HTTPException,Form,UploadFile,File
from fastapi.responses import FileResponse,HTMLResponse,RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from . import __version__,oss
from .store import database,root,search
from .contents import replace_contents
from .auth import csrf_token,require_csrf,verify_password,login_allowed,login_failed
from .jobs import enqueue,get_job,queue_schema
from .limits import BodyLimit

BASE=Path(__file__).parent
TEMPLATES=Jinja2Templates(directory=BASE/'templates')


def create_app():
    app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
    secret=os.environ.get('COOK_SESSION_SECRET','')
    password_hash=os.environ.get('COOK_PASSWORD_HASH','')
    if len(secret)<32 or not password_hash:raise RuntimeError('请先完成独立站初始账户配置')

    @app.middleware('http')
    async def guard(request,call_next):
        path=request.url.path
        if path not in ('/login','/health','/style.css') and not request.session.get('owner'):
            return RedirectResponse('/login',303)
        limit=128*1024
        try:length=int(request.headers.get('content-length','0'))
        except ValueError:return HTMLResponse('请求格式错误',400)
        if request.method=='POST' and (length>limit or length<0):return HTMLResponse('提交内容过大',413)
        response=await call_next(request)
        response.headers.update({'Content-Security-Policy':"default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'",'X-Content-Type-Options':'nosniff','Referrer-Policy':'same-origin','Cache-Control':'no-store'})
        return response

    app.add_middleware(BodyLimit)

    # Added last, therefore outermost: session is populated before authentication guard.
    app.add_middleware(SessionMiddleware,secret_key=secret,session_cookie='chen_cook_session',https_only=os.environ.get('COOK_SECURE_COOKIE','1')=='1',same_site='lax',max_age=7*86400)

    def render(request,name,**context):
        return TEMPLATES.TemplateResponse(request=request,name=name,context={'csrf':csrf_token(request),**context})

    @app.get('/health')
    def health():return {'ok':True,'version':__version__,'service':'chen-cook','revision':os.environ.get('COOK_REVISION','unknown')}

    @app.get('/style.css')
    def stylesheet():return FileResponse(BASE/'style.css',media_type='text/css')

    @app.get('/reader.js')
    def reader_script():return FileResponse(BASE/'reader.js',media_type='application/javascript')

    @app.get('/manage.js')
    def manage_script():return FileResponse(BASE/'manage.js',media_type='application/javascript')

    @app.get('/login')
    def login_page(request:Request):return render(request,'login.html',error='')

    @app.post('/login')
    def login(request:Request,password:str=Form(''),csrf:str=Form('')):
        require_csrf(request,csrf)
        address=request.client.host if request.client else 'unknown'
        if not login_allowed(address):return render(request,'login.html',error='尝试过多，请五分钟后重试')
        if not verify_password(password,password_hash):
            login_failed(address)
            return render(request,'login.html',error='密码不正确')
        request.session.clear();request.session.update(owner=True,csrf=secrets.token_urlsafe(32))
        return RedirectResponse('/',303)

    @app.post('/logout')
    def logout(request:Request,csrf:str=Form('')):
        require_csrf(request,csrf);request.session.clear();return RedirectResponse('/login',303)

    @app.get('/')
    def catalogue(request:Request,q:str='',kind:str=''):
        if kind not in ('','ebooks','magazines') or len(q)>100:raise HTTPException(400,'筛选条件不正确')
        with database() as conn:
            books=conn.execute("SELECT * FROM books WHERE (?='' OR kind=?) ORDER BY id DESC LIMIT 200",(kind,kind)).fetchall()
            hits=search(conn,q)
        return render(request,'index.html',books=books,hits=hits[:100],more=len(hits)>100,q=q,kind=kind)

    @app.get('/books/{book_id}')
    def book_detail(request:Request,book_id:int):
        with database() as conn:
            book=conn.execute('SELECT * FROM books WHERE id=?',(book_id,)).fetchone()
            contents=conn.execute('SELECT * FROM book_contents WHERE book_id=? ORDER BY position',(book_id,)).fetchall()
        if not book:raise HTTPException(404,'书刊不存在')
        return render(request,'book.html',book=book,contents=contents)

    @app.get('/books/{book_id}/pages/{page}')
    def page_view(request:Request,book_id:int,page:int):
        with database() as conn:
            row=conn.execute('SELECT b.title,b.pages,p.* FROM pages p JOIN books b ON b.id=p.book_id WHERE book_id=? AND page=?',(book_id,page)).fetchone()
            contents=conn.execute('SELECT * FROM book_contents WHERE book_id=? ORDER BY position',(book_id,)).fetchall()
        if not row:raise HTTPException(404,'页面不存在')
        return render(request,'page.html',row=row,contents=contents)

    @app.get('/books/{book_id}/images/{page}')
    def page_image(book_id:int,page:int):
        if book_id<1 or page<1:raise HTTPException(404)
        with database() as conn:book=conn.execute('SELECT sha256 FROM books WHERE id=? AND pages>=?',(book_id,page)).fetchone()
        path=root()/'previews'/book['sha256']/f'{page}.jpg' if book else None
        if not path or not path.is_file():raise HTTPException(404)
        return FileResponse(path,media_type='image/jpeg')

    @app.get('/settings')
    def settings(request:Request):return render(request,'settings.html',configured=oss.configured(),message='')

    @app.post('/settings')
    def save_settings(request:Request,bucket:str=Form(''),access_id:str=Form(''),access_secret:str=Form(''),csrf:str=Form('')):
        require_csrf(request,csrf)
        try:oss.save_settings(bucket,access_id,access_secret)
        except ValueError as error:return render(request,'settings.html',configured=oss.configured(),message=str(error))
        return RedirectResponse('/sources',303)

    @app.get('/sources')
    def sources(request:Request,kind:str='ebooks',marker:str=''):
        if kind not in ('ebooks','magazines') or len(marker)>1024:raise HTTPException(400)
        if not oss.configured():return RedirectResponse('/settings',303)
        try:items,next_marker=oss.list_sources(kind+'/',marker)
        except Exception:return render(request,'sources.html',items=[],next_marker='',kind=kind,error='无法读取OSS，请核对凭据、Bucket名称和读取权限。')
        with database() as conn:existing={r['object_key'] for r in conn.execute('SELECT object_key FROM books')}
        return render(request,'sources.html',items=items,next_marker=next_marker,kind=kind,existing=existing,error='')

    @app.post('/imports')
    def start_import(request:Request,key:str=Form(''),title:str=Form(''),csrf:str=Form('')):
        require_csrf(request,csrf)
        if not oss.configured():raise HTTPException(400,'请先设置OSS')
        try:job_id=enqueue(key,title)
        except ValueError as error:raise HTTPException(400,str(error))
        return RedirectResponse(f'/jobs/{job_id}',303)

    @app.get('/jobs')
    def jobs(request:Request):
        with database() as conn:
            queue_schema(conn);rows=conn.execute('SELECT * FROM import_jobs ORDER BY id DESC LIMIT 100').fetchall()
        return render(request,'jobs.html',jobs=rows)

    @app.get('/jobs/{job_id}')
    def job_view(request:Request,job_id:int):
        job=get_job(job_id)
        if not job:raise HTTPException(404)
        return render(request,'job.html',job=job)

    @app.get('/books/{book_id}/contents')
    def contents_editor(request:Request,book_id:int):
        with database() as conn:
            book=conn.execute('SELECT * FROM books WHERE id=?',(book_id,)).fetchone()
            entries=conn.execute('SELECT * FROM book_contents WHERE book_id=? ORDER BY position',(book_id,)).fetchall()
        if not book:raise HTTPException(404)
        return render(request,'contents.html',book=book,entries=entries,error='')

    @app.post('/books/{book_id}/contents')
    async def save_contents(request:Request,book_id:int):
        form=await request.form(max_fields=11000)
        require_csrf(request,str(form.get('csrf','')))
        titles=form.getlist('title');pages=form.getlist('page')
        if len(titles)!=len(pages) or len(titles)>5000:raise HTTPException(400,'目录条数不正确')
        entries=[]
        try:
            for title,page in zip(titles,pages):
                title=str(title).strip();page=str(page).strip()
                if not title and not page:continue
                entries.append({'title':title,'page':int(page),'level':1})
            if not entries and form.get('clear')!='1':raise ValueError('如需清空目录，请勾选确认清空')
            replace_contents(book_id,entries)
        except ValueError as error:raise HTTPException(400,str(error))
        return RedirectResponse(f'/books/{book_id}',303)

    @app.post('/books/{book_id}/contents/file')
    async def import_contents_file(request:Request,book_id:int,file:UploadFile=File(...),csrf:str=Form('')):
        require_csrf(request,csrf)
        payload=await file.read(128*1024+1)
        if len(payload)>128*1024:raise HTTPException(413,'目录文件过大')
        try:
            entries=json.loads(payload.decode('utf-8-sig'))
            if not entries:raise ValueError('目录文件为空')
            replace_contents(book_id,entries)
        except (ValueError,UnicodeError):raise HTTPException(400,'目录文件格式或页码不正确，原目录未修改')
        return RedirectResponse(f'/books/{book_id}',303)

    return app
