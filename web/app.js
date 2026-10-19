const $=id=>document.getElementById(id);
let proofing=false;
let config,book,editing=false,progress={},font=Number(localStorage.getItem('font')||21),observer,cropPage,cropRect,dragStart,toastTimer;
document.documentElement.style.setProperty('--font',font+'px');
const el=(tag,cls,text)=>{let n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n};
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,6500)}
async function api(path,opts={}){const r=await fetch(path,{...opts,headers:{...(opts.body instanceof FormData?{}:{'Content-Type':'application/json'}),...opts.headers}});if(!r.ok){let msg;try{msg=(await r.json()).detail}catch{msg='请求失败：'+r.status}throw Error(typeof msg==='string'?msg:JSON.stringify(msg))}return r.json()}
function safe(fn){return async(...args)=>{try{await fn(...args)}catch(e){toast(e.message)}}}
function asset(src){return `/api/books/${book.id}/assets/${encodeURIComponent(src)}`}
async function shelf(){if(editing&&!confirm('退出会丢失未保存的编辑，继续吗？'))return;editing=false;observer?.disconnect();book=null;$('home').hidden=false;$('reader').hidden=true;const books=await api('/api/books');$('bookCount').textContent=books.length+' 本';$('books').replaceChildren();if(!books.length)$('books').append(el('div','empty','书架还没有书。从电脑工作台转换 PDF，或导入已转换的阅读包。'));for(const b of books){const card=el('button','book');const cover=el('div','cover');if(b.cover){const img=el('img');img.src=`/api/books/${b.id}/assets/${encodeURIComponent(b.cover)}`;img.alt=b.title;img.loading='lazy';cover.append(img)}else cover.append(el('span','title-cover',b.title));card.append(cover,el('h3','',b.title),el('p','',`${b.pages} / ${b.page_count} 页 · ${b.pending?'有待核对内容':'已核对'}`));card.onclick=safe(()=>openBook(b.id));$('books').append(card)}}
async function openBook(id,anchor){if(editing&&!confirm('放弃未保存的修改？'))return;editing=false;observer?.disconnect();book=await api('/api/books/'+id);progress=await api('/api/progress/'+id);$('home').hidden=true;$('reader').hidden=false;$('readingTitle').textContent=book.title;$('editButton').textContent='核对编辑';render();requestAnimationFrame(()=>{const target=anchor||progress.block_id;if(target)document.getElementById('b-'+target)?.scrollIntoView();else window.scrollTo(0,0)});}
function allBlocks(){return book.pages.flatMap(p=>p.blocks)}
function anchorLink(b,label){const a=el('a','',label);a.href='#b-'+b.id;a.onclick=e=>{e.preventDefault();document.getElementById('b-'+b.id)?.scrollIntoView({behavior:'smooth'});$('toc').classList.remove('open')};return a}
function catalogFor(block){const c=block.catalog;return c&&c.text_snapshot===block.text&&Array.isArray(c.rows)?c:null}
function catalogItem(row,sidebar=false){
 const item=el(sidebar?'div':'li',sidebar?'catalog-nav-row':'catalog-row');
 if(!row.title){if(!sidebar)item.append(el('p','catalog-unresolved',row.raw));return item}
 const target=row.target_id&&allBlocks().find(b=>b.id===row.target_id);
 const title=target?anchorLink(target,row.title):el('span','',row.title);
 item.append(title);
 if(!sidebar)item.append(el('span','catalog-page',row.printed_page));
 if(!target)item.append(el('small','catalog-pending','待定位'));
 return item;
}
function renderToc(){
 const list=$('tocLinks');list.replaceChildren();
 const blocks=allBlocks(),hasCatalog=blocks.some(b=>catalogFor(b)),linked=new Set();
 if(hasCatalog){
  for(const b of blocks){
   const c=catalogFor(b);
   if(c){for(const row of c.rows){if(row.title)list.append(catalogItem(row,true));if(row.target_id)linked.add(row.target_id)}}
   else if(b.role==='chapter')list.append(anchorLink(b,b.text));
  }
 }
 const headings=blocks.filter(b=>b.role!=='page_furniture'&&!catalogFor(b)&&(b.kind==='heading'||b.role==='recipe')&&!linked.has(b.id)&&b.role!=='chapter');
 if(headings.length&&hasCatalog)list.append(el('div','toc-head','正文标题'));
 for(const b of headings){const a=anchorLink(b,b.text||'未命名标题');a.style.paddingLeft=(Number(b.level||2)-1)*12+'px';list.append(a)}
 if(!list.children.length)list.append(el('p','muted','暂未识别到标题，可在核对编辑中设置。'));
 $('bookmarkLinks').replaceChildren();
 for(const id of progress.bookmarks||[]){const b=blocks.find(x=>x.id===id);if(b)$('bookmarkLinks').append(anchorLink(b,(b.text||b.caption||'图片').slice(0,25)))}
}
// Reflow only the presentation: stored OCR text and editor contents remain unchanged.
function readingParagraphs(text){
 const paragraphs=[];
 const structural=/^(?:步骤\s*\d+|[一二三四五六七八九十]+[、．.]|[（(]\d+[）)]|\d+[、．.](?!\d)|(?:原料|辅料|调料|制作关键|使用贴士|制作方法|制作步骤)[：:])/;
 let current='';
 const flush=()=>{if(current)paragraphs.push(current);current=''};
 for(const raw of String(text||'').replace(/\r\n?/g,'\n').split('\n')){
  const line=raw.trim();
  if(!line){flush();continue}
  if(current&&structural.test(line))flush();
  if(current&&/[A-Za-z0-9]$/.test(current)&&/^[A-Za-z0-9]/.test(line))current+=' ';
  current+=line;
 }
 flush();return paragraphs;
}
function readingText(block){
 const node=el('div','prose');
 const catalog=catalogFor(block);
 if(catalog){
  const rows=el('ol','catalog-list');for(const row of catalog.rows)rows.append(catalogItem(row));node.append(rows);
  const details=el('details','catalog-source');details.append(el('summary','','查看识别原文'));details.append(el('pre','',block.text));node.append(details);return node;
 }
 for(const paragraph of readingParagraphs(block.text))node.append(el('p','',paragraph));
 return node;
}
function render(){document.body.classList.toggle('proof-mode',proofing||editing);$('content').classList.add('book-edition');renderToc();const content=$('content');content.replaceChildren();content.append(el('h1','',book.title));content.append(el('div','notice','自动转换初稿：未核对标记表示文字、顺序或图文归属尚未确认。目录条目会与正文标题匹配；待定位条目不猜测跳转。可在电脑工作台整理结构并核对。'));if(editing){const bar=el('div','save-strip');bar.append(el('span','','修改后请保存，原文不会被自动润色。'));let btn=el('button','primary','保存修改');btn.onclick=safe(save);bar.append(btn);content.append(bar);const title=el('input');title.value=book.title;title.setAttribute('aria-label','书名');title.oninput=()=>book.title=title.value;title.style.width='100%';content.append(title)}for(const pg of book.pages){if(!pg.blocks.length)continue;for(const b of pg.blocks){const wrap=el('section',editing?'block editbox':'block');wrap.id='b-'+b.id;wrap.dataset.block=b.id;wrap.dataset.role=b.role||b.kind;if(editing){const controls=el('div','edit-controls');const kind=el('select');for(const [value,text] of [['text','正文'],['heading','目录标题'],['image','图片']]){if((b.kind==='image')!==(value==='image'))continue;let o=el('option','',text);o.value=value;kind.append(o)}kind.value=b.kind;kind.onchange=()=>{b.kind=kind.value;delete b.role;delete b.catalog;render()};controls.append(kind);if(b.kind==='heading'){const level=el('select');for(let i=1;i<=3;i++){const o=el('option','','目录 '+i+' 级');o.value=i;level.append(o)}level.value=b.level||2;level.onchange=()=>{b.level=+level.value;renderToc()};controls.append(level)}const check=el('input');check.type='checkbox';check.checked=!!b.reviewed;check.onchange=()=>b.reviewed=check.checked;let label=el('label','','已对照核对 ');label.prepend(check);controls.append(label);for(const [label,delta] of [['↑',-1],['↓',1]]){const btn=el('button','',label);btn.title='移动内容块（可跨页）';btn.onclick=()=>move(b.id,delta);controls.append(btn)}const del=el('button','','删除');del.onclick=()=>{if(confirm('确认删除此内容块？')){pg.blocks=pg.blocks.filter(x=>x.id!==b.id);render()}};controls.append(del);wrap.append(controls);if(b.kind==='image'){const img=el('img');img.src=asset(b.src);img.alt=b.caption||'待核对裁图';wrap.append(img);const caption=el('textarea');caption.value=b.caption||'';caption.placeholder='原文图注（不要新增原文没有的说明）';caption.oninput=()=>b.caption=caption.value;wrap.append(caption)}else{const text=el('textarea');text.value=b.text;text.oninput=()=>{b.text=text.value;renderToc()};wrap.append(text);const split=el('button','','在光标处拆分');split.onclick=()=>{const pos=text.selectionStart;if(pos<=0||pos>=b.text.length)return;const n={...b,id:crypto.randomUUID().replaceAll('-','').slice(0,16),text:b.text.slice(pos),reviewed:false};b.text=b.text.slice(0,pos);pg.blocks.splice(pg.blocks.indexOf(b)+1,0,n);render()};wrap.append(split)}}else if(b.kind==='image'){const figure=el('figure');const img=el('img');img.src=asset(b.src);img.alt=b.caption||'菜谱配图';img.loading='lazy';img.onclick=()=>{$('largeImage').src=img.src;$('imageDialog').showModal()};figure.append(img);if(b.caption)figure.append(el('figcaption','',b.caption));wrap.append(figure)}else if(catalogFor(b))wrap.append(readingText(b));else if(b.role==='recipe'||b.role==='subheading')wrap.append(el(b.role==='recipe'?'h2':'h3','',b.text));else if(b.kind==='text')wrap.append(readingText(b));else wrap.append(el(Number(b.level||2)===3?'h3':'h2','',b.text));const foot=el('div','block-foot');foot.append(el('span','',`来源第 ${b.page} 页`));if(!b.reviewed)foot.append(el('span','pending','待核对'));if(config.mode==='local'){const original=el('button','','对照原页 / 裁图');original.onclick=safe(()=>showOriginal(b.page));foot.append(original)}if(!editing){const mark=el('button','',(progress.bookmarks||[]).includes(b.id)?'★ 已收藏':'☆ 书签');mark.onclick=safe(async()=>{const marks=new Set(progress.bookmarks||[]);marks.has(b.id)?marks.delete(b.id):marks.add(b.id);progress.bookmarks=[...marks];await persistProgress();renderToc();mark.textContent=marks.has(b.id)?'★ 已收藏':'☆ 书签'});foot.append(mark)}wrap.append(foot);content.append(wrap)}}connectReadingFlow();buildChapterNavigation();if(!editing){observer?.disconnect();observer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){progress.block_id=e.target.dataset.block;clearTimeout(window.progressTimer);window.progressTimer=setTimeout(()=>persistProgress().catch(()=>{}),800)}},{rootMargin:'-10% 0px -65% 0px'});content.querySelectorAll('.block').forEach(n=>observer.observe(n))}}
function move(id,delta){const flat=allBlocks(),i=flat.findIndex(x=>x.id===id),j=i+delta;if(j<0||j>=flat.length)return;const b=flat[i],target=flat[j],from=book.pages.find(p=>p.blocks.includes(b)),to=book.pages.find(p=>p.blocks.includes(target));from.blocks.splice(from.blocks.indexOf(b),1);to.blocks.splice(to.blocks.indexOf(target)+(delta>0?1:0),0,b);render();document.getElementById('b-'+id)?.scrollIntoView({block:'center'})}
async function save(){book=await api('/api/books/'+book.id,{method:'PUT',body:JSON.stringify(book)});toast('修改已保存');render()}
async function persistProgress(){if(book)await api('/api/progress/'+book.id,{method:'PUT',body:JSON.stringify(progress)})}
async function jobs(){if(config.mode!=='local')return;const data=await api('/api/jobs');$('jobList').replaceChildren();for(const j of data){const row=el('div','job');let head=el('div','job-head');head.append(el('strong','',j.title));const labels={queued:'排队中',running:'处理中',paused:'已暂停',done:'转换完成 · 待核对',failed:'处理失败'};head.append(el('span','muted',labels[j.status]));row.append(head);const p=el('progress');p.max=j.total;p.value=j.done;row.append(p,el('div','muted',`${j.done} / ${j.total} 页`));if(j.error)row.append(el('p','error',j.error));const actions=el('div','edit-controls');if(j.status==='running'||['paused','failed'].includes(j.status)){const btn=el('button','',j.status==='running'?'暂停（当前页结束后）':'继续 / 重试');btn.onclick=safe(async()=>{await api(`/api/jobs/${j.id}/${j.status==='running'?'pause':'resume'}`,{method:'POST'});await jobs()});actions.append(btn)}if(j.done){const read=el('button','','打开初稿');read.onclick=safe(()=>openBook(j.book_id));actions.append(read)}row.append(actions);$('jobList').append(row)}}
async function showOriginal(page){cropPage=page;cropRect=null;$('cropBox').hidden=true;$('originalTitle').textContent=`原 PDF · 第 ${page} 页`;$('originalImage').src=`/api/books/${book.id}/original/${page}`;$('cropHint').textContent=editing?'拖动框选要保留的图片。添加后关闭窗口并保存修改。':'对照原文；如需补充裁图，请先进入“核对编辑”。';$('addCrop').hidden=!editing;$('originalDialog').showModal()}
function point(e){const r=$('originalImage').getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))]}
$('originalWrap').onpointerdown=e=>{if(!editing)return;dragStart=point(e);$('originalWrap').setPointerCapture(e.pointerId);e.preventDefault()};
$('originalWrap').onpointermove=e=>{if(!dragStart)return;const end=point(e);cropRect=[Math.min(dragStart[0],end[0]),Math.min(dragStart[1],end[1]),Math.max(dragStart[0],end[0]),Math.max(dragStart[1],end[1])];const [x,y,x2,y2]=cropRect;Object.assign($('cropBox').style,{left:x*100+'%',top:y*100+'%',width:(x2-x)*100+'%',height:(y2-y)*100+'%'});$('cropBox').hidden=false};
$('originalWrap').onpointerup=()=>dragStart=null;
$('addCrop').onclick=safe(async()=>{if(!cropRect||cropRect[2]-cropRect[0]<.01||cropRect[3]-cropRect[1]<.01)throw Error('请先拖动框选图片');const b=await api('/api/books/'+book.id+'/crop',{method:'POST',body:JSON.stringify({page:cropPage,box:cropRect})});let pg=book.pages.find(p=>p.page===cropPage);if(!pg)throw Error('该页未转换');pg.blocks.push(b);render();toast('裁图已添加到该页末尾，可调整顺序；请保存修改')});
$('closeOriginal').onclick=()=>$('originalDialog').close();$('closeImage').onclick=()=>$('imageDialog').close();
$('shelfNav').onclick=safe(shelf);$('back').onclick=safe(shelf);$('tasksNav').onclick=safe(async()=>{await shelf();$('tasks').hidden=false;await jobs();$('tasks').scrollIntoView()});$('refreshTasks').onclick=safe(jobs);
$('addButton').onclick=()=>$('addDialog').showModal();$('pickFiles').onclick=safe(async()=>{const r=await api('/api/pick',{method:'POST'});$('paths').value=r.paths.join('\n')});
$('startJobs').onclick=safe(async()=>{const btn=$('startJobs');btn.disabled=true;try{const paths=$('paths').value.split('\n').map(x=>x.trim().replace(/^"|"$/g,'')).filter(Boolean);await api('/api/jobs',{method:'POST',body:JSON.stringify({paths,pages:$('pageSpec').value})});$('addDialog').close();$('tasks').hidden=false;await jobs();await shelf();toast('任务已加入。可在转换工作台查看进度。')}finally{btn.disabled=false}});
$('editButton').onclick=safe(async()=>{if(editing){await save();editing=false}else{editing=true;observer?.disconnect()}$('editButton').textContent=editing?'保存并结束编辑':'核对编辑';render()});
$('tocButton').onclick=()=>$('toc').classList.toggle('open');$('closeToc').onclick=()=>$('toc').classList.remove('open');
function resize(delta){font=Math.max(16,Math.min(34,font+delta));document.documentElement.style.setProperty('--font',font+'px');localStorage.setItem('font',font)}$('smaller').onclick=()=>resize(-1);$('larger').onclick=()=>resize(1);$('themeButton').onclick=()=>document.body.classList.toggle('sage');
$('exportButton').onclick=()=>{if(editing){toast('请先保存并结束编辑');return}location.href=`/api/books/${book.id}/export`};
$('syncButton').onclick=()=>{if(editing){toast('请先保存并结束编辑');return}$('siteUrl').value=localStorage.getItem('siteUrl')||'';$('syncDialog').showModal()};
$('doSync').onclick=safe(async()=>{const btn=$('doSync');btn.disabled=true;btn.textContent='上传中…';try{await api(`/api/books/${book.id}/sync`,{method:'POST',body:JSON.stringify({url:$('siteUrl').value,token:$('syncToken').value})});localStorage.setItem('siteUrl',$('siteUrl').value);$('syncToken').value='';$('syncDialog').close();toast('已上传到网站')}finally{btn.disabled=false;btn.textContent='上传'}});
$('importButton').onclick=()=>$('importDialog').showModal();$('doImport').onclick=safe(async()=>{if(!$('importFile').files[0])throw Error('请选择阅读包');const btn=$('doImport');btn.disabled=true;try{const body=new FormData();body.append('file',$('importFile').files[0]);await api('/api/import',{method:'POST',body,headers:{'x-sync-token':$('importToken').value}});$('importToken').value='';$('importDialog').close();await shelf();toast('阅读包已导入')}finally{btn.disabled=false}});
async function search(){const q=$('search').value.trim();$('searchResults').replaceChildren();if(q.length<2){toast('请输入至少两个字');return}const hits=await api('/api/search?q='+encodeURIComponent(q));$('searchResults').append(el('p','muted',`${hits.length} 条内容结果（最多显示 100 条）`));for(const hit of hits){let b=el('button','search-hit');b.append(el('small','',hit.title),el('span','',hit.snippet));b.onclick=safe(()=>openBook(hit.book_id,hit.block_id));$('searchResults').append(b)}const cards=$('books').children;for(const c of cards)c.hidden=!c.textContent.toLowerCase().includes(q.toLowerCase())}
$('searchButton').onclick=safe(search);$('search').onkeydown=e=>{if(e.key==='Enter')safe(search)()};$('search').oninput=()=>{if(!$('search').value){$('searchResults').replaceChildren();for(const c of $('books').children)c.hidden=false}};
let updateBusy=false;
let closeBusy=false;
async function desktopSaveAndQuit(){if(updateBusy||closeBusy)return;closeBusy=true;try{if(editing){await save();editing=false}await api('/api/quit',{method:'POST'});toast('正在保存当前页并退出…')}catch(e){toast('尚未退出：'+e.message)}finally{closeBusy=false}}
$('quitButton').onclick=desktopSaveAndQuit;
function acceptDesktopPaths(paths){$('paths').value=paths.join('\n');if(!$('addDialog').open)$('addDialog').showModal()}
$('desktopDrop').ondragover=e=>{e.preventDefault();$('desktopDrop').classList.add('dragging')};
$('desktopDrop').ondragleave=()=>$('desktopDrop').classList.remove('dragging');
$('desktopDrop').ondrop=e=>{e.preventDefault();$('desktopDrop').classList.remove('dragging')};
$('desktopDrop').onclick=()=>$('addDialog').showModal();
$('updateButton').onclick=safe(async()=>{const info=await api('/api/update');$('updateVersion').textContent='当前版本：'+info.current;$('updateFeed').value=info.feed||'';$('updateStatus').textContent=info.feed?'点击下方按钮检查，有新版将自动下载、安装并重启。':'首次使用请填写固定的版本信息地址；发布地址尚未设置时无法在线更新。';$('updateDialog').showModal();if(info.feed)$('checkUpdate').click()});
$('closeUpdate').onclick=()=>{if(!updateBusy)$('updateDialog').close()};$('updateDialog').oncancel=e=>{if(updateBusy)e.preventDefault()};
$('checkUpdate').onclick=safe(async()=>{
 if(updateBusy)return;
 const feed=$('updateFeed').value.trim();
 if(!feed){$('updateStatus').textContent='请先填写版本信息地址。';return}
 updateBusy=true;$('checkUpdate').disabled=true;$('closeUpdate').disabled=true;
 try{
  if(editing){await save();editing=false;render();$('editButton').textContent='核对编辑'}
  $('updateStatus').textContent='正在检查更新…';
  await api('/api/update',{method:'PUT',body:JSON.stringify({feed})});
  const info=await api('/api/update/check',{method:'POST'});
  if(!info.available){$('updateStatus').textContent='当前已是最新版本（'+info.current+'）。';return}
  $('updateStatus').textContent='发现 '+info.version+'，正在自动下载并更新…';
  await api('/api/update/install',{method:'POST'});
  const deadline=Date.now()+20*60*1000;
  while(Date.now()<deadline){
   await new Promise(resolve=>setTimeout(resolve,2000));
   let status;
   try{status=await api('/api/update')}catch{ $('updateStatus').textContent='程序正在安装或重启，请保持启动窗口开启…';continue }
   if(status.current!==info.current){location.reload();return}
   $('updateStatus').textContent=status.status.message||'更新处理中…';
   if(status.status.phase==='failed')return;
   if(status.status.phase==='done')return;
  }
  $('updateStatus').textContent='更新仍未结束，请查看程序启动窗口；不要删除 data 文件夹。';
 }catch(e){$('updateStatus').textContent=e.message}
 finally{updateBusy=false;$('checkUpdate').disabled=false;$('closeUpdate').disabled=false}
});
safe(async()=>{config=await api('/api/config');const local=config.mode==='local';$('mode').textContent=local?'转换工作台 · v'+config.version:'在线阅读书库';for(const id of ['addButton','tasksNav','editButton','localActions','updateButton','quitButton'])$(id).hidden=!local;$('tokenLabel').hidden=local;if(config.desktop){document.body.classList.add('desktop-mode');$('collectionLabel').textContent='转换项目';$('shelfNav').textContent='转换项目';$('tasksNav').textContent='任务进度';$('desktopDrop').hidden=false;$('tasks').hidden=false;await jobs()}await shelf();setInterval(()=>{if(!$('tasks').hidden)jobs().catch(()=>{})},4000)})();

