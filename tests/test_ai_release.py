"""Exercise the actual shipped desktop ZIP with synthetic PDFs and mocked paid calls."""
import importlib.util,json,subprocess,sys,tempfile,unittest,zipfile
from pathlib import Path

class DesktopReleaseTests(unittest.TestCase):
 def test_shipped_ai_trial(self):
  if importlib.util.find_spec('fitz') is None:self.skipTest('PyMuPDF required for desktop release integration; CI installs it')
  root=Path(__file__).resolve().parents[1]
  manifest=json.loads((root/'releases/latest.json').read_text())
  with tempfile.TemporaryDirectory() as directory:
   with zipfile.ZipFile(root/'releases'/manifest['url']) as archive:archive.extractall(directory)
   source=root/'tests/ai_desktop_cases.py'
   Path(directory,'test_ai.py').write_bytes(source.read_bytes())
   result=subprocess.run([sys.executable,'-m','unittest','test_ai','-v'],cwd=directory,capture_output=True,text=True,timeout=120)
   self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
