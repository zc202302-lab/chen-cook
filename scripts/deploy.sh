#!/usr/bin/env bash
set -Eeuo pipefail
cd /opt/chen-cook
exec 9>/run/lock/chen-cook-deploy.lock
flock -n 9 || exit 0
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo '检测到受管理源码有本地修改，停止自动更新'; exit 1
fi
target="${1:-$(git rev-parse HEAD)}"
git rev-parse --verify "$target^{commit}" >/dev/null
old="$(git rev-parse HEAD)"
mkdir -p /var/backups/chen-cook
if [[ -f /var/lib/chen-cook/catalogue.sqlite3 ]]; then
  .venv/bin/python - <<'PY'
import sqlite3,datetime
from pathlib import Path
backup=Path('/var/backups/chen-cook')/('catalogue-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S')+'.sqlite3')
with sqlite3.connect('/var/lib/chen-cook/catalogue.sqlite3') as source,sqlite3.connect(backup) as dest:
    source.backup(dest)
    assert dest.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
backup.chmod(0o600)
PY
fi
rollback() {
  trap - ERR
  set +e
  echo '更新失败，恢复上一源码与服务；保留全部书刊数据和备份。' >&2
  if [[ "$old" != "$target" ]]; then
    git switch --detach "$old"
    .venv/bin/pip install -q -r requirements.txt
    install -m 0644 deploy/chen-cook.service /etc/systemd/system/chen-cook.service
    install -m 0644 deploy/chen-cook-worker.service /etc/systemd/system/chen-cook-worker.service
    printf 'COOK_REVISION=%s\n' "$old" > /etc/chen-cook/revision.env
    systemctl daemon-reload
    systemctl restart chen-cook chen-cook-worker
  fi
  exit 1
}
trap rollback ERR
git merge --ff-only "$target"
if [[ "$old" != "$target" ]] && ! git diff --quiet "$old" "$target" -- requirements.txt; then
  .venv/bin/pip install -q -r requirements.txt
fi
.venv/bin/python -m compileall -q cooklib
install -m 0644 deploy/chen-cook.service /etc/systemd/system/chen-cook.service
install -m 0644 deploy/chen-cook-worker.service /etc/systemd/system/chen-cook-worker.service
printf 'COOK_REVISION=%s\n' "$target" > /etc/chen-cook/revision.env
systemctl daemon-reload
systemctl restart chen-cook chen-cook-worker
for attempt in {1..15}; do
  if result="$(curl --max-time 3 -fsS http://172.19.0.1:8020/health)"; then
    if .venv/bin/python - "$result" "$target" <<'PY'
import json,sys
body=json.loads(sys.argv[1]);assert body['ok'] and body['service']=='chen-cook' and body['revision']==sys.argv[2]
PY
    then
      echo "独立书刊站已更新：$target"
      exit 0
    fi
  fi
  sleep 1
done
echo '新版本健康检查失败' >&2
rollback
