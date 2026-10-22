"""Full browser acceptance of the original-PDF library, synthetic source only."""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright, expect

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
sys.path.insert(0,str(root/'tests'))
from test_catalogue import synthetic_pdf,TOKEN

artifacts=root/'artifacts';artifacts.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    env={**os.environ,'COOK_READER_DATA':directory,'COOK_SYNC_TOKEN':TOKEN}
    process=subprocess.Popen([sys.executable,'-m','uvicorn','server:app','--host','127.0.0.1','--port',str(port)],cwd=root,env=env)
    base=f'http://127.0.0.1:{port}'
    try:
        with httpx.Client(base_url=base) as client:
            for _ in range(100):
                try:
                    if client.get('/health').status_code==200:break
                except httpx.TransportError:pass
                time.sleep(.1)
            else:raise RuntimeError('Server did not start')
            response=client.post('/api/library/upload',headers={'x-sync-token':TOKEN},files={'file':('合成阅读样书.pdf',synthetic_pdf())},data={'category':'烹饪杂志','year':'2026'})
            response.raise_for_status();bid=response.json()['id']
            for _ in range(100):
                if client.get('/api/library/books/'+bid).json()['status']=='ready':break
                time.sleep(.05)
            else:raise RuntimeError('Index failed')
        with sync_playwright() as p:
            for name in ('chromium','webkit'):
                browser=getattr(p,name).launch()
                try:
                    for width in (320,390,768,1440):
                        context=browser.new_context(viewport={'width':width,'height':900})
                        page=context.new_page();errors=[]
                        page.on('pageerror',lambda error:errors.append(str(error)))
                        page.goto(base)
                        expect(page.locator('.book-card')).to_have_count(1)
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                        page.screenshot(path=str(artifacts/f'library-home-{name}-{width}.png'),full_page=True)
                        page.get_by_label('搜索知识').fill('保管注意事项')
                        page.locator('#searchForm').get_by_role('button').click()
                        expect(page.locator('.result')).to_have_count(1)
                        expect(page.locator('.result .source')).to_contain_text('合成阅读样书')
                        page.locator('.result .text-button').click()
                        expect(page.locator('#pageNumber')).to_have_value('4')
                        expect(page.locator('#originalPage')).to_be_visible()
                        page.wait_for_function('document.querySelector("#originalPage").naturalWidth>0')
                        if width<=800:page.locator('#tocToggle').click()
                        page.locator('[data-toc-page="2"]').click()
                        expect(page.locator('#pageNumber')).to_have_value('2')
                        page.locator('#nextPage').click()
                        expect(page.locator('#pageNumber')).to_have_value('3')
                        page.locator('#zoomIn').click()
                        assert page.locator('#originalPage').evaluate('e=>e.style.getPropertyValue("--page-width")')=='125%'
                        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
                        page.screenshot(path=str(artifacts/f'library-reader-{name}-{width}.png'),full_page=True)
                        page.locator('#back').click()
                        page.locator('#manage').click()
                        page.locator('#key').fill(TOKEN)
                        page.locator('[data-trash]').click()
                        expect(page.locator('#managedBooks')).to_contain_text('暂无资料')
                        page.locator('#showTrash').click()
                        page.locator('[data-restore]').click()
                        page.locator('#showActive').click()
                        expect(page.locator('.managed-book')).to_have_count(1)
                        page.locator('#closeManager').click()
                        expect(page.locator('.book-card')).to_have_count(1)
                        assert not errors,errors
                        context.close()
                finally:browser.close()
    finally:
        process.terminate();process.wait(timeout=10)
