#!/usr/bin/env bash
set -Eeuo pipefail
[[ $(id -u) == 0 ]] || { echo '请在青岛服务器以root执行首次安装'; exit 1; }
cd /opt/chen-cook
command -v python3 >/dev/null
command -v docker >/dev/null
# Do not bind a public address or silently take another service's port.
python3 - <<'PY'
import socket
address='172.19.0.1'
try:
 with socket.socket() as server:server.bind((address,8020))
except OSError:
 import subprocess
 if subprocess.run(['systemctl','is-active','--quiet','chen-cook']).returncode:
  raise SystemExit('172.19.0.1:8020不可用，未安装；请核对Caddy网桥和端口占用')
PY
python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
id chencook >/dev/null 2>&1 || useradd --system --home-dir /var/lib/chen-cook --shell /usr/sbin/nologin chencook
install -d -o chencook -g chencook -m 0700 /var/lib/chen-cook
install -d -m 0700 /etc/chen-cook
.venv/bin/python scripts/configure.py
.venv/bin/python scripts/migrate_library.py
chown -R chencook:chencook /var/lib/chen-cook
find /var/lib/chen-cook -type d -exec chmod 0700 {} +
find /var/lib/chen-cook -type f -exec chmod 0600 {} +
bash scripts/deploy.sh
.venv/bin/python scripts/connect_caddy.py
install -m 0644 deploy/chen-cook-update.service /etc/systemd/system/chen-cook-update.service
install -m 0644 deploy/chen-cook-update.timer /etc/systemd/system/chen-cook-update.timer
systemctl daemon-reload
systemctl enable --now chen-cook chen-cook-worker chen-cook-update.timer
echo '独立站已安装。请确认cook的A记录为47.104.233.200，然后访问 https://cook.ziboxiaozhushou.cn'
echo '首次登录后，在网页设置OSS，再从“添加书刊”选择PDF入库。后续通过CI的main更新由定时器自动安装。'
curl --max-time 20 -fsS https://cook.ziboxiaozhushou.cn/health || echo '本地服务正常；公网HTTPS尚待DNS/证书联通，请提供此处输出核对。'
