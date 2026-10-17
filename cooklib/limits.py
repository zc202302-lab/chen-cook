from starlette.responses import PlainTextResponse

class BodyLimit:
    """Bound POST bodies, including chunked requests, before form parsing."""
    def __init__(self,app,max_bytes=128*1024):self.app,self.max_bytes=app,max_bytes
    async def __call__(self,scope,receive,send):
        if scope['type']!='http' or scope['method']!='POST':
            return await self.app(scope,receive,send)
        chunks=[];size=0
        while True:
            message=await receive()
            if message['type']=='http.disconnect':return
            body=message.get('body',b'');size+=len(body)
            if size>self.max_bytes:
                return await PlainTextResponse('提交内容过大',413)(scope,receive,send)
            chunks.append(body)
            if not message.get('more_body',False):break
        pending=True
        async def replay():
            nonlocal pending
            if pending:
                pending=False
                return {'type':'http.request','body':b''.join(chunks),'more_body':False}
            return await receive()
        await self.app(scope,replay,send)
