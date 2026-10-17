"""Single-owner authentication, password hash and session CSRF."""
import hashlib
import hmac
import os
import secrets
import time
from fastapi import HTTPException


def hash_password(password, salt=None):
    if len(password)<12:
        raise ValueError('密码至少12位')
    salt=salt or secrets.token_hex(16)
    digest=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
    return f'pbkdf2_sha256$600000${salt}${digest}'


def verify_password(password, encoded):
    try:
        algorithm,rounds,salt,digest=encoded.split('$')
        if algorithm!='pbkdf2_sha256' or int(rounds)!=600000:return False
        actual=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),int(rounds)).hex()
        return hmac.compare_digest(actual,digest)
    except (ValueError,TypeError):return False


def csrf_token(request):
    if 'csrf' not in request.session:request.session['csrf']=secrets.token_urlsafe(32)
    return request.session['csrf']


def require_csrf(request, token):
    expected=request.session.get('csrf','')
    if not expected or not token or not hmac.compare_digest(expected,token):
        raise HTTPException(403,'页面已过期，请刷新后重试')


def require_login(request):
    if not request.session.get('owner'):raise HTTPException(401,'请先登录')


# A single web process, bounded login limiter, never records passwords.
_attempts={}
def login_allowed(address):
    now=time.monotonic()
    for key in list(_attempts):
        if _attempts[key][1]<now:del _attempts[key]
    if len(_attempts)>10000:return False
    return _attempts.get(address,(0,0))[0]<10


def login_failed(address):
    count,until=_attempts.get(address,(0,time.monotonic()+300))
    _attempts[address]=(count+1,until)
