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
from test_reader import package,TOKEN,DETAIL_TEXT

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
                    for width in (320,390,768,1440,1920):
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
                        expect(page.locator('#b-detail .reading-subtitle')).to_have_count(4)
                        expect(page.locator('#b-detail .reading-subtitle').first).to_have_text('步骤1熬制汤料')
                        expect(page.locator('#b-detail .reading-list')).to_have_count(2)
                        expect(page.locator('#b-detail .reading-list li')).to_have_count(6)
                        expect(page.locator('#b-detail .recipe-measure',has_text='2.5升')).to_have_count(1)
                        expect(page.locator('#b-detail .recipe-measure',has_text='0.5%')).to_have_count(1)
                        assert page.locator('#b-detail .recipe-measure').first.evaluate("e=>getComputedStyle(e).whiteSpace")=='nowrap'
                        assert ''.join(page.locator('#b-detail .prose').text_content().split())==''.join(DETAIL_TEXT.split())
                        page.locator('#larger').click()
                        assert page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--font').trim()")=='22px'
                        page.locator('#tocButton').click()
                        page.locator('#tocLinks a',has_text='制作步骤').click()
                        expect(page.locator('#b-steps')).to_be_in_viewport()
                        expect(page.locator('#b-title .block-foot')).to_be_hidden()
                        page.locator('#proofButton').click()
                        expect(page.locator('#comparison')).to_be_visible()
                        expect(page.locator('#compareTitle')).to_have_text('识别原文对照')
                        expect(page.locator('#compareBody pre').last).to_have_text(DETAIL_TEXT)
                        expect(page.locator('#b-detail .reading-list li')).to_have_count(6)
                        expect(page.locator('#chapterSelect')).to_have_value('1')
                        expect(page.locator('#b-catalog')).to_be_hidden()
                        expect(page.locator('#b-title .block-foot')).to_be_hidden()
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                        if width>760:
                            boxes=[page.locator(selector).bounding_box() for selector in ('#toc','#content','#comparison')]
                            assert boxes[0]['width']<=180
                            assert boxes[0]['x']+boxes[0]['width']<=boxes[1]['x']
                            assert boxes[1]['x']+boxes[1]['width']<=boxes[2]['x']+1
                            assert boxes[1]['width']>=260
                        page.screenshot(path=str(artifacts/f'{name}-{width}-comparison.png'),full_page=True)
                        # Add a synthetic second page in memory, then exercise actual scroll-follow.
                        page.evaluate("book.page_count=2;book.pages.push({page:2,blocks:[{id:'follow-page',kind:'text',page:2,text:'第二页原文。'.repeat(100)}]});render();navigateToBlock('steps',false)")
                        page.locator('#closeComparison').click()
                        page.locator('#proofButton').click()
                        page.locator('#compareNext').click()
                        expect(page.locator('#comparePage')).to_have_value('2')
                        expect(page.locator('#compareBody pre')).to_have_text('第二页原文。'*100)
                        expect(page.locator('#compareFollow')).not_to_be_checked()
                        page.locator('#comparePrevious').click()
                        expect(page.locator('#comparePage')).to_have_value('1')
                        page.locator('#compareFollow').check()
                        page.evaluate("navigateToBlock('follow-page',false)")
                        expect(page.locator('#comparePage')).to_have_value('2')
                        page.evaluate("navigateToBlock('steps',false)")
                        expect(page.locator('#comparePage')).to_have_value('1')
                        page.evaluate("book.pages.pop();book.page_count=1;render();navigateToBlock('steps',false)")
                        page.locator('#compareFollow').uncheck()
                        page.locator('#compareFollow').check()
                        page.locator('#closeComparison').click()
                        expect(page.locator('#comparison')).to_be_hidden()
                        page.locator('#fontChoice').select_option('serif')
                        assert page.evaluate('document.documentElement.dataset.readingFont')=='serif'
                        page.locator('#fontChoice').select_option('sans')
                        # Native local mode uses the same panel with a real image response.
                        page.route('**/api/books/'+bid+'/original/1',lambda route:route.fulfill(status=200,content_type='image/svg+xml',body='<svg xmlns="http://www.w3.org/2000/svg" width="600" height="840"><rect width="600" height="840" fill="#ede7d9"/><text x="40" y="80" font-size="32">SYNTHETIC SOURCE PAGE</text></svg>'))
                        page.evaluate("config.mode='local'")
                        page.locator('#proofButton').click()
                        expect(page.locator('#compareTitle')).to_have_text('原 PDF 对照')
                        expect(page.locator('#compareBody img')).to_be_visible()
                        page.locator('#compareBody img').click()
                        expect(page.locator('#imageDialog')).to_be_visible()
                        page.locator('#closeImage').click()
                        page.screenshot(path=str(artifacts/f'{name}-{width}-original.png'),full_page=True)
                        page.locator('#closeComparison').click()
                        page.evaluate("config.mode='server';progress.block_id='title'")
                        page.locator('#readingBookmark').click()
                        with httpx.Client(base_url=base) as client:
                            saved_marks=client.get('/api/progress/'+bid).json()['bookmarks']
                            assert len(saved_marks)==1 and saved_marks[0] in ('title','body','image','steps','method','detail')
                        expect(page.locator('#bookmarkLinks a')).to_have_count(1)
                        page.locator('#content figure img').click()
                        expect(page.locator('#imageDialog')).to_be_visible()
                        page.locator('#closeImage').click()
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                        page.locator('#b-detail').scroll_into_view_if_needed()
                        page.screenshot(path=str(artifacts/f'{name}-{width}.png'),full_page=True)
                        with httpx.Client(base_url=base) as client:
                            assert client.get('/api/books/'+bid).json()['pages'][0]['blocks'][-1]['text']==DETAIL_TEXT
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
                            assert client.get('/api/progress/'+bid).json()['bookmarks']==saved_marks
                        context.close()
                        print(f'PASS {name} {width}: reading, reflow, TOC, fonts, image, bookmark, search')
                finally:browser.close()
    finally:
        process.terminate()
        try:process.wait(timeout=10)
        except subprocess.TimeoutExpired:process.kill();process.wait()

