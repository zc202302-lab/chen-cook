#!/usr/bin/env bash
set -Eeuo pipefail
cd /opt/chen-cook
exec 9>/run/lock/chen-cook-deploy.lock
flock -n 9 || exit 0
[[ -z "$(git status --porcelain --untracked-files=no)" ]] || { echo '受管理源码有本地修改，停止部署'; exit 1; }
target="${1:-$(git rev-parse HEAD)}"
[[ "$target" =~ ^[0-9a-f]{40}$ ]] || exit 1
git rev-parse --verify "$target^{commit}" >/dev/null
old="$(git rev-parse HEAD)"
backup="/var/backups/chen-cook/reader-deploy-$(date +%Y%m%d-%H%M%S)"
install -d -m 0700 "$backup"
cp /etc/systemd/system/chen-cook.service "$backup/chen-cook.service"
cp /etc/chen-cook/revision.env "$backup/revision.env"
worker_was_active=0
systemctl is-active --quiet chen-cook-worker && worker_was_active=1
rollback() {
  trap - ERR
  set +e
  echo '阅读端更新失败，恢复旧代码和服务；书刊数据保持原位。' >&2
  if [[ "$old" != "$target" ]]; then git switch --detach "$old"; fi
  .venv/bin/pip install -q -r requirements.txt
  cp "$backup/chen-cook.service" /etc/systemd/system/chen-cook.service
  cp "$backup/revision.env" /etc/chen-cook/revision.env
  systemctl daemon-reload
  systemctl restart chen-cook
  if [[ "$worker_was_active" == 1 ]]; then systemctl start chen-cook-worker; fi
  exit 1
}
trap rollback ERR
git merge --ff-only "$target"
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m compileall -q app.py server.py catalogue.py scripts
install -d -o chencook -g chencook -m 0700 /var/lib/chen-cook/reader
install -m 0644 deploy/chen-cook.service /etc/systemd/system/chen-cook.service
printf 'COOK_REVISION=%s\n' "$target" > /etc/chen-cook/revision.env
systemctl daemon-reload
systemctl restart chen-cook
for attempt in {1..25}; do
  if result="$(curl --max-time 3 -fsS http://172.19.0.1:8020/health)"; then
    if .venv/bin/python - "$result" "$target" <<'PY'
import json,sys
b=json.loads(sys.argv[1]);assert b['ok'] and b['service']=='chen-cook' and b['mode']=='reader' and b['revision']==sys.argv[2]
PY
    then
      systemctl stop chen-cook-worker.service || true
      systemctl disable chen-cook-worker.service || true
      printf '%s\n' "$target" > /var/lib/chen-cook/reader/deployed-revision
      echo "阅读端已更新：$target"
      exit 0
    fi
  fi
  sleep 1
done
rollback
