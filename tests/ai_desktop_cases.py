import copy,io,json,tempfile,time,unittest,zipfile,threading
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import engine
from app import create_app
from storage import atomic_json
ENDPOINT='https://dashscope.aliyuncs.com/compatible-mode/v1';BID='b'*24

def page(n=1):
 return {'page':n,'ocr_size':[600,800],'ocr_lines':[{'text':'合成菜谱','box':[10,10,180,40]},{'text':'原料：盐2.5克。','box':[10,50,300,80]}],'blocks':[{'id':'text'+str(n),'kind':'text','page':n,'text':'合成菜谱\n原料：盐2.5克。','reviewed':False}]}
def response(groups=None):
 return {'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'groups':groups if groups is not None else [{'ids':['t0'],'kind':'heading','level':2},{'ids':['t1'],'kind':'text'}]})}}],'usage':{'prompt_tokens':1000,'completion_tokens':200}}

class AiLayoutTests(unittest.TestCase):
 def test_endpoint_pages_and_output_limits(self):
  self.assertEqual(engine.ai_endpoint(ENDPOINT+'/'),ENDPOINT)
  for url in ['http://dashscope.aliyuncs.com/compatible-mode/v1','https://evil.test/compatible-mode/v1','https://dashscope.aliyuncs.com.evil.test/compatible-mode/v1','https://user@dashscope.aliyuncs.com/compatible-mode/v1',ENDPOINT+'?secret=x']:
   with self.assertRaises(ValueError):engine.ai_endpoint(url)
  self.assertEqual(engine.ai_page_numbers('1,3-5',[1,3,4,5]),[1,3,4,5])
  for value in ['1-21','1-99999999','0','3-1','1,99','']:
   with self.assertRaises(ValueError):engine.ai_page_numbers(value,list(range(1,30)))
  broken=response();broken['choices'][0]['finish_reason']='length'
  with self.assertRaises(ValueError):engine.ai_layout_response(broken)
 def test_character_image_preservation_and_reject_missing_duplicate_or_edited(self):
  original=page();original['blocks'].append({'id':'img','kind':'image','src':'photo.png','page':1,'caption':'原图注','reviewed':True});untouched=copy.deepcopy(original)
  groups=[{'ids':['t0'],'kind':'heading','level':2,'text':'模型改写不采用'},{'ids':['i0'],'kind':'image'},{'ids':['t1'],'kind':'text'}]
  result=engine.ai_layout_apply(original,groups)
  self.assertEqual(result['blocks'][0]['text'],'合成菜谱');self.assertEqual(result['blocks'][2]['text'],'原料：盐2.5克。');self.assertEqual(result['blocks'][1]['caption'],'原图注');self.assertEqual(original,untouched)
  for groups in [[{'ids':['t0'],'kind':'text'}],[{'ids':['t0','t0'],'kind':'text'}],[{'ids':['t0','t1','i0'],'kind':'text'}]]:
   with self.assertRaises(ValueError):engine.ai_layout_apply(original,groups)
  original['blocks'][0]['text']='成合菜谱\n原料：盐2.5克。'
  with self.assertRaises(ValueError):engine.ai_layout_units(original)
  original['blocks'][0]['text']='已人工改字'
  with self.assertRaises(ValueError):engine.ai_layout_units(original)
 def test_payload_has_no_key_and_bounded_generation(self):
  seen=[];engine.ai_layout_request(ENDPOINT,'SECRET',page(),b'png',transport=lambda payload:seen.append(payload) or response())
  self.assertEqual(seen[0]['max_tokens'],8192);self.assertFalse(seen[0]['enable_thinking']);self.assertNotIn('SECRET',json.dumps(seen));self.assertIn('data:image/png;base64',json.dumps(seen))

class AiApiTests(unittest.TestCase):
 def setUp(self):
  import fitz
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.pdf=self.root/'source.pdf'
  doc=fitz.open();doc.new_page();doc.new_page();doc.save(self.pdf);doc.close()
  self.original={'id':BID,'title':'合成样书','page_count':2,'revision':1,'status':'done','pages':[page(1),page(2)]}
  atomic_json(self.root/'books'/BID/'book.json',self.original)
  atomic_json(self.root/'jobs.json',{'test':{'id':'test','book_id':BID,'source':str(self.pdf),'status':'done','indices':[0,1],'total':2,'done':2,'title':'合成样书'}})
  self.client=TestClient(create_app(self.root,'local'));self.client.__enter__();self.client.put('/api/ai/settings',json={'endpoint':ENDPOINT,'api_key':'SYNTHETIC-SECRET'}).raise_for_status()
 def tearDown(self):self.client.__exit__(None,None,None);self.temp.cleanup()
 def start(self,pages='1-2',**extra):return self.client.post('/api/books/'+BID+'/ai-trial',json={'pages':pages,'revision':1,'consent':True,**extra})
 def wait(self):
  for _ in range(150):
   result=self.client.get('/api/ai/trials').json()[0]
   if result['status'] not in ('running','stopping'):return result
   time.sleep(.02)
  self.fail('trial timed out')
 def test_no_paid_request_without_consent_valid_pages_or_revision_and_key_not_persisted(self):
  with patch.object(engine,'ai_layout_request') as request:
   self.assertEqual(self.start(consent=False).status_code,400);self.assertEqual(self.start('1-21').status_code,400);self.assertEqual(self.start('1',revision=0).status_code,409)
   self.assertEqual(self.client.post('/api/books/'+BID+'/ai-trial',headers={'origin':'https://evil.test'},json={}).status_code,403);request.assert_not_called()
  self.assertNotIn('SYNTHETIC-SECRET',self.client.get('/api/ai/settings').text);self.assertNotIn('SYNTHETIC-SECRET',(self.root/'private/ai-settings.json').read_text())
  with TestClient(create_app(self.root/'server','server')) as server:self.assertEqual(server.get('/api/ai/settings').status_code,403)
 def test_separate_result_export_privacy_and_original_page_access(self):
  with patch.object(engine,'ai_layout_request',return_value=response()) as request:
   self.start().raise_for_status();result=self.wait();self.assertEqual(result['status'],'done');self.assertEqual(request.call_count,2)
  self.assertEqual(result['done'],[1,2]);self.assertGreater(result['estimated_yuan'],0);self.assertEqual(json.loads((self.root/'books'/BID/'book.json').read_text()),self.original)
  copied=self.client.get('/api/books/'+result['result_id']).json();self.assertEqual(copied['pages'][0]['blocks'][1]['text'],'原料：盐2.5克。');self.assertNotIn('source',result);self.assertNotIn('endpoint',result)
  download=self.client.get('/api/books/'+result['result_id']+'/export');download.raise_for_status()
  with zipfile.ZipFile(io.BytesIO(download.content)) as z:self.assertEqual(z.namelist(),['book.json']);self.assertNotIn(b'SYNTHETIC-SECRET',z.read('book.json'))
  self.assertEqual(self.client.get('/api/books/'+result['result_id']+'/original/1').status_code,200)
 def test_failed_output_records_usage_without_auto_retry_and_resume_skips_saved(self):
  with patch.object(engine,'ai_layout_request',side_effect=[response(),response([{'ids':['t0'],'kind':'text'}])]) as request:
   self.start().raise_for_status();result=self.wait();self.assertEqual(result['status'],'failed');self.assertEqual(request.call_count,2)
  self.assertEqual(result['done'],[1]);self.assertEqual(result['prompt_tokens'],2000)
  with patch.object(engine,'ai_layout_request',return_value=response()) as request:
   self.client.post('/api/ai/trials/'+result['id']+'/resume').raise_for_status();result=self.wait();self.assertEqual(result['status'],'done');self.assertEqual(request.call_count,1)
  self.assertEqual(len(self.client.get('/api/books/'+result['result_id']).json()['pages']),2)
 def test_stop_prevents_next_request_and_running_trial_blocks_delete_update(self):
  entered=threading.Event();release=threading.Event()
  def hold(*args):entered.set();release.wait(3);return response()
  with patch.object(engine,'ai_layout_request',side_effect=hold) as request:
   self.start().raise_for_status();self.assertTrue(entered.wait(2));trial=self.client.get('/api/ai/trials').json()[0]
   self.assertEqual(self.client.delete('/api/books/'+BID).status_code,409);self.assertEqual(self.client.delete('/api/books/'+trial['result_id']).status_code,409);self.assertEqual(self.client.post('/api/update/install').status_code,409)
   self.client.post('/api/ai/trials/'+trial['id']+'/stop').raise_for_status();release.set();result=self.wait();self.assertEqual(result['status'],'paused');self.assertEqual(request.call_count,1);self.assertEqual(result['done'],[1])
