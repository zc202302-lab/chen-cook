'use strict';
(() => {
  const main = document.querySelector('main[data-mode="comfort"]');
  if (!main) return;
  const id = main.dataset.book, total = Number(main.dataset.total), initial = Number(main.dataset.page);
  const base = '/books/' + id, target = n => base + '/pages/' + n + '?mode=comfort';
  const progressKey = 'chen-cooking-reader-v1-' + id;
  const preferencesKey = 'chen-cook-comfort-v1';
  let preferences = {size:20, spacing:'1.9', font:'sans', theme:'paper'};
  try { Object.assign(preferences, JSON.parse(localStorage.getItem(preferencesKey) || '{}')); } catch (_) {}
  const apply = () => {
    preferences.size = Math.max(16, Math.min(30, Number(preferences.size) || 20));
    if (!['1.6','1.9','2.2'].includes(preferences.spacing)) preferences.spacing = '1.9';
    if (!['sans','serif'].includes(preferences.font)) preferences.font = 'sans';
    if (!['paper','white','night'].includes(preferences.theme)) preferences.theme = 'paper';
    document.body.style.setProperty('--reading-size', preferences.size + 'px');
    document.body.style.setProperty('--reading-leading', preferences.spacing);
    document.body.dataset.theme = preferences.theme;
    document.body.dataset.font = preferences.font;
    document.querySelector('#font-size').textContent = preferences.size;
    document.querySelector('#line-spacing').value = preferences.spacing;
    document.querySelector('#reader-font').value = preferences.font;
    document.querySelectorAll('[data-theme]').forEach(button => {
      if (button.tagName === 'BUTTON') button.setAttribute('aria-pressed', String(button.dataset.theme === preferences.theme));
    });
    document.querySelector('#font-smaller').disabled = preferences.size <= 16;
    document.querySelector('#font-larger').disabled = preferences.size >= 30;
    try { localStorage.setItem(preferencesKey, JSON.stringify(preferences)); } catch (_) {}
  };
  document.querySelector('#font-smaller').addEventListener('click', () => { preferences.size -= 2; apply(); });
  document.querySelector('#font-larger').addEventListener('click', () => { preferences.size += 2; apply(); });
  document.querySelector('#line-spacing').addEventListener('change', e => { preferences.spacing = e.target.value; apply(); });
  document.querySelector('#reader-font').addEventListener('change', e => { preferences.font = e.target.value; apply(); });
  document.querySelectorAll('button[data-theme]').forEach(button => button.addEventListener('click', () => { preferences.theme = button.dataset.theme; apply(); }));
  apply();

  const pages = document.querySelector('#flow-pages'), more = document.querySelector('#flow-more'), status = document.querySelector('#flow-status');
  let last = initial, current = initial, busy = false, paused = false;
  const mark = n => {
    if (n === current) return;
    current = n;
    document.querySelector('#current-page').textContent = n;
    document.querySelector('#jump-number').value = n;
    document.querySelector('#reading-mode').href = base + '/pages/' + n;
    history.replaceState(null, '', target(n));
    try { localStorage.setItem(progressKey, String(n)); } catch (_) {}
    for (const [rel, destination, label] of [['prev', n-1, '‹ 上一页'], ['next', n+1, '下一页 ›']]) {
      let link = document.querySelector('a[rel=' + rel + ']');
      let boundary = document.querySelector('.flow-' + rel + '-bound');
      const valid = destination >= 1 && destination <= total;
      if (!link && valid) {
        link = document.createElement('a'); link.rel = rel; link.textContent = label;
        boundary.replaceWith(link);
      }
      if (link) { link.href = target(destination); link.hidden = !valid; }
      if (!valid && !boundary) {
        boundary = document.createElement('span'); boundary.className = 'flow-' + rel + '-bound';
        boundary.setAttribute('aria-disabled', 'true'); boundary.textContent = rel === 'prev' ? '已是首页' : '已是末页';
        link.after(boundary);
      }
      if (boundary) boundary.hidden = valid;
    }
  };
  const add = payload => {
    const section = document.createElement('section'); section.className = 'flow-page'; section.dataset.flowPage = payload.page;
    const label = document.createElement('div'); label.className = 'flow-page-label';
    const number = document.createElement('span'); number.textContent = 'PDF 第 ' + payload.page + ' 页';
    const original = document.createElement('a'); original.href = base + '/pages/' + payload.page; original.textContent = '对照原页';
    label.append(number, original); section.append(label);
    for (const block of payload.blocks) {
      const element = document.createElement(block.kind === 'heading' ? 'h2' : 'p'); element.textContent = block.text;
      if (block.uncertain) { element.className = 'uncertain'; element.title = '识别存疑，请核对原页'; }
      section.append(element);
    }
    if (!payload.blocks.length) {
      const empty = document.createElement('p'); empty.className = 'flow-empty'; empty.textContent = '本页没有可重排文字，请对照原页。'; section.append(empty);
    }
    pages.append(section);
  };
  const load = async () => {
    if (busy || last >= total) return;
    busy = true; more.disabled = true; status.textContent = '正在载入下一页文字…';
    try {
      const response = await fetch(base + '/flow/' + (last+1), {headers:{Accept:'application/json'}});
      if (response.redirected) { paused = true; status.textContent = '登录已过期，请返回书刊重新登录。'; return; }
      if (!response.ok) throw new Error('load');
      const payload = await response.json();
      if (payload.page !== last+1 || !Array.isArray(payload.blocks)) throw new Error('page');
      add(payload); last = payload.page; status.textContent = last === total ? '已到全书末尾' : '';
      paused = payload.blocks.map(block => block.text).join('').length < 30;
    } catch (_) { paused = true; status.textContent = '载入失败，请点击重试。'; }
    finally { busy = false; more.disabled = false; more.hidden = last >= total; }
  };
  more.hidden = last >= total;
  more.addEventListener('click', () => { paused = false; load(); });
  let scheduled = false;
  const position = () => {
    scheduled = false;
    if (document.querySelector('dialog[open]')) return;
    let visible = initial;
    for (const section of pages.children) {
      if (section.getBoundingClientRect().top <= innerHeight * .35) visible = Number(section.dataset.flowPage);
      else break;
    }
    mark(visible);
    if (!paused && more.getBoundingClientRect().top < innerHeight + 300) load();
  };
  window.addEventListener('scroll', () => { if (!scheduled) { scheduled = true; requestAnimationFrame(position); } }, {passive:true});
})();
