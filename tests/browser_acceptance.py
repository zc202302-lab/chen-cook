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

def swipe(page, dx, dy=0, multitouch=False):
    """Exercise touch-handler guards without interfering with native browser zoom."""
    page.locator('.page-viewport').evaluate('''(el, args) => {
      const send = (type, touches, changedTouches=[]) => {
        const event = new Event(type, {bubbles:true});
        Object.assign(event, {touches, changedTouches}); el.dispatchEvent(event);
      };
      const start={clientX:160,clientY:200};
      send('touchstart', [start]);
      if(args.multitouch) send('touchmove', [start, {clientX:180,clientY:200}]);
      send('touchend', [], [{clientX:160+args.dx,clientY:200+args.dy}]);
    }''', {'dx':dx,'dy':dy,'multitouch':multitouch})

def reading_layout(page, width):
    page.wait_for_function('document.querySelector("#page-image").complete && document.querySelector("#page-image").naturalWidth>0')
    bounds=page.locator('#page-image').bounding_box()
    assert bounds['y']<=56, (width,bounds)  # Page, not administration, occupies the first screen.
    assert abs(bounds['width']-min(width,960))<=1, (width,bounds)
    assert page.locator('.reader-topbar').bounding_box()['height']<=56
    assert page.locator('.reader-bottom').bounding_box()['height']<=60
    assert page.locator('.site-header').count()==0
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width

