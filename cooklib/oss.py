"""Private Qingdao OSS. Keys never enter HTML or logs."""
import json
import os
from pathlib import Path
import re
import tempfile
from .store import root


def settings_path():return root()/'oss-settings.json'


def configured():return settings_path().is_file()


def save_settings(bucket, access_id, access_secret):
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{1,61}[a-z0-9]',bucket):raise ValueError('Bucket名称格式错误')
    if not access_id.strip() or not access_secret.strip():raise ValueError('请填写OSS访问凭据')
    folder=root();folder.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(dir=folder,prefix='.oss-')
    try:
        os.fchmod(fd,0o600)
        with os.fdopen(fd,'w') as file:json.dump({'bucket':bucket,'access_id':access_id.strip(),'access_secret':access_secret.strip()},file)
        os.replace(name,settings_path())
    finally:
        Path(name).unlink(missing_ok=True)


def bucket_client():
    import oss2
    data=json.loads(settings_path().read_text())
    return oss2.Bucket(oss2.Auth(data['access_id'],data['access_secret']), 'https://oss-cn-qingdao.aliyuncs.com',data['bucket'],connect_timeout=30)


def valid_key(key):
    return isinstance(key,str) and key.startswith(('ebooks/','magazines/')) and key.lower().endswith('.pdf') and len(key)<=1024


def list_sources(prefix,marker=''):
    if prefix not in ('ebooks/','magazines/'):raise ValueError('未知书刊类型')
    result=bucket_client().list_objects(prefix=prefix,marker=marker,max_keys=100)
    return [o for o in result.object_list if valid_key(o.key)], result.next_marker if result.is_truncated else ''


def download(key,path):
    if not valid_key(key):raise ValueError('仅支持电子书或杂志目录中的PDF')
    bucket=bucket_client();size=bucket.head_object(key).content_length
    if not 0<size<=1024**3:raise ValueError('PDF大小须在1GiB以内')
    response=bucket.get_object(key)
    try:
        received=0
        with Path(path).open('wb') as output:
            while chunk:=response.read(1024*1024):
                received+=len(chunk)
                if received>size or received>1024**3:raise ValueError('下载大小不符')
                output.write(chunk)
        if received!=size:raise ValueError('下载不完整，请重试')
    finally:response.close()
