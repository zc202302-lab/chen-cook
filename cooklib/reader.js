'use strict';
(() => {
  const book = document.querySelector('main[data-book]');
  if (!book) return;
  const id = book.dataset.book, total = Number(book.dataset.total);
  const key = 'chen-cooking-reader-v1-' + id;
  const page = Number(book.dataset.page);
  let mode = book.dataset.mode || 'original';
  if (!page) { try { mode = localStorage.getItem(key + '-mode') || mode; } catch (_) {} }
  const target = n => '/books/' + id + '/pages/' + n + (mode === 'comfort' ? '?mode=comfort' : '');
  if (page) {
    try { localStorage.setItem(key, String(page)); localStorage.setItem(key + '-mode', mode); }
    catch (_) { document.querySelector('#reading-status').textContent = '浏览器未允许保存阅读位置。'; }
  } else {
    let saved;
    try { saved = Number(localStorage.getItem(key)); } catch (_) { return; }
    if (Number.isInteger(saved) && saved >= 1 && saved <= total) {
      const link = document.querySelector('#continue-reading');
      link.href = '/books/' + id + '/source.pdf#page=' + saved; link.hidden = false;
      document.querySelector('#saved-position').textContent = '此前网页阅读记录：PDF 第' + saved + '页。原 PDF 内的新进度由浏览器管理。';
    }
    return;
  }
  const jump = document.querySelector('#page-jump');
  jump.addEventListener('submit', e => {
    e.preventDefault();
    const input = jump.querySelector('input'), n = Number(input.value);
    if (input.reportValidity() && Number.isInteger(n) && n >= 1 && n <= total) location.assign(target(n));
  });
  const image = document.querySelector('#page-image');
  const viewport = document.querySelector('.page-viewport');
  const status = document.querySelector('#image-status');
  const retry = document.querySelector('#image-retry');
  if (image) {
  const loaded = () => { status.hidden = true; retry.hidden = true; };
  const failed = () => { status.hidden = false; status.textContent = '原页加载失败，请重试。'; retry.hidden = false; };
  image.addEventListener('load', loaded);
  image.addEventListener('error', failed);
  if (image.complete) image.naturalWidth ? loaded() : failed();
  retry.addEventListener('click', () => {
    status.textContent = '正在加载原页…'; retry.hidden = true; image.src = image.src;
  });
  }
  document.querySelectorAll('[data-dialog]').forEach(button => {
    button.addEventListener('click', () => document.getElementById(button.dataset.dialog).showModal());
  });
  document.querySelectorAll('.reader-sheet').forEach(dialog => {
    dialog.querySelector('[data-close-dialog]').addEventListener('click', () => dialog.close());
    dialog.addEventListener('click', e => {
      const rect = dialog.getBoundingClientRect();
      if (e.target === dialog && (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom)) dialog.close();
    });
  });
  const restore = document.querySelector('#reader-restore');
  document.querySelector('#reader-focus').addEventListener('click', () => {
    document.querySelector('#tools-dialog').close();
    document.body.classList.add('reader-focus'); restore.hidden = false;
  });
  restore.addEventListener('click', () => {
    document.body.classList.remove('reader-focus'); restore.hidden = true;
  });
  if (!image) return;
  let zoom = 100;
  const resize = n => {
    zoom = Math.min(250, Math.max(50, n));
    image.style.width = zoom + '%';
    document.querySelector('#zoom-label').textContent = zoom + '%';
    if (zoom === 100) viewport.scrollLeft = 0;
  };
  document.querySelector('#zoom-in').addEventListener('click', () => resize(zoom + 25));
  document.querySelector('#zoom-out').addEventListener('click', () => resize(zoom - 25));
  document.querySelector('#zoom-reset').addEventListener('click', () => resize(100));

  // Preserve native scrolling/pinch zoom; only deliberate fit-width swipes turn pages.
  let touch = null;
  viewport.addEventListener('touchstart', e => {
    touch = e.touches.length === 1 && zoom === 100 && (!window.visualViewport || window.visualViewport.scale <= 1.01)
      ? {x:e.touches[0].clientX, y:e.touches[0].clientY, time:Date.now()} : null;
  }, {passive:true});
  viewport.addEventListener('touchmove', e => { if (e.touches.length !== 1) touch = null; }, {passive:true});
  viewport.addEventListener('touchcancel', () => { touch = null; }, {passive:true});
  const turn = direction => {
    const link = document.querySelector(direction > 0 ? 'a[rel=next]' : 'a[rel=prev]');
    if (link) location.assign(link.href);
  };
  viewport.addEventListener('touchend', e => {
    const start = touch; touch = null;
    if (!start || e.touches.length || !e.changedTouches.length) return;
    const dx = e.changedTouches[0].clientX - start.x, dy = e.changedTouches[0].clientY - start.y;
    if (Date.now() - start.time < 650 && Math.abs(dx) > 70 && Math.abs(dy) < 45 && Math.abs(dx) > Math.abs(dy) * 2) turn(dx < 0 ? 1 : -1);
  }, {passive:true});
  document.addEventListener('keydown', e => {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey || document.querySelector('dialog[open]') || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName) || e.target.isContentEditable || zoom !== 100) return;
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault(); turn(e.key === 'ArrowRight' ? 1 : -1);
    }
  });
})();
