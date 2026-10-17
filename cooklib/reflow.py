"""Read-only, conservative reflow of existing text/audits. No OCR or PDF work here."""
import json
import math
import re
from statistics import median
from .store import root

START = re.compile(r'^(?:步骤\s*\d+|配方\s*[一二三四五六七八九十\d]+|制作关键|制作方法|操作要点|原料[：:]|调料[：:]|做法[：:])')


def _join(left, right):
    # Preserve every non-whitespace character; never infer or "correct" quantities.
    gap = ' ' if left and right and left[-1].isascii() and right[0].isascii() and left[-1].isalnum() and right[0].isalnum() else ''
    return left + gap + right


def _blocks(lines):
    result=[]; paragraph=''; uncertain=False
    def flush():
        nonlocal paragraph,uncertain
        if paragraph:result.append({'kind':'paragraph','text':paragraph,'uncertain':uncertain})
        paragraph='';uncertain=False
    for text, heading, low, blank in lines:
        if not text:flush();continue
        if heading:
            flush();result.append({'kind':'heading','text':text,'uncertain':low});continue
        if blank or START.match(text) or re.search(r'[。！？!?]$',paragraph):flush()
        paragraph=_join(paragraph,text);uncertain=uncertain or low
    flush()
    return result


def reflow(text, digest, page, method):
    """Use retained detector order + geometry, falling back to stored text safely.

    Only obvious vertical margin labels and isolated bottom page numbers are
    omitted from this view; the database and original image are never modified.
    Confidence flags indicate detector uncertainty, not measured accuracy.
    """
    if method.startswith('ocr:') and re.fullmatch(r'[0-9a-f]{64}',digest):
        path=root()/'ocr-audit'/digest/f'{page}.json'
        try:
            if path.stat().st_size>8*1024*1024:raise ValueError('audit too large')
            audit=json.loads(path.read_text(encoding='utf-8'))
            source=audit['lines'];order=audit['reading_order'];width=float(audit['width'])
            if not 0<width<=20000 or not 0<len(source)<=10000:raise ValueError('audit shape')
            if any(type(i) is not int for i in order) or sorted(order)!=list(range(len(source))):raise ValueError('audit order')
            rows=[]
            for item in source:
                points=item[0];value=item[1];score=float(item[2])
                if not isinstance(value,str) or len(points)!=4:raise ValueError('audit line')
                xs=[float(p[0]) for p in points];ys=[float(p[1]) for p in points]
                if not all(math.isfinite(n) for n in xs+ys+[score]):raise ValueError('audit coordinates')
                x,y,x2,y2=min(xs),min(ys),max(xs),max(ys)
                if x2<=x or y2<=y:raise ValueError('audit bounds')
                rows.append((value.strip(),x,y,x2,y2,score))
            height=max(r[4] for r in rows)
            normal=median(r[4]-r[2] for r in rows)
            lines=[];omitted=0
            for index in order:
                value,x,y,x2,y2,score=rows[index]
                vertical=(y2-y)>1.7*(x2-x) and (x<width*.08 or x2>width*.92) and len(value)<=14
                footer=y>height*.93 and re.fullmatch(r'\d{1,4}',value)
                if vertical or footer:omitted+=1;continue
                heading=(y2-y)>normal*1.35 and len(value)<=48
                lines.append((value,heading,score<.8,False))
            return {'blocks':_blocks(lines),'source':'geometry','omitted':omitted,'ocr':True}
        except (OSError,ValueError,TypeError,KeyError,IndexError,OverflowError):
            pass
    lines=[(line.strip(),False,False,not line.strip()) for line in text.splitlines()]
    return {'blocks':_blocks(lines),'source':'text','omitted':0,'ocr':method.startswith('ocr:')}
