"""Run locally on the server; credentials never travel through GitHub/chat."""
import getpass
from pathlib import Path
import os
import secrets
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from cooklib.auth import hash_password

path=Path('/etc/chen-cook/site.env')
if path.exists():
    print('保留已有独立站账户配置')
    raise SystemExit(0)
password=getpass.getpass('设置独立书刊站登录密码（至少12位，不显示）：')
if password!=getpass.getpass('再次输入密码：'):raise SystemExit('两次密码不一致，未保存')
hashed=hash_password(password)
path.parent.mkdir(parents=True,exist_ok=True)
fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'w') as file:
    file.write(f'COOK_DATA_DIR=/var/lib/chen-cook\nCOOK_SESSION_SECRET={secrets.token_hex(32)}\nCOOK_PASSWORD_HASH={hashed}\nCOOK_SECURE_COOKIE=1\n')
print('独立账户配置已保存')
