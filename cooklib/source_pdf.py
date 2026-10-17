"""Stream the original private OSS PDF unchanged; never render or store a copy."""
import re
from email.utils import formatdate
from urllib.parse import quote
from fastapi import HTTPException
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask
from . import oss


def byte_range(value, size):
    if not value:return None
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',value.strip())
    if not match or not any(match.groups()):raise ValueError('range')
    left,right=match.groups()
    if left:
        start=int(left);end=min(int(right),size-1) if right else size-1
    else:
        suffix=int(right)
        if suffix<=0:raise ValueError('range')
        start=max(0,size-suffix);end=size-1
    if not 0<=start<=end<size:raise ValueError('range')
    return start,end


def original_response(request, book):
    key=book['object_key']
    if not oss.valid_key(key):raise HTTPException(400,'源文件路径不正确')
    try:
        bucket=oss.bucket_client()
        metadata=bucket.head_object(key)
        size=metadata.content_length
        if not isinstance(size,int) or size<=0:raise ValueError('size')
    except Exception:
        raise HTTPException(502,'暂时无法读取原 PDF，请核对OSS设置和源文件是否存在。') from None
    headers={'Accept-Ranges':'bytes','Content-Disposition':f"inline; filename=book-{book['id']}.pdf; filename*=UTF-8''{quote(book['title']+'.pdf',safe='')}",'Content-Type':'application/pdf'}
    etag=getattr(metadata,'etag','')
    if isinstance(etag,str) and re.fullmatch(r'[A-Za-z0-9._-]{1,200}',etag):headers['ETag']='"'+etag+'"'
    modified=getattr(metadata,'last_modified',None)
    if isinstance(modified,(float,int)):
        headers['Last-Modified']=formatdate(modified,usegmt=True)
    selection=None
    # HEAD describes the full representation; Range is a GET-only request field.
    if request.method=='GET':
        value=request.headers.get('range','')
        validator=request.headers.get('if-range')
        if validator and validator not in (headers.get('ETag'),headers.get('Last-Modified')):value=''
        try:selection=byte_range(value,size)
        except ValueError:
            return Response(status_code=416,headers={**headers,'Content-Range':f'bytes */{size}'})
    start,end=selection if selection else (0,size-1)
    headers['Content-Length']=str(end-start+1)
    if selection:headers['Content-Range']=f'bytes {start}-{end}/{size}'
    if request.method=='HEAD':return Response(headers=headers)
    try:
        upstream=bucket.get_object(key,byte_range=selection,headers={'If-Match':headers['ETag']} if 'ETag' in headers else None)
    except Exception:
        raise HTTPException(502,'原 PDF 读取失败，请刷新重试。') from None
    def chunks():
        try:
            remaining=end-start+1
            while remaining:
                chunk=upstream.read(min(256*1024,remaining))
                if not chunk:raise RuntimeError('Source PDF stream ended early')
                remaining-=len(chunk)
                yield chunk
        finally:upstream.close()
    return StreamingResponse(chunks(),status_code=206 if selection else 200,headers=headers,background=BackgroundTask(upstream.close))
