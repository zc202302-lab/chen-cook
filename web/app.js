const $=id=>document.getElementById(id);
let proofing=false;
let config,book,editing=false,progress={},font=Number(localStorage.getItem('font')||21),observer,cropPage,cropRect,dragStart,toastTimer;
document.documentElement.style.setProperty('--font',font+'px');
const el=(tag,cls,text)=>{let n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n};
function toast(text){$('toast').textContent=text;$('toast').hidden=false;clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').hidden=true,6500)}
async function api(path,opts={}){const r=await fetch(path,{...opts,headers:{...(opts.body instanceof FormData?{}:{'Content-Type':'application/json'}),...opts.headers}});if(!r.ok){let msg;try{msg=(await r.json()).detail}catch{msg='请求失败：'+r.status}throw Error(typeof msg==='string'?msg:JSON.stringify(msg))}return r.json()}
function safe(fn){return async(...args)=>{try{await fn(...args)}catch(e){toast(e.message)}}}
function asset(src){return `/api/books/${book.id}/assets/${encodeURIComponent(src)}`}
async function shelf(){if(editing&&!confirm('退出会丢失未保存的编辑，继续吗？'))return;editing=false;observer?.disconnect();setComparison(false);book=null;$('home').hidden=false;$('reader').hidden=true;const books=await api('/api/books');$('bookCount').textContent=books.length+' 本';$('books').replaceChildren();if(!books.length)$('books').append(el('div','empty','书架还没有书。从电脑工作台转换 PDF，或导入已转换的阅读包。'));for(const b of books){const card=el('button','book');const cover=el('div','cover');if(b.cover){const img=el('img');img.src=`/api/books/${b.id}/assets/${encodeURIComponent(b.cover)}`;img.alt=b.title;img.loading='lazy';cover.append(img)}else cover.append(el('span','title-cover',b.title));card.append(cover,el('h3','',b.title),el('p','',`${b.pages} / ${b.page_count} 页 · ${b.pending?'有待核对内容':'已核对'}`));card.onclick=safe(()=>openBook(b.id));const entry=el('div','book-entry');const remove=el('button','delete-book','删除');remove.setAttribute('aria-label','删除《'+b.title+'》');remove.onclick=()=>requestBookDeletion(b);entry.append(card,remove);$('books').append(entry)}}
async function openBook(id,anchor){if(editing&&!confirm('放弃未保存的修改？'))return;editing=false;observer?.disconnect();readingUnitIndex=0;comparisonPage=null;book=await api('/api/books/'+id);progress=await api('/api/progress/'+id);$('home').hidden=true;$('reader').hidden=false;$('readingTitle').textContent=book.title;$('editButton').textContent='核对编辑';render();if(proofing)showComparisonPage(1,true);requestAnimationFrame(()=>{const target=anchor||progress.block_id;if(target)navigateToBlock(target,false);else window.scrollTo(0,0)});}
function allBlocks(){return book.pages.flatMap(p=>p.blocks)}
function anchorLink(b,label){const a=el('a','',label);a.href='#b-'+b.id;a.onclick=e=>{e.preventDefault();navigateToBlock(b.id);$('toc').classList.remove('open')};return a}
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
// A presentation-only parse. Each segment is a slice of recognized text.
function numberedReadingSegments(text){
 const matches=[...text.matchAll(/\d{1,3}[.．、](?!\d)/gu)].filter(m=>{
  const before=m.index?text[m.index-1]:'';
  return !m.index||/[\s。；;：:）)]/u.test(before);
 });
 const accepted=[];
 for(const match of matches){
  const value=parseInt(match[0],10);
  if(!accepted.length){if(value===1||match.index===0)accepted.push(match)}
  else if(value===parseInt(accepted[accepted.length-1][0],10)+1)accepted.push(match);
 }
 if(!accepted.length||accepted.length===1&&accepted[0].index>0)return [{kind:'paragraph',text}];
 const result=[];
 if(accepted[0].index)result.push({kind:'paragraph',text:text.slice(0,accepted[0].index)});
 result.push({kind:'list',items:accepted.map((m,i)=>({marker:m[0],text:text.slice(m.index+m[0].length,i+1<accepted.length?accepted[i+1].index:text.length)}))});
 return result;
}
function recipeHeading(chunk){
 const step=chunk.match(/^步骤\s*\d+/u);
 if(step){
  const rest=chunk.slice(step[0].length);let cut=0;
  const firstItem=/(?<!\d)1[.．、](?!\d)/u.exec(rest);
  if(firstItem&&firstItem.index<=24&&!/[。；;]/u.test(rest.slice(0,firstItem.index)))cut=firstItem.index;
  else if(!/^(?:将|把|取|先|用|在)/u.test(rest.trimStart())){
   const title=/^(.{2,14}?)(?=(?:将|把|取|先|锅中|锅内|在锅|用)[^\s])/u.exec(rest);
   if(title&&!/[。；;：:]/u.test(title[1]))cut=title[1].length;
  }
  return {heading:chunk.slice(0,step[0].length+cut),body:chunk.slice(step[0].length+cut)};
 }
 const label=/^(?:应用方法|使用方法|制作方法|制作步骤|制作关键|关键提示|使用贴士|技术要点|(?:原料|主料|辅料|调料|配料)[：:]|制作[^\s，。；：:\d]{0,4}?汁)[：:]?/u.exec(chunk);
 return label?{heading:label[0],body:chunk.slice(label[0].length)}:null;
}
function recipeReadingSegments(text){
 const result=[];
 const append=segment=>{
  if(segment.kind==='paragraph'&&!segment.text.trim())return;
  const last=result[result.length-1];
  if(segment.kind==='list'&&last?.kind==='list'&&parseInt(segment.items[0].marker,10)===parseInt(last.items[last.items.length-1].marker,10)+1)last.items.push(...segment.items);
  else result.push(segment);
 };
 for(const paragraph of readingParagraphs(text)){
  const headers=[...paragraph.matchAll(/步骤\s*\d+|应用方法|使用方法|制作方法|制作步骤|制作关键|关键提示|使用贴士|技术要点|(?:原料|主料|辅料|调料|配料)[：:]|制作[^\s，。；：:\d]{0,4}?汁/gu)]
   .filter(m=>!m.index||/[\s。；;：:]/u.test(paragraph[m.index-1]));
  if(!headers.length){numberedReadingSegments(paragraph).forEach(append);continue}
  if(headers[0].index)numberedReadingSegments(paragraph.slice(0,headers[0].index)).forEach(append);
  headers.forEach((m,i)=>{
   const chunk=paragraph.slice(m.index,i+1<headers.length?headers[i+1].index:paragraph.length);
   const section=recipeHeading(chunk);
   if(section){append({kind:'heading',text:section.heading});numberedReadingSegments(section.body).forEach(append)}
   else numberedReadingSegments(chunk).forEach(append);
  });
 }
 return result;
}
function appendReadingText(node,text,emphasize=false){
 if(!emphasize){node.append(document.createTextNode(text));return}
 const pattern=/\d+(?:[.．]\d+)?\s*(?:千克|公斤|毫升|分钟|小时|克|升|秒|℃|%|个|根|块)/gu;
 let offset=0;
 for(const match of text.matchAll(pattern)){
  node.append(document.createTextNode(text.slice(offset,match.index)),el('span','recipe-measure',match[0]));offset=match.index+match[0].length;
 }
 node.append(document.createTextNode(text.slice(offset)));
}

