"""Chen Cook original-PDF library service."""
import json
import os
import secrets
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from catalogue import mount_catalogue


def create_app(data=None):
    root = Path(data or os.environ.get('COOK_READER_DATA', '/var/lib/chen-cook/reader')).resolve()
    root.mkdir(parents=True, exist_ok=True)
    token = os.environ.get('COOK_SYNC_TOKEN', '')
    if not token:
        path = root / 'sync-token'
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as stream:
                stream.write(secrets.token_urlsafe(32))
        except FileExistsError:
            pass
        token = path.read_text().strip()
        if not token:
            raise RuntimeError('管理密钥文件为空，请在服务器修复后重启')
    source = Path(__file__).parent
    version = json.loads((source / 'version.json').read_text())['version']
    revision = os.environ.get('COOK_REVISION', 'development')
    app = FastAPI(title='灶间书房 · 原文资料库', docs_url=None, redoc_url=None)
    app.state.root = root

    @app.middleware('http')
    async def protect(request, call_next):
        if request.method not in ('GET', 'HEAD', 'OPTIONS'):
            origin = request.headers.get('origin')
            if origin and urlsplit(origin).netloc.lower() != request.headers.get('host', '').lower():
                return JSONResponse({'detail': '不接受跨站写入请求'}, 403)
        result = await call_next(request)
        if request.url.path in ('/', '/index.html') or request.url.path.startswith('/library/'):
            result.headers['Cache-Control'] = 'no-cache'
        result.headers['X-Content-Type-Options'] = 'nosniff'
        result.headers['Referrer-Policy'] = 'same-origin'
        result.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        return result

    @app.get('/health')
    def health():
        # The installed deployment supervisor expects mode=reader.
        return dict(ok=True, service='chen-cook', mode='reader', library=True,
                    version=version, revision=revision)

    mount_catalogue(app, root, token)

    @app.get('/')
    @app.get('/index.html')
    def library_home():
        return FileResponse(source / 'web/library/index.html')

    app.mount('/library', StaticFiles(directory=source / 'web/library', html=True), name='library')
    return app
