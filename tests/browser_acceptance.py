"""Real standalone login, directory editing and desktop/mobile reader."""
import os
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import fitz
import uvicorn
from playwright.sync_api import sync_playwright
from cooklib.auth import hash_password

with tempfile.TemporaryDirectory() as tmp:
    os.environ.update(COOK_DATA_DIR=tmp,COOK_PASSWORD_HASH=hash_password('browser-test-12345'),COOK_SESSION_SECRET='browser-session-test-'*3,COOK_SECURE_COOKIE='0')
    from cooklib.import_book import import_pdf
    source=Path(tmp)/'test.pdf'
    with fitz.open() as doc:
        for _ in range(3):doc.new_page()
        doc.set_toc([[1,'P8 测试章节',2]]);doc.save(source)
    book,_=import_pdf(source,'magazines/test.pdf','测试样刊',reading_only=True)
    from cooklib.web import create_app
    with socket.socket() as probe:probe.bind(('127.0.0.1',0));port=probe.getsockname()[1]
    server=uvicorn.Server(uvicorn.Config(create_app(),host='127.0.0.1',port=port,log_level='error'))
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    for _ in range(100):
        if server.started:break
        time.sleep(.05)
    assert server.started
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch()
            for width in [320,390,768,1440]:
                context=browser.new_context(viewport={'width':width,'height':900})
                page=context.new_page();page.goto(f'http://127.0.0.1:{port}/')
                assert page.url.endswith('/login')
                page.get_by_label('登录密码').fill('browser-test-12345')
                page.get_by_role('button',name='登录',exact=True).click()
                page.wait_for_url(f'http://127.0.0.1:{port}/')
                page.get_by_role('link',name='测试样刊',exact=True).click()
                page.get_by_role('link',name='P8 测试章节 PDF 2',exact=True).click()
                page.wait_for_url('**/pages/2')
                page.locator('#page-image').wait_for()
                assert page.locator('#page-image').evaluate('(el)=>el.complete && el.naturalWidth>0')
                page.get_by_role('button',name='放大',exact=True).click()
                assert page.locator('#zoom-label').inner_text()=='125%'
                page.get_by_role('button',name='适合宽度').click()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
                page.get_by_label('页码',exact=True).fill('3');page.get_by_role('button',name='前往',exact=True).click()
                page.wait_for_url('**/pages/3');page.reload()
                page.get_by_role('link',name='返回书刊详情').click()
                page.get_by_role('link',name='继续阅读',exact=True).click();page.wait_for_url('**/pages/3')
                page.get_by_role('link',name='返回书刊详情').click()
                page.get_by_role('link',name='编辑目录',exact=True).click()
                page.get_by_label('章节名称').fill('网页修改目录')
                page.get_by_label('实际PDF页码').fill('1')
                page.get_by_role('button',name='保存目录',exact=True).click()
                assert page.get_by_role('link',name='网页修改目录 PDF 1',exact=True).is_visible()
                page.get_by_role('link',name='编辑目录',exact=True).click()
                page.get_by_label('章节名称').fill('P8 测试章节');page.get_by_label('实际PDF页码').fill('2')
                page.get_by_role('button',name='保存目录',exact=True).click()
                page.get_by_role('button',name='退出',exact=True).click()
                page.wait_for_url('**/login');context.close()
            browser.close()
    finally:server.should_exit=True;thread.join(timeout=10)
print('Standalone login, private reader, progress, web TOC editing: 320/390/768/1440 passed')