if($('localActions')){
 const organizeButton=el('button','','重新整理结构');organizeButton.id='organizeButton';
 organizeButton.onclick=safe(async()=>{
  if(editing){toast('请先保存并结束编辑');return}
  organizeButton.disabled=true;organizeButton.textContent='正在整理…';
  try{const result=await api(`/api/books/${book.id}/organize`,{method:'POST',body:JSON.stringify({revision:book.revision})});book=result.book;observer?.disconnect();render();toast(`识别 ${result.summary.entries} 个目录条目，已定位 ${result.summary.linked} 个；其余保留待核对。整理前内容已备份。`)}
  finally{organizeButton.disabled=false;organizeButton.textContent='重新整理结构'}
 });$('localActions').prepend(organizeButton);
}

const editionTools=$('reader').querySelector('.readerbar>div');
const proofButton=el('button','','对照模式');proofButton.id='proofButton';proofButton.setAttribute('aria-pressed','false');
proofButton.onclick=()=>{proofing=!proofing;proofButton.textContent=proofing?'返回阅读':'对照模式';proofButton.setAttribute('aria-pressed',String(proofing));render()};editionTools.append(proofButton);
const bookmarkButton=el('button','','书签');bookmarkButton.id='readingBookmark';
bookmarkButton.onclick=safe(async()=>{const blocks=allBlocks();const b=blocks.find(x=>x.id===progress.block_id)||blocks.find(x=>x.kind==='heading')||blocks[0];if(!b)return;const marks=new Set(progress.bookmarks||[]);marks.has(b.id)?marks.delete(b.id):marks.add(b.id);progress.bookmarks=[...marks];await persistProgress();renderToc();toast(marks.has(b.id)?'已添加当前位置书签':'已取消当前位置书签')});editionTools.append(bookmarkButton);
function buildChapterNavigation(){
 $('chapterNavigation')?.remove();if(editing)return;
 const chapters=allBlocks().filter(b=>b.role!=='page_furniture'&&!catalogFor(b)&&(b.role==='recipe'||b.role==='chapter'||b.kind==='heading'&&b.role!=='subheading'));
 if(!chapters.length)return;
 const nav=el('nav','chapter-navigation');nav.id='chapterNavigation';nav.setAttribute('aria-label','章节阅读');
 const previous=el('button','','上一节'),next=el('button','','下一节'),label=el('span');
 const current=()=>{let index=0;for(let i=0;i<chapters.length;i++){const n=document.getElementById('b-'+chapters[i].id);if(n&&n.getBoundingClientRect().top<innerHeight*.4)index=i}return index};
 const update=()=>{if(!document.getElementById('chapterNavigation'))return;const i=current();label.textContent=`${i+1} / ${chapters.length}`;previous.disabled=i===0;next.disabled=i===chapters.length-1};
 const go=delta=>{const i=Math.max(0,Math.min(chapters.length-1,current()+delta));document.getElementById('b-'+chapters[i].id)?.scrollIntoView({behavior:'smooth'});};
 previous.onclick=()=>go(-1);next.onclick=()=>go(1);nav.append(previous,label,next);$('content').append(nav);update();window.onscroll=()=>requestAnimationFrame(update);
}