function readingText(block){
 const node=el('div','prose');
 const catalog=catalogFor(block);
 if(catalog){
  const rows=el('ol','catalog-list');for(const row of catalog.rows)rows.append(catalogItem(row));node.append(rows);
  const details=el('details','catalog-source');details.append(el('summary','','查看识别原文'));details.append(el('pre','',block.text));node.append(details);return node;
 }
 const segments=recipeReadingSegments(block.text);
 const structured=segments.some(s=>s.kind!=='paragraph');node.dataset.structured=String(structured);
 for(const segment of segments){
  if(segment.kind==='heading'){
   const heading=el('h4','reading-subtitle');const step=/^(步骤\s*\d+)(.*)$/u.exec(segment.text);
   if(step){heading.append(el('span','step-number',step[1]),el('span','',step[2]))}else heading.textContent=segment.text;
   node.append(heading);
  }else if(segment.kind==='list'){
   const list=el('ol','reading-list');list.setAttribute('aria-label','原文编号条目');list.start=parseInt(segment.items[0].marker,10);
   for(const item of segment.items){const row=el('li');row.value=parseInt(item.marker,10);const body=el('p');appendReadingText(body,item.text,structured);row.append(el('span','reading-marker',item.marker),body);list.append(row)}
   node.append(list);
  }else{const paragraph=el('p');appendReadingText(paragraph,segment.text,structured);node.append(paragraph)}
 }
 return node;
}
function render(){document.body.classList.toggle('proof-mode',editing);$('content').classList.add('book-edition');renderToc();const content=$('content');content.replaceChildren();content.append(el('h1','',book.title));content.append(el('div','notice','自动转换初稿：未核对标记表示文字、顺序或图文归属尚未确认。目录条目会与正文标题匹配；待定位条目不猜测跳转。可在电脑工作台整理结构并核对。'));if(editing){const bar=el('div','save-strip');bar.append(el('span','','修改后请保存，原文不会被自动润色。'));let btn=el('button','primary','保存修改');btn.onclick=safe(save);bar.append(btn);content.append(bar);const title=el('input');title.value=book.title;title.setAttribute('aria-label','书名');title.oninput=()=>book.title=title.value;title.style.width='100%';content.append(title)}for(const pg of book.pages){if(!pg.blocks.length)continue;for(const b of pg.blocks){const wrap=el('section',editing?'block editbox':'block');wrap.id='b-'+b.id;wrap.dataset.block=b.id;wrap.dataset.page=b.page;wrap.dataset.role=b.role||b.kind;if(editing){const controls=el('div','edit-controls');const kind=el('select');for(const [value,text] of [['text','正文'],['heading','目录标题'],['image','图片']]){if((b.kind==='image')!==(value==='image'))continue;let o=el('option','',text);o.value=value;kind.append(o)}kind.value=b.kind;kind.onchange=()=>{b.kind=kind.value;delete b.role;delete b.catalog;render()};controls.append(kind);if(b.kind==='heading'){const level=el('select');for(let i=1;i<=3;i++){const o=el('option','','目录 '+i+' 级');o.value=i;level.append(o)}level.value=b.level||2;level.onchange=()=>{b.level=+level.value;renderToc()};controls.append(level)}const check=el('input');check.type='checkbox';check.checked=!!b.reviewed;check.onchange=()=>b.reviewed=check.checked;let label=el('label','','已对照核对 ');label.prepend(check);controls.append(label);for(const [label,delta] of [['↑',-1],['↓',1]]){const btn=el('button','',label);btn.title='移动内容块（可跨页）';btn.onclick=()=>move(b.id,delta);controls.append(btn)}const del=el('button','','删除');del.onclick=()=>{if(confirm('确认删除此内容块？')){pg.blocks=pg.blocks.filter(x=>x.id!==b.id);render()}};controls.append(del);wrap.append(controls);if(b.kind==='image'){const img=el('img');img.src=asset(b.src);img.alt=b.caption||'待核对裁图';wrap.append(img);const caption=el('textarea');caption.value=b.caption||'';caption.placeholder='原文图注（不要新增原文没有的说明）';caption.oninput=()=>b.caption=caption.value;wrap.append(caption)}else{const text=el('textarea');text.value=b.text;text.oninput=()=>{b.text=text.value;renderToc()};wrap.append(text);const split=el('button','','在光标处拆分');split.onclick=()=>{const pos=text.selectionStart;if(pos<=0||pos>=b.text.length)return;const n={...b,id:crypto.randomUUID().replaceAll('-','').slice(0,16),text:b.text.slice(pos),reviewed:false};b.text=b.text.slice(0,pos);pg.blocks.splice(pg.blocks.indexOf(b)+1,0,n);render()};wrap.append(split)}}else if(b.kind==='image'){const figure=el('figure');const img=el('img');img.src=asset(b.src);img.alt=b.caption||'菜谱配图';img.loading='lazy';img.onclick=()=>{$('largeImage').src=img.src;$('imageDialog').showModal()};figure.append(img);if(b.caption)figure.append(el('figcaption','',b.caption));wrap.append(figure)}else if(catalogFor(b))wrap.append(readingText(b));else if(b.role==='recipe'||b.role==='subheading')wrap.append(el(b.role==='recipe'?'h2':'h3','',b.text));else if(b.kind==='text')wrap.append(readingText(b));else wrap.append(el(Number(b.level||2)===3?'h3':'h2','',b.text));const foot=el('div','block-foot');foot.append(el('span','',`来源第 ${b.page} 页`));if(!b.reviewed)foot.append(el('span','pending','待核对'));if(config.mode==='local'){const original=el('button','','对照原页 / 裁图');original.onclick=safe(()=>showOriginal(b.page));foot.append(original)}if(!editing){const mark=el('button','',(progress.bookmarks||[]).includes(b.id)?'★ 已收藏':'☆ 书签');mark.onclick=safe(async()=>{const marks=new Set(progress.bookmarks||[]);marks.has(b.id)?marks.delete(b.id):marks.add(b.id);progress.bookmarks=[...marks];await persistProgress();renderToc();mark.textContent=marks.has(b.id)?'★ 已收藏':'☆ 书签'});foot.append(mark)}wrap.append(foot);content.append(wrap)}}connectReadingFlow();buildChapterNavigation();if(!editing){observer?.disconnect();observer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){progress.block_id=e.target.dataset.block;if(proofing&&comparisonFollow)showComparisonPage(Number(e.target.dataset.page));clearTimeout(window.progressTimer);window.progressTimer=setTimeout(()=>persistProgress().catch(()=>{}),800)}},{rootMargin:'-10% 0px -65% 0px'});content.querySelectorAll('.block').forEach(n=>observer.observe(n))}}
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
proofButton.onclick=()=>setComparison(!proofing);editionTools.append(proofButton);
const bookmarkButton=el('button','','书签');bookmarkButton.id='readingBookmark';
bookmarkButton.onclick=safe(async()=>{const blocks=allBlocks();const b=blocks.find(x=>x.id===progress.block_id)||blocks.find(x=>x.kind==='heading')||blocks[0];if(!b)return;const marks=new Set(progress.bookmarks||[]);marks.has(b.id)?marks.delete(b.id):marks.add(b.id);progress.bookmarks=[...marks];await persistProgress();renderToc();toast(marks.has(b.id)?'已添加当前位置书签':'已取消当前位置书签')});editionTools.append(bookmarkButton);
let readingUnits=[],readingUnitIndex=0;
const subsectionTitle=/^(?:制作(?:方法|过程|步骤)?|原料|主料|辅料|调料|配料|用料|步骤\s*\d*|配方\s*\d+|制作关键|使用贴士|小贴士)$/;
function deriveReadingUnits(){
 const units=[];let current=null;
 for(const b of allBlocks()){
  const text=String(b.text||'').trim();
  const boundary=b.role!=='page_furniture'&&!catalogFor(b)&&!subsectionTitle.test(text)&&(b.role==='recipe'||b.role==='chapter'||b.kind==='heading'&&Number(b.level||2)<=2);
  if(!current||boundary&&current.ids.length){
   current={title:boundary?text:(units.length?'正文':'书前内容'),ids:[]};units.push(current);
  }
  current.ids.push(b.id);
 }
 return units;
}
function applyReadingUnit(index,savePosition=false){
 readingUnitIndex=Math.max(0,Math.min(index,readingUnits.length-1));
 const unit=readingUnits[readingUnitIndex],visible=new Set(unit?.ids||[]);
 for(const n of $('content').querySelectorAll('.block'))n.hidden=!(editing||visible.has(n.dataset.block));
 const bookTitle=$('content').querySelector(':scope>h1');if(bookTitle)bookTitle.hidden=!editing&&readingUnitIndex!==0;
 const select=$('chapterSelect');if(select)select.value=String(readingUnitIndex);
 const label=$('chapterPosition');if(label)label.textContent=`${readingUnitIndex+1} / ${readingUnits.length}`;
 const previous=$('previousChapter'),next=$('nextChapter');if(previous)previous.disabled=readingUnitIndex===0;if(next)next.disabled=readingUnitIndex>=readingUnits.length-1;
 if(savePosition&&unit){progress.block_id=unit.ids[0];persistProgress().catch(e=>toast(e.message));window.scrollTo({top:0,behavior:'smooth'})}
}
function navigateToBlock(id,smooth=true){
 if(!editing){const index=readingUnits.findIndex(u=>u.ids.includes(id));if(index>=0)applyReadingUnit(index)}
 requestAnimationFrame(()=>document.getElementById('b-'+id)?.scrollIntoView({behavior:smooth?'smooth':'instant',block:'start'}));
}
function buildChapterNavigation(){
 $('chapterNavigation')?.remove();$('chapterSwitcher')?.remove();readingUnits=deriveReadingUnits();
 if(editing){applyReadingUnit(readingUnitIndex);return}
 if(!readingUnits.length)return;
 const switcher=el('div','chapter-switcher');switcher.id='chapterSwitcher';
 const label=el('label','','当前章节 ');label.htmlFor='chapterSelect';
 const select=el('select');select.id='chapterSelect';select.setAttribute('aria-label','选择章节');
 readingUnits.forEach((u,i)=>{const option=el('option','',`${i+1}. ${u.title}`);option.value=String(i);select.append(option)});
 select.onchange=()=>applyReadingUnit(Number(select.value),true);switcher.append(label,select);
 $('content').querySelector(':scope>h1').after(switcher);
 const nav=el('nav','chapter-navigation');nav.id='chapterNavigation';nav.setAttribute('aria-label','章节阅读');
 const previous=el('button','','上一章'),next=el('button','','下一章'),position=el('span');previous.id='previousChapter';next.id='nextChapter';position.id='chapterPosition';
 previous.onclick=()=>applyReadingUnit(readingUnitIndex-1,true);next.onclick=()=>applyReadingUnit(readingUnitIndex+1,true);
 nav.append(previous,position,next);$('content').append(nav);applyReadingUnit(readingUnitIndex);
}

