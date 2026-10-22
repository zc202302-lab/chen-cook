"""Original-PDF catalogue. No rewriting of source text or original files."""
import hashlib
import json
import os
import re
import sqlite3
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import fitz
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field


class Metadata(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    category: str = Field(max_length=40)
    year: str = Field(default='', max_length=4)
    issue: str = Field(default='', max_length=40)


class Article(BaseModel):
    title: str = Field(min_length=1, max_length=240)
    start: int = Field(ge=1)
    end: int = Field(ge=1)
    level: int = Field(default=1, ge=1, le=12)


def mount_catalogue(app, root, token):
    root = Path(root) / 'original-library'
    root.mkdir(parents=True, exist_ok=True)
    files = root / 'files'
    files.mkdir(exist_ok=True)
    dbpath = root / 'catalogue.sqlite3'
    lock = threading.RLock()
    processing = threading.Lock()
    api = APIRouter(prefix='/api/library')

    def db():
        con = sqlite3.connect(dbpath, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute('PRAGMA foreign_keys=ON')
        return con

    with db() as con:
        con.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS books(
          id TEXT PRIMARY KEY, digest TEXT UNIQUE, title TEXT, category TEXT,
          year TEXT, issue TEXT, filename TEXT, pages INTEGER DEFAULT 0,
          status TEXT, detail TEXT DEFAULT '', created REAL,
          empty_pages INTEGER DEFAULT 0, deleted INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS pages(book TEXT, page INTEGER, body TEXT,
          PRIMARY KEY(book,page), FOREIGN KEY(book) REFERENCES books(id));
        CREATE TABLE IF NOT EXISTS articles(
          id TEXT PRIMARY KEY, book TEXT, title TEXT, start INTEGER, end INTEGER,
          level INTEGER, body TEXT, kind TEXT,
          FOREIGN KEY(book) REFERENCES books(id));
        CREATE INDEX IF NOT EXISTS article_book ON articles(book);
        CREATE VIRTUAL TABLE IF NOT EXISTS article_search USING fts5(
          id UNINDEXED, title, body, tokenize='trigram');
        ''')
        con.execute("UPDATE books SET status='queued' WHERE status='indexing'")

    def authorize(request):
        import hmac
        if not hmac.compare_digest(request.headers.get('x-sync-token', ''), token):
            raise HTTPException(403, '请输入书库管理密钥')

    def getbook(bid, deleted=False):
        with db() as con:
            row = con.execute('SELECT * FROM books WHERE id=? AND deleted=?', (bid, int(deleted))).fetchone()
        if not row:
            raise HTTPException(404, '资料不存在')
        return dict(row)

    def public(row):
        return {k:v for k,v in dict(row).items() if k not in ('digest', 'filename')}

    def replace_articles(con, bid, rows, kind):
        con.execute('DELETE FROM article_search WHERE id IN (SELECT id FROM articles WHERE book=?)', (bid,))
        con.execute('DELETE FROM articles WHERE book=?', (bid,))
        for item in rows:
            aid = uuid.uuid4().hex
            body = '\n'.join(r[0] for r in con.execute(
                'SELECT body FROM pages WHERE book=? AND page BETWEEN ? AND ? ORDER BY page',
                (bid, item['start'], item['end'])))
            con.execute('INSERT INTO articles VALUES(?,?,?,?,?,?,?,?)',
                (aid, bid, item['title'], item['start'], item['end'], item.get('level', 1), body, kind))
            con.execute('INSERT INTO article_search VALUES(?,?,?)', (aid, item['title'], body))

    def index(bid):
        # One document at a time keeps rendering/extraction within server memory limits.
        with processing:
            with db() as con:
                con.execute("UPDATE books SET status='indexing', detail='' WHERE id=?", (bid,))
            try:
                with fitz.open(files / (bid + '.pdf')) as doc:
                    if doc.needs_pass or not len(doc):
                        raise ValueError('PDF 已加密或没有页面，请提供可直接打开的文件')
                    count = len(doc)
                    toc = [r for r in doc.get_toc() if 0 < r[2] <= count]
                    empty = 0
                    with db() as con:
                        con.execute('DELETE FROM pages WHERE book=?', (bid,))
                        for i, page in enumerate(doc):
                            body = page.get_text(sort=True)
                            if len(body.strip()) < 12:
                                empty += 1
                            con.execute('INSERT INTO pages VALUES(?,?,?)', (bid, i+1, body))
                        rows = []
                        for i, (level, title, start) in enumerate(toc):
                            end = next((r[2]-1 for r in toc[i+1:] if r[0] <= level and r[2] > start), count)
                            rows.append(dict(title=title[:240], start=start, end=max(start, end), level=min(level, 12)))
                        if not rows:
                            rows = [dict(title=f'原文第 {i+1} 页', start=i+1, end=i+1) for i in range(count)]
                        replace_articles(con, bid, rows, 'embedded' if toc else 'page')
                        detail = (f'{empty} 页文字不足，可能需要 OCR 或为图片页。' if empty else '')
                        if not toc:
                            detail += '未发现内嵌目录，当前按页检索；可在管理中录入文章目录。'
                        con.execute('UPDATE books SET pages=?,status=?,detail=?,empty_pages=? WHERE id=?',
                            (count, 'needs_ocr' if empty else 'ready', detail, empty, bid))
            except Exception as exc:
                detail = str(exc) if isinstance(exc, ValueError) else '文件索引失败，请检查 PDF 后重试'
                with db() as con:
                    con.execute("UPDATE books SET status='error',detail=? WHERE id=?", (detail, bid))

    def queue(bid):
        threading.Thread(target=index, args=(bid,), daemon=True).start()

    def recover():
        with db() as con:
            pending = con.execute("SELECT id FROM books WHERE status='queued' AND deleted=0").fetchall()
        for row in pending:
            queue(row['id'])

    previous_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(application):
        async with previous_lifespan(application):
            recover()
            yield

    app.router.lifespan_context = lifespan

    @api.get('/books')
    def listing(category: str='', year: str='', trash: bool=False):
        with db() as con:
            rows = con.execute('SELECT * FROM books WHERE deleted=? AND (?=\'\' OR category=?) AND (?=\'\' OR year=?) ORDER BY created DESC',
                (int(trash), category, category, year, year)).fetchall()
        return [public(r) for r in rows]

    @api.post('/upload')
    def upload(request: Request, file: UploadFile=File(...), category: str=Form('烹饪书籍'), year: str=Form(''), issue: str=Form('')):
        authorize(request)
        if not file.filename or not file.filename.lower().endswith('.pdf'):
            raise HTTPException(400, '请选择 PDF 文件')
        if len(category)>40 or (year and not re.fullmatch(r'\d{4}', year)) or len(issue)>40:
            raise HTTPException(400, '分类、年份或期号格式错误')
        bid = uuid.uuid4().hex
        path = files / (bid+'.pdf')
        digest = hashlib.sha256()
        try:
            size = 0
            with path.open('wb') as out:
                while chunk := file.file.read(1024*1024):
                    size += len(chunk)
                    if size > 2*1024**3:
                        raise HTTPException(413, '单个 PDF 不能超过 2GB')
                    digest.update(chunk)
                    out.write(chunk)
            with processing, fitz.open(path) as doc:
                if doc.needs_pass or not len(doc):
                    raise HTTPException(400, '文件已加密或没有页面')
            with lock, db() as con:
                previous = con.execute('SELECT id,deleted FROM books WHERE digest=?', (digest.hexdigest(),)).fetchone()
                if previous:
                    raise HTTPException(409, '相同文件已在书库或回收站中')
                title = Path(file.filename.replace('\\', '/')).stem[:240]
                con.execute('INSERT INTO books(id,digest,title,category,year,issue,filename,status,created) VALUES(?,?,?,?,?,?,?,?,?)',
                    (bid, digest.hexdigest(), title, category, year, issue, file.filename[:255], 'queued', time.time()))
        except HTTPException:
            path.unlink(missing_ok=True)
            raise
        except Exception:
            path.unlink(missing_ok=True)
            raise HTTPException(400, '无法读取 PDF 文件')
        queue(bid)
        return {'id':bid, 'status':'queued'}

    @api.get('/books/{bid}')
    def detail(bid: str):
        b = getbook(bid)
        with db() as con:
            rows = con.execute('SELECT id,title,start,end,level,kind FROM articles WHERE book=? ORDER BY start,rowid', (bid,)).fetchall()
        return {**public(b), 'articles':[dict(r) for r in rows]}

    @api.patch('/books/{bid}')
    def edit(bid: str, body: Metadata, request: Request):
        authorize(request)
        getbook(bid)
        if body.year and not re.fullmatch(r'\d{4}', body.year):
            raise HTTPException(400, '年份应为四位数字')
        with db() as con:
            con.execute('UPDATE books SET title=?,category=?,year=?,issue=? WHERE id=?',
                (body.title.strip(), body.category.strip(), body.year, body.issue.strip(), bid))
        return {'ok':True}

    @api.put('/books/{bid}/catalogue')
    def edit_toc(bid: str, body: list[Article], request: Request):
        authorize(request)
        with processing:
            b = getbook(bid)
            if not body or len(body)>5000 or any(a.start>a.end or a.end>b['pages'] for a in body):
                raise HTTPException(400, '目录页码超出 PDF 范围，或文章起止页错误')
            with db() as con:
                replace_articles(con, bid, [a.model_dump() for a in body], 'manual')
        return {'ok':True}

    @api.post('/books/{bid}/reindex')
    def reindex(bid: str, request: Request):
        authorize(request)
        b=getbook(bid)
        if b['status'] in ('indexing','queued'):
            raise HTTPException(409, '正在处理，请稍后')
        with db() as con:
            con.execute("UPDATE books SET status='queued' WHERE id=?", (bid,))
        queue(bid)
        return {'ok':True}

    @api.delete('/books/{bid}')
    def delete(bid: str, request: Request):
        authorize(request)
        b=getbook(bid)
        if b['status'] in ('indexing','queued'):
            raise HTTPException(409, '正在处理，请完成后移入回收站')
        with db() as con:
            con.execute('UPDATE books SET deleted=1 WHERE id=?', (bid,))
        return {'ok':True}

    @api.post('/books/{bid}/restore')
    def restore(bid: str, request: Request):
        authorize(request)
        getbook(bid, deleted=True)
        with db() as con:
            con.execute('UPDATE books SET deleted=0 WHERE id=?', (bid,))
        return {'ok':True}

    @api.get('/books/{bid}/original')
    def original(bid: str):
        getbook(bid)
        return FileResponse(files/(bid+'.pdf'), media_type='application/pdf', filename='original.pdf', content_disposition_type='inline')

    @api.get('/books/{bid}/page/{page}')
    def render(bid: str, page: int, width: int=1400):
        getbook(bid)
        # Image endpoint works in mobile browsers without a native PDF viewer.
        with processing, fitz.open(files/(bid+'.pdf')) as doc:
            if not 1<=page<=len(doc):
                raise HTTPException(404, '页码不存在')
            p=doc[page-1]
            scale=min(max(320,width),2000)/p.rect.width
            if p.rect.height*scale>4000:
                scale=4000/p.rect.height
            png=p.get_pixmap(matrix=fitz.Matrix(scale,scale), alpha=False).tobytes('png')
        return Response(png, media_type='image/png', headers={'Cache-Control':'private, max-age=86400'})

    @api.get('/search')
    def search(q: str='', category: str='', year: str='', book: str='', offset: int=0, limit: int=30):
        q=q.strip()
        if not q or len(q)>160:
            return {'total':0, 'items':[], 'offset':0}
        limit=max(1,min(limit,100));offset=max(0,offset)
        terms=q.split()
        params=[]
        conditions=['b.deleted=0']
        for key,val in [('b.category',category),('b.year',year),('a.book',book)]:
            if val:
                conditions.append(key+'=?');params.append(val)
        # Trigram handles Chinese; short terms use literal LIKE with escaped wildcards.
        for term in terms:
            if len(term)>=3:
                conditions.append('a.id IN (SELECT id FROM article_search WHERE article_search MATCH ?)')
                params.append('"'+term.replace('"','""')+'"')
            else:
                literal=term.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
                conditions.append("(a.title LIKE ? ESCAPE '\\' OR a.body LIKE ? ESCAPE '\\')")
                params.extend(['%'+literal+'%']*2)
        where=' AND '.join(conditions)
        with db() as con:
            total=con.execute('SELECT count(*) FROM articles a JOIN books b ON a.book=b.id WHERE '+where, params).fetchone()[0]
            rows=con.execute('SELECT a.*, b.title AS source,b.category,b.year,b.issue FROM articles a JOIN books b ON a.book=b.id WHERE '+where+
                ' ORDER BY (instr(lower(a.title),lower(?))>0) DESC,b.created DESC,a.start LIMIT ? OFFSET ?',params+[q,limit,offset]).fetchall()
            items=[]
            for row in rows:
                r=dict(row);body=r.pop('body')
                target=terms[0]
                matching=con.execute('SELECT page,body FROM pages WHERE book=? AND page BETWEEN ? AND ? ORDER BY page',
                    (r['book'],r['start'],r['end'])).fetchall()
                found=next((p for p in matching if target.lower() in p['body'].lower()),None)
                text=found['body'] if found else body
                pos=max(0,text.lower().find(target.lower()))
                r['snippet']=('…' if pos>50 else '')+text[max(0,pos-50):pos+170]
                r['page']=found['page'] if found else r['start']
                items.append(r)
        return {'total':total, 'items':items, 'offset':offset, 'limit':limit}

    app.include_router(api)
