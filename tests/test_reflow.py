import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from cooklib.reflow import reflow


class ReflowTest(unittest.TestCase):
    def test_geometry_keeps_column_order_and_quantities_without_margin_noise(self):
        def line(text,x,y,w=180,h=20,score=.99):return [[[x,y],[x+w,y],[x+w,y+h],[x,y+h]],text,score]
        lines=[line('测试标题',180,50,160,40),line('步骤1加入150',40,120),line('克后拌匀。',40,155),
               line('步骤2再加20克。',290,120,score=.6),line('栏外',1,180,10,120),line('8',40,980,10,20)]
        digest='a'*64
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,COOK_DATA_DIR=tmp):
            path=Path(tmp)/'ocr-audit'/digest/'1.json';path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'width':550,'lines':lines,'reading_order':[0,1,4,2,5,3]}))
            result=reflow('unchanged stored text',digest,1,'ocr:rapidocr')
        self.assertEqual(result['source'],'geometry');self.assertEqual(result['omitted'],2)
        self.assertEqual([b['text'] for b in result['blocks']],['测试标题','步骤1加入150克后拌匀。','步骤2再加20克。'])
        self.assertEqual(result['blocks'][0]['kind'],'heading')
        self.assertTrue(result['blocks'][-1]['uncertain'])

    def test_missing_or_invalid_audit_falls_back_without_inventing_text(self):
        text='步骤1加入150\n克。\n\n步骤2加入20克。\n<script>not executable</script>'
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,COOK_DATA_DIR=tmp):
            result=reflow(text,'b'*64,1,'ocr:rapidocr')
            path=Path(tmp)/'ocr-audit'/('b'*64)/'1.json';path.parent.mkdir(parents=True)
            path.write_text('{"width":500,"lines":[],"reading_order":[]}')
            self.assertEqual(result,reflow(text,'b'*64,1,'ocr:rapidocr'))
        joined=''.join(block['text'] for block in result['blocks'])
        self.assertEqual(''.join(joined.split()),''.join(text.split()))
        self.assertEqual(result['source'],'text')

    def test_no_text_is_not_fabricated(self):
        self.assertEqual(reflow('','invalid-digest',1,'image')['blocks'],[])
