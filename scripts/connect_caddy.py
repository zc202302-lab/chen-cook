"""Add one host to the known Caddy container without replacing existing hosts."""
import datetime
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

CONTAINER='sms-relay-caddy-1'

def run(*args,**kwargs):return subprocess.run(args,check=True,**kwargs)


def main():
    meta=json.loads(subprocess.check_output(['docker','inspect',CONTAINER]))[0]
    mounts=meta.get('Mounts',[])
    destination='/etc/caddy/Caddyfile'
    candidates=[]
    for mount in mounts:
        dst=mount['Destination'].rstrip('/')
        if destination==dst or destination.startswith(dst+'/'):
            suffix=destination[len(dst):].lstrip('/')
            path=Path(mount['Source'])/suffix if suffix else Path(mount['Source'])
            if path.is_file():candidates.append(path)
    if len(candidates)!=1:
        raise SystemExit('无法唯一确定现有Caddy配置文件，未修改其他站点；请提供 docker inspect sms-relay-caddy-1 的 Mounts 信息。')
    source=candidates[0]
    original=source.read_text()
    host='cook.ziboxiaozhushou.cn'
    block=Path('/opt/chen-cook/deploy/Caddyfile.cook').read_text()
    if host in original:
        if block.strip() not in original:
            raise SystemExit('cook域名已有不同配置，未覆盖；请先核对现有上游。')
        print('Caddy已配置相同的独立cook站点，保留现有配置')
        return
    candidate=original.rstrip()+'\n\n'+block
    with tempfile.TemporaryDirectory() as tmp:
        file=Path(tmp)/'candidate.Caddyfile';file.write_text(candidate)
        run('docker','cp',str(file),f'{CONTAINER}:/tmp/chen-cook-candidate.Caddyfile')
        run('docker','exec',CONTAINER,'caddy','validate','--config','/tmp/chen-cook-candidate.Caddyfile','--adapter','caddyfile')
        backup=source.with_name(source.name+'.chen-cook-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
        shutil.copy2(source,backup)
        # Keep the original inode so file bind mounts see the updated content.
        source.write_text(candidate)
        try:run('docker','exec',CONTAINER,'caddy','reload','--config',destination,'--adapter','caddyfile')
        except Exception:
            source.write_text(original)
            run('docker','exec',CONTAINER,'caddy','reload','--config',destination,'--adapter','caddyfile')
            raise
    print('已增加独立cook站点，原Caddy站点保留。备份：'+str(backup))


if __name__=='__main__':main()
