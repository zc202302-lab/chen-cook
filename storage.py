import json
import os
import re
import shutil
import tempfile
import threading
import zipfile
from pathlib import Path

LOCK = threading.RLock()
ID = re.compile(r'^[a-f0-9]{24}$')
ASSET = re.compile(r'^[A-Za-z0-9_-]+\.(png|jpg|jpeg|webp)$')


def atomic_json(path, obj):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp')
    with LOCK:
        temp.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(temp,path)


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def validate_book(book):
    if not isinstance(book,dict) or not ID.fullmatch(str(book.get('id',''))):
        raise ValueError('无效书籍编号')
    if not isinstance(book.get('title'),str) or not isinstance(book.get('pages'),list):
        raise ValueError('书籍格式错误')
    ids=set()
    for page in book['pages']:
        if not isinstance(page.get('page'),int) or not isinstance(page.get('blocks'),list):
            raise ValueError('页面格式错误')
        for block in page['blocks']:
            if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',str(block.get('id',''))) or block['id'] in ids:
                raise ValueError('内容块编号无效或重复')
            ids.add(block['id'])
            if 'role' in block and block['role'] not in ('chapter','catalog','recipe','subheading','procedure','ingredients','tips','page_furniture'):
                raise ValueError('内容结构类型错误')
            catalog=block.get('catalog')
            if catalog is not None:
                if not isinstance(catalog,dict) or not isinstance(catalog.get('text_snapshot'),str) or not isinstance(catalog.get('rows'),list) or len(catalog['rows'])>5000:
                    raise ValueError('目录结构错误')
                for row in catalog['rows']:
                    if not isinstance(row,dict) or not isinstance(row.get('raw'),str):raise ValueError('目录行格式错误')
                    for key in ('title','printed_page','target_id','evidence'):
                        if key in row and not isinstance(row[key],str):raise ValueError('目录条目格式错误')
                    if row.get('target_id') and not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',row['target_id']):raise ValueError('目录目标错误')
            if block.get('kind') not in ('text','heading','image'):
                raise ValueError('内容类型错误')
            if block['kind']=='image' and not ASSET.fullmatch(str(block.get('src',''))):
                raise ValueError('图片名称无效')
            if block['kind']!='image' and not isinstance(block.get('text'),str):
                raise ValueError('文字格式错误')
    return book


def public_book(book):
    # Explicit allow-list: never export source path, raw page image, OCR cache or credentials.
    out={k:book[k] for k in ('id','title','page_count','revision','status') if k in book}
    out['schema_version']=1
    out['pages']=[]
    for p in book['pages']:
        blocks=[]
        for b in p['blocks']:
            blocks.append({k:b[k] for k in ('id','kind','page','level','reviewed','text','src','caption','box','confidence','note','role','catalog') if k in b})
        out['pages'].append(dict(page=p['page'],blocks=blocks,warning=p.get('warning','')))
    return out


def export_book(directory, destination):
    book=validate_book(public_book(read_json(directory/'book.json')))
    if not book['pages']:
        raise ValueError('尚无可导出的转换结果')
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('book.json',json.dumps(book,ensure_ascii=False))
        assets={b['src'] for p in book['pages'] for b in p['blocks'] if b['kind']=='image'}
        for name in assets:
            z.write(directory/'assets'/name,'assets/'+name)
    return destination


