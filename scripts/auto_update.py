"""Pull only successful push/main CI revisions from the public, fixed repository."""
import json
from pathlib import Path
import re
import subprocess
import urllib.request

ROOT=Path('/opt/chen-cook')
url='https://api.github.com/repos/zc202302-lab/chen-cook/actions/workflows/ci.yml/runs?branch=main&event=push&status=success&per_page=5'
request=urllib.request.Request(url,headers={'Accept':'application/vnd.github+json','User-Agent':'chen-cook-updater'})
with urllib.request.urlopen(request,timeout=20) as response:data=json.load(response)
subprocess.run(['git','fetch','origin','main'],cwd=ROOT,check=True,timeout=60)
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
for run in data.get('workflow_runs',[]):
    target=run.get('head_sha','')
    if not re.fullmatch('[0-9a-f]{40}',target) or run.get('event')!='push' or run.get('head_branch')!='main' or run.get('conclusion')!='success':continue
    if target==head:break
    if subprocess.run(['git','merge-base','--is-ancestor',head,target],cwd=ROOT).returncode:continue
    if subprocess.run(['git','merge-base','--is-ancestor',target,'origin/main'],cwd=ROOT).returncode:continue
    subprocess.run(['bash',str(ROOT/'scripts/deploy.sh'),target],check=True,timeout=600)
    break