function connectReadingFlow(){
 if(editing)return;
 let previous=null,target=null;
 const label=/^(?:步骤\s*\d+|配方\s*\d+|原料|主料|辅料|调料|制作关键|使用贴士|制作方法|制作步骤|[一二三四五六七八九十]+[、．.]|[（(]\d+[）)]|\d+[、．.](?!\d))/;
 for(const block of allBlocks()){
  if(block.role==='page_furniture')continue;
  const node=document.getElementById('b-'+block.id);
  if(block.kind!=='text'||catalogFor(block)||['recipe','subheading','chapter'].includes(block.role)){previous=null;target=null;continue}
  if(node?.querySelector('.prose[data-structured="true"]')){previous=null;target=null;continue}
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

let managementToken='',pendingDeletion=null;
function managementHeaders(){return config.mode==='local'?{}:{'x-sync-token':managementToken}}
function requestBookDeletion(item){
 pendingDeletion=item;$('deleteBookTitle').textContent=`删除《${item.title}》？`;
 $('deleteBookHint').textContent=config.mode==='local'?'将本机转换结果移入回收站，原 PDF 保留；网站副本不会被同步删除。':'将网站阅读副本移入回收站，电脑上的原 PDF 和转换结果保留。';
 $('deleteTokenLabel').hidden=config.mode==='local';$('deleteToken').value=managementToken;$('deleteBookError').textContent='';$('deleteBookDialog').showModal();
}
async function loadTrash(){
 if(config.mode!=='local')managementToken=$('trashToken').value.trim();
 const list=$('trashList');list.replaceChildren();
 const items=await api('/api/trash',{headers:managementHeaders()});
 if(!items.length)list.append(el('p','muted','回收站为空。'));
 for(const item of items){
  const row=el('div','trash-row');row.append(el('strong','',item.title));
  const controls=el('div','edit-controls');
  const restore=el('button','','恢复');restore.onclick=safe(async()=>{restore.disabled=true;try{await api(`/api/trash/${item.trash_id}/restore`,{method:'POST',headers:managementHeaders()});await loadTrash();await shelf();if(config.mode==='local')await jobs();toast('电子书和阅读进度已恢复')}finally{restore.disabled=false}});
  const purge=el('button','danger-link','彻底删除');purge.onclick=safe(async()=>{if(!confirm(`彻底删除《${item.title}》的转换结果？此操作无法撤销，原 PDF 不受影响。`))return;await api(`/api/trash/${item.trash_id}`,{method:'DELETE',headers:managementHeaders()});await loadTrash()});
  controls.append(restore,purge);row.append(controls);list.append(row);
 }
}
const deleteDialog=el('dialog');deleteDialog.id='deleteBookDialog';
deleteDialog.innerHTML='<h2 id="deleteBookTitle"></h2><p id="deleteBookHint" class="muted"></p><label id="deleteTokenLabel">网站同步密钥<input id="deleteToken" type="password" autocomplete="off"></label><p id="deleteBookError" role="alert"></p><div class="dialog-actions"><button id="cancelDeleteBook">取消</button><button id="confirmDeleteBook" class="primary">移入回收站</button></div>';
document.body.append(deleteDialog);$('cancelDeleteBook').onclick=()=>deleteDialog.close();
$('confirmDeleteBook').onclick=async()=>{const button=$('confirmDeleteBook');button.disabled=true;try{if(config.mode!=='local')managementToken=$('deleteToken').value.trim();const item=pendingDeletion;await api('/api/books/'+item.id,{method:'DELETE',headers:managementHeaders()});deleteDialog.close();$('deleteToken').value='';pendingDeletion=null;await shelf();if(config.mode==='local')await jobs();toast('已移入回收站，原 PDF 保留')}catch(e){$('deleteBookError').textContent=e.message}finally{button.disabled=false}};
const trashDialog=el('dialog');trashDialog.id='trashDialog';trashDialog.innerHTML='<h2>回收站</h2><p class="muted">可以恢复已删除的电子书、阅读进度和书签。</p><label id="trashTokenLabel">网站同步密钥<input id="trashToken" type="password" autocomplete="off"></label><button id="loadTrash">查看回收站</button><div id="trashList"></div><div class="dialog-actions"><button id="closeTrash">关闭</button></div>';document.body.append(trashDialog);
$('loadTrash').onclick=safe(loadTrash);$('closeTrash').onclick=()=>{trashDialog.close();$('trashToken').value=''};
const trashButton=el('button','','回收站');trashButton.id='trashButton';
trashButton.onclick=safe(async()=>{$('trashTokenLabel').hidden=config.mode==='local';$('trashToken').value=managementToken;$('trashList').replaceChildren();trashDialog.showModal();if(config.mode==='local'||managementToken)await loadTrash()});
$('importButton').parentElement.append(trashButton);

// The comparison is a separate surface; the reading edition and chapters remain intact.
let comparisonPage=null,comparisonFollow=true;
function setComparison(open){
 proofing=open;$('comparison').hidden=!open;$('reader').classList.toggle('with-comparison',open);
 proofButton.textContent=open?'关闭对照':'对照模式';proofButton.setAttribute('aria-pressed',String(open));
 if(open&&book){const block=allBlocks().find(b=>b.id===progress.block_id);showComparisonPage(block?.page||book.pages[0]?.page||1,true)}
}
function showComparisonPage(page,force=false){
 if(!book||!proofing)return;
 const maximum=Math.max(1,Number(book.page_count)||1,...book.pages.map(p=>Number(p.page)||1));
 page=Math.max(1,Math.min(maximum,Math.trunc(Number(page)||1)));
 if(!force&&comparisonPage===page)return;
 comparisonPage=page;$('comparePage').value=page;$('comparePage').max=maximum;$('compareTotal').textContent='/ '+maximum;
 $('comparePrevious').disabled=page<=1;$('compareNext').disabled=page>=maximum;
 const local=config.mode==='local';$('compareTitle').textContent=local?'原 PDF 对照':'识别原文对照';
 $('compareHint').textContent=local?'原页来自电脑上的 PDF；正文滚动时自动跟随。点击原页可放大。':'原 PDF 仅保存在电脑。此处显示转换时保存的识别原文，保留原换行，供文字核对；原页请在电脑工作台查看。';
 const body=$('compareBody');body.replaceChildren();body.scrollTop=0;
 if(local){
  const status=el('p','compare-status','正在载入原页…');status.setAttribute('role','status');
  const image=el('img','compare-original');image.alt=`原 PDF 第 ${page} 页`;image.hidden=true;
  image.onload=()=>{status.remove();image.hidden=false};
  image.onerror=()=>{image.remove();status.textContent='原页无法载入，请确认电脑上的原 PDF 仍在原路径。可关闭对照后重新打开重试。'};
  image.onclick=()=>{$('largeImage').src=image.src;$('imageDialog').showModal()};
  image.src=`/api/books/${book.id}/original/${page}`;body.append(status,image);
 }else{
  const blocks=book.pages.find(p=>Number(p.page)===page)?.blocks||[];
  if(!blocks.length)body.append(el('p','compare-status','此页尚无转换内容。'));
  for(const b of blocks){
   const source=el('section','compare-source');source.dataset.sourceBlock=b.id;
   if(b.kind==='image'){const image=el('img');image.src=asset(b.src);image.alt=b.caption||'该页提取的图片';source.append(image);if(b.caption)source.append(el('p','',b.caption))}
   else source.append(el('pre','',b.text||''));
   body.append(source);
  }
 }
}
$('closeComparison').onclick=()=>setComparison(false);
$('compareFollow').onchange=()=>{comparisonFollow=$('compareFollow').checked;if(comparisonFollow){const b=allBlocks().find(b=>b.id===progress.block_id);if(b)showComparisonPage(b.page)}};
function manualComparison(page){comparisonFollow=false;$('compareFollow').checked=false;showComparisonPage(page)}
$('comparePrevious').onclick=()=>manualComparison(comparisonPage-1);
$('compareNext').onclick=()=>manualComparison(comparisonPage+1);
$('comparePage').onchange=()=>manualComparison($('comparePage').value);
const fontChoice=el('select');fontChoice.id='fontChoice';fontChoice.setAttribute('aria-label','正文字体');
for(const [value,label] of [['sans','黑体'],['serif','宋体']]){const option=el('option','',label);option.value=value;fontChoice.append(option)}
fontChoice.value=localStorage.getItem('readingFont')==='serif'?'serif':'sans';
function applyReadingFont(){document.documentElement.dataset.readingFont=fontChoice.value;localStorage.setItem('readingFont',fontChoice.value)}
fontChoice.onchange=applyReadingFont;applyReadingFont();$('smaller').before(fontChoice);
