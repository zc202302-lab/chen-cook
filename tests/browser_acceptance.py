"""Real Chromium/WebKit acceptance, using synthetic content only."""
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx
from playwright.sync_api import sync_playwright,expect

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
sys.path.insert(0,str(root/'tests'))
from test_reader import package,TOKEN

artifacts=root/'artifacts';artifacts.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    with socket.socket() as socket_:socket_.bind(('127.0.0.1',0));port=socket_.getsockname()[1]
    env={**os.environ,'COOK_READER_DATA':tmp,'COOK_SYNC_TOKEN':TOKEN,'COOK_REVISION':'synthetic-browser-test'}
    process=subprocess.Popen([sys.executable,'-m','uvicorn','server:app','--host','127.0.0.1','--port',str(port)],cwd=root,env=env)
    base=f'http://127.0.0.1:{port}'
    try:
        with httpx.Client(base_url=base,timeout=10) as client:
            for _ in range(100):
                try:
                    if client.get('/health').status_code==200:break
                except httpx.TransportError:pass
                time.sleep(.1)
            else:raise RuntimeError('test server failed to start')
            result=client.post('/api/import',headers={'x-sync-token':TOKEN},files={'file':('synthetic.zip',package(catalog=True))})
            result.raise_for_status();bid=result.json()['id']
        with sync_playwright() as p:
            for name in ('chromium','webkit'):
                browser=getattr(p,name).launch()
                try:
                    for width in (320,390,768,1440):
                        with httpx.Client(base_url=base) as client:
                            client.put('/api/progress/'+bid,json={'block_id':'','bookmarks':[]}).raise_for_status()
                        context=browser.new_context(viewport={'width':width,'height':900})
                        page=context.new_page()
                        page.goto(base)
                        expect(page.locator('.book')).to_have_count(1)
                        for button in ('addButton','tasksNav','editButton','updateButton','quitButton'):
                            expect(page.locator('#'+button)).to_be_hidden()
                        page.locator('.book').click()
                        expect(page.locator('#reader')).to_be_visible()
                        expect(page.locator('.catalog-list li')).to_have_count(2)
                        expect(page.locator('.catalog-list .catalog-pending')).to_have_count(1)
                        expect(page.locator('.catalog-list li').first.locator('.catalog-page')).to_have_text('05')
                        expect(page.locator('#chapterSelect')).to_have_value('0')
                        page.locator('#nextChapter').click()
                        expect(page.locator('#b-title')).to_be_visible()
                        expect(page.locator('#b-catalog')).to_be_hidden()
                        page.locator('#previousChapter').click()
                        expect(page.locator('#b-catalog')).to_be_visible()
                        page.locator('.catalog-list li').first.locator('a').click()
                        expect(page.locator('#b-title')).to_be_in_viewport()
                        expect(page.locator('#chapterSelect')).to_have_value('1')
                        expect(page.locator('.catalog-source pre')).to_have_text('合成菜谱··05\n另一道菜··08')
                        expect(page.locator('.prose p').first).to_have_text('合成原料说明应随屏幕自然换行。')
                        assert '\n' not in page.locator('.prose p').first.text_content()
                        page.locator('#larger').click()
                        assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--font').trim()")=='22px'
                        page.locator('#tocButton').click()
                        page.locator('#tocLinks a',has_text='制作步骤').click()
                        expect(page.locator('#b-steps')).to_be_in_viewport()
                        expect(page.locator('#b-title .block-foot')).to_be_hidden()
                        page.locator('#proofButton').click()
                        page.locator('#b-title .block-foot button').click()
                        page.locator('#proofButton').click()
                        expect(page.locator('#bookmarkLinks a')).to_have_count(1)
                        page.locator('#content figure img').click()
                        expect(page.locator('#imageDialog')).to_be_visible()
                        page.locator('#closeImage').click()
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                        page.screenshot(path=str(artifacts/f'{name}-{width}.png'),full_page=True)
                        page.locator('#back').click()
                        page.locator('#search').fill('合成原料')
                        page.locator('#searchButton').click()
                        expect(page.locator('.search-hit')).to_have_count(1)
                        page.locator('#search').fill('')
                        page.locator('.delete-book').click()
                        expect(page.locator('#deleteBookDialog')).to_be_visible()
                        page.locator('#deleteToken').fill(TOKEN)
                        page.locator('#confirmDeleteBook').click()
                        expect(page.locator('#deleteBookDialog')).not_to_be_visible()
                        expect(page.locator('.book')).to_have_count(0)
                        page.locator('#trashButton').click()
                        expect(page.locator('.trash-row')).to_have_count(1)
                        page.locator('.trash-row button',has_text='恢复').click()
                        expect(page.locator('.book')).to_have_count(1)
                        expect(page.locator('.trash-row')).to_have_count(0)
                        page.locator('#closeTrash').click()
                        with httpx.Client(base_url=base) as client:
                            assert client.get('/api/progress/'+bid).json()['bookmarks']==['title']
                        context.close()
                        print(f'PASS {name} {width}: reading, reflow, TOC, fonts, image, bookmark, search')
                finally:browser.close()
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()