with tempfile.TemporaryDirectory() as tmp:
    os.environ.update(COOK_DATA_DIR=tmp,COOK_PASSWORD_HASH=hash_password('browser-test-12345'),COOK_SESSION_SECRET='browser-session-test-'*3,COOK_SECURE_COOKIE='0')
    from cooklib.import_book import import_pdf
    source=Path(tmp)/'test.pdf'
    with fitz.open() as doc:
        for number in range(3):
            leaf=doc.new_page()
            leaf.draw_rect(fitz.Rect(0,0,595,125),color=None,fill=(.13,.37,.27))
            leaf.insert_text((30,80),f'READING DEMO / {number+1}',fontsize=26,color=(1,1,1))
            leaf.insert_text((30,175),'A full-width page, with controls out of the way.',fontsize=16)
            leaf.insert_textbox(fitz.Rect(30,210,565,750),('Method 1: add 150 grams. Keep the original quantity unchanged. Read the next step carefully. '*12),fontsize=13)
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
          for engine in ['chromium','webkit']:
            browser=getattr(p,engine).launch()
            for width in [320,390,768,1440]:
                context=browser.new_context(viewport={'width':width,'height':700 if width<700 else 900},has_touch=width<700,is_mobile=width<700)
                page=context.new_page();page.goto(f'http://127.0.0.1:{port}/')
                errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
                assert page.url.endswith('/login')
                page.get_by_label('登录密码').fill('browser-test-12345')
                page.get_by_role('button',name='登录',exact=True).click()
                page.wait_for_url(f'http://127.0.0.1:{port}/')
                page.get_by_role('link',name='测试样刊',exact=True).click()
                page.get_by_role('link',name='P8 测试章节 PDF 2',exact=True).click()
                page.wait_for_url('**/pages/2')
                reading_layout(page,width)
                Path('artifacts').mkdir(exist_ok=True)
                page.screenshot(path=f'artifacts/reader-{engine}-{width}.png')
                page.get_by_role('button',name='目录',exact=True).click()
                assert page.get_by_role('dialog',name='章节目录').is_visible()
                assert page.locator('.reader-toc a[aria-current=page]').count()==1
                page.get_by_role('button',name='关闭目录',exact=True).click()
                page.get_by_role('button',name='页码和阅读工具').click()
                page.get_by_role('button',name='放大',exact=True).click()
                assert page.locator('#zoom-label').inner_text()=='125%'
                page.get_by_role('button',name='关闭阅读工具').click()
                assert page.locator('.page-viewport').evaluate('(el)=>el.scrollWidth>el.clientWidth')
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
                swipe(page,-100);assert page.url.endswith('/pages/2')  # Pan, not turn, when zoomed.
                page.get_by_role('button',name='页码和阅读工具').click()
                page.get_by_role('button',name='适合宽度').click()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
                page.get_by_role('button',name='专注阅读 · 隐藏工具栏').click()
                assert not page.locator('.reader-topbar').is_visible()
                assert page.locator('#page-image').bounding_box()['y']==0
                page.get_by_role('button',name='显示工具栏').click()
                reading_layout(page,width)
                swipe(page,-100,100);assert page.url.endswith('/pages/2')  # Diagonal scroll is not a turn.
                swipe(page,-100,multitouch=True);assert page.url.endswith('/pages/2')
                swipe(page,-100);page.wait_for_url('**/pages/3')
                assert page.get_by_text('已是末页',exact=True).is_visible()
                page.locator('a[rel=prev]').click();page.wait_for_url('**/pages/2')
                page.get_by_role('button',name='页码和阅读工具').click()
                page.get_by_label('页码',exact=True).fill('0');page.get_by_role('button',name='前往',exact=True).click()
                assert page.url.endswith('/pages/2')  # Invalid page is rejected by the form.
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
                page.get_by_role('link',name='网页修改目录 PDF 1',exact=True).click()
                assert page.get_by_text('已是首页',exact=True).is_visible()
                page.keyboard.press('ArrowRight');page.wait_for_url('**/pages/2')
                page.get_by_role('link',name='返回书刊详情').click()
                page.get_by_role('link',name='编辑目录',exact=True).click()
                page.get_by_label('章节名称').fill('P8 测试章节');page.get_by_label('实际PDF页码').fill('2')
                page.get_by_role('button',name='保存目录',exact=True).click()
                page.get_by_role('link',name='舒适阅读 · 文字版',exact=True).click()
                page.wait_for_url('**/pages/1?mode=comfort')
                assert page.locator('.flow-page').first.is_visible()
                assert page.locator('#page-image').count()==0
                assert page.locator('.flow-page p').first.evaluate('(el)=>getComputedStyle(el).fontSize')=='20px'
                page.get_by_role('button',name='页码和阅读工具').click()
                page.get_by_role('button',name='放大字号',exact=True).click()
                assert page.locator('#font-size').inner_text()=='22'
                page.get_by_label('行距',exact=True).select_option('2.2')
                page.get_by_label('字体',exact=True).select_option('serif')
                page.get_by_role('button',name='夜间',exact=True).click()
                page.get_by_role('button',name='关闭阅读工具').click()
                page.reload()
                assert page.locator('body').get_attribute('data-theme')=='night'
                assert page.locator('.flow-page p').first.evaluate('(el)=>getComputedStyle(el).fontSize')=='22px'
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
                page.screenshot(path=f'artifacts/comfort-{engine}-{width}.png')
                page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
                page.locator('[data-flow-page="2"]').wait_for()
                page.locator('[data-flow-page="2"]').scroll_into_view_if_needed()
                page.wait_for_url('**/pages/2?mode=comfort')
                assert page.locator('#current-page').inner_text()=='2'
                page.get_by_role('link',name='返回书刊详情').click()
                page.get_by_role('link',name='继续阅读',exact=True).click()
                page.wait_for_url('**/pages/2?mode=comfort')
                page.get_by_role('link',name='原页',exact=True).click()
                page.wait_for_url('**/pages/2')
                reading_layout(page,width)
                page.get_by_role('link',name='返回书刊详情').click()
                page.get_by_role('button',name='退出',exact=True).click()
                page.wait_for_url('**/login');assert not errors,errors;context.close()
            browser.close()
    finally:server.should_exit=True;thread.join(timeout=10)
print('Chromium + WebKit: original reader + comfort typography, themes, continuous flow, progress/mode, TOC, auth: 320/390/768/1440 passed')