def import_book(archive, root):
    with zipfile.ZipFile(archive) as z:
        info=z.infolist()
        if len(info)>30000 or sum(i.file_size for i in info)>1024**3:
            raise ValueError('结果包超过第一版导入上限：1GB 或 30000 个文件')
        names=[i.filename for i in info]
        if len(set(names))!=len(names):
            raise ValueError('结果包包含重复文件')
        if 'book.json' not in names or z.getinfo('book.json').file_size>64*1024**2:
            raise ValueError('缺少书籍信息或信息过大')
        if any(n!='book.json' and not(n.startswith('assets/') and ASSET.fullmatch(n[7:])) for n in names):
            raise ValueError('结果包包含不允许的文件（不接受 PDF 或原页文件）')
        book=validate_book(public_book(json.loads(z.read('book.json'))))
        assets={b['src'] for p in book['pages'] for b in p['blocks'] if b['kind']=='image'}
        if any('assets/'+n not in names for n in assets):
            raise ValueError('结果包缺少图片')
        target=root/book['id']
        if target.exists():
            raise ValueError('同一本书已存在；第一版请勿重复导入覆盖已有修正')
        with tempfile.TemporaryDirectory(dir=root) as temp:
            staging=Path(temp)/'book';(staging/'assets').mkdir(parents=True)
            for name in assets:
                (staging/'assets'/name).write_bytes(z.read('assets/'+name))
            atomic_json(staging/'book.json',book)
            os.replace(staging,target)
    return book


def trash_book(root, bid):
    """Move only a converted book and its reading progress. Never follow source paths."""
    import uuid
    from datetime import datetime, timezone
    root=Path(root)
    if not ID.fullmatch(bid):raise ValueError('书籍编号无效')
    with LOCK:
        source=root/'books'/bid
        if source.is_symlink() or not(source/'book.json').is_file():raise ValueError('书籍不存在')
        book=read_json(source/'book.json')
        if book.get('id')!=bid:raise ValueError('书籍编号不匹配')
        trash=root/'trash'
        if trash.is_symlink():raise ValueError('回收站目录无效')
        trash.mkdir(exist_ok=True)
        tid=uuid.uuid4().hex;target=trash/tid
        progress=root/'progress'/f'{bid}.json'
        if progress.is_symlink():raise ValueError('阅读进度路径无效')
        info=dict(trash_id=tid,id=bid,title=book['title'],deleted_at=datetime.now(timezone.utc).isoformat())
        os.replace(source,target)
        try:
            if progress.exists():os.replace(progress,target/'.reading-progress.json')
            atomic_json(target/'.deleted.json',info)
        except BaseException:
            if (target/'.reading-progress.json').exists():
                progress.parent.mkdir(exist_ok=True);os.replace(target/'.reading-progress.json',progress)
            os.replace(target,source)
            raise
        return info


def trash_directory(root, tid):
    if not re.fullmatch(r'[a-f0-9]{32}',tid):raise ValueError('回收站编号无效')
    root=Path(root);path=root/'trash'/tid
    if (root/'trash').is_symlink() or path.is_symlink() or not(path/'book.json').is_file():raise ValueError('回收站条目不存在')
    return path


def list_trash(root):
    result=[]
    for path in (Path(root)/'trash').glob('*/.deleted.json'):
        if path.parent.is_symlink():continue
        info=read_json(path)
        result.append({k:info[k] for k in ('trash_id','id','title','deleted_at')})
    return sorted(result,key=lambda x:x['deleted_at'],reverse=True)


def restore_book(root, tid):
    root=Path(root)
    with LOCK:
        source=trash_directory(root,tid);book=read_json(source/'book.json');bid=book['id']
        if not ID.fullmatch(bid):raise ValueError('书籍编号无效')
        target=root/'books'/bid
        if target.exists() or target.is_symlink():raise ValueError('书库已有同一本书，不能覆盖；请先处理现有版本')
        progress=root/'progress'/f'{bid}.json'
        if progress.exists() or progress.is_symlink():raise ValueError('已有同书阅读进度，不能覆盖')
        os.replace(source,target)
        try:
            saved=target/'.reading-progress.json'
            if saved.exists():
                progress.parent.mkdir(exist_ok=True);os.replace(saved,progress)
            (target/'.deleted.json').unlink(missing_ok=True)
        except BaseException:
            if progress.exists():os.replace(progress,target/'.reading-progress.json')
            os.replace(target,source);raise
        return {'id':bid,'title':book['title']}


def purge_book(root, tid):
    with LOCK:shutil.rmtree(trash_directory(root,tid))