function connectReadingFlow(){
 if(editing||proofing)return;
 let previous=null,target=null;
 const label=/^(?:步骤\s*\d+|配方\s*\d+|原料|主料|辅料|调料|制作关键|使用贴士|制作方法|制作步骤|[一二三四五六七八九十]+[、．.]|[（(]\d+[）)]|\d+[、．.](?!\d))/;
 for(const block of allBlocks()){
  if(block.role==='page_furniture')continue;
  const node=document.getElementById('b-'+block.id);
  if(block.kind!=='text'||catalogFor(block)||['recipe','subheading','chapter'].includes(block.role)){previous=null;target=null;continue}
  const paragraphs=node?.querySelectorAll('.prose p');
  if(!paragraphs?.length){previous=null;target=null;continue}
  if(previous&&target&&!label.test(block.text.trim())&&!/[。！？!?：:]$/.test(previous.text.trim())&&block.page-previous.page>=0&&block.page-previous.page<=1){
   const first=paragraphs[0],span=el('span','continuation',first.textContent);
   if(/[A-Za-z0-9]$/.test(target.textContent)&&/^[A-Za-z0-9]/.test(span.textContent))target.append(document.createTextNode(' '));
   target.append(span);first.remove();
  }
  const remaining=node.querySelectorAll('.prose p');if(remaining.length)target=remaining[remaining.length-1];
  previous=block;
 }
}
