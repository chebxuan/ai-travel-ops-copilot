"""User-run offline credential setup; no services, network calls or database access."""
import argparse
from datetime import datetime, timezone
import getpass
import hashlib
import os
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]


def read(path):
    if not path.exists():
        return [],{}
    lines=path.read_text().splitlines()
    values={}
    for line in lines:
        if '=' in line and not line.startswith('#'):
            key,value=line.split('=',1);values[key]=value.strip().strip('"').strip("'")
    return lines,values


def install(path,changes):
    lines,_=read(path)
    if path.exists():
        backup=path.with_name(path.name+'.ops-backup-'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        fd=os.open(backup,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as output:output.write(path.read_text())
    result=[line for line in lines if line.split('=',1)[0] not in changes]
    result.extend(key+'='+value for key,value in changes.items())
    temp=path.with_name(path.name+'.ops-temp-'+secrets.token_hex(8))
    fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as output:output.write('\n'.join(result)+'\n')
    os.replace(temp,path)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--target',choices=['local','production'],required=True)
    parser.add_argument('--backend-url',help='Local backend origin, e.g. http://127.0.0.1:8000; overrides a preserved old port')
    parser.add_argument('--rotate-login',action='store_true',help='Invalidate existing sessions by changing the password hash')
    args=parser.parse_args()
    if args.backend_url:
        if args.target!='local':parser.error('--backend-url is only for local setup.')
        try:
            url=urlsplit(args.backend_url)
            valid=(url.scheme=='http' and url.hostname in ('127.0.0.1','localhost','::1') and not url.username and not url.password and url.path in ('','/') and not url.query and not url.fragment and (url.port is None or 1<=url.port<=65535))
        except ValueError:
            valid=False
        if not valid:parser.error('Use a local HTTP backend origin without a path or credentials.')
    path=ROOT/('deploy/.env.production' if args.target=='production' else '.env')
    if not path.exists():parser.error('Create the existing backend/deployment configuration first.')
    _,config=read(path)
    changes={}
    required=['OPS_BACKEND_KEY','OPS_SESSION_KEY']
    if args.target=='production':required+=['DB_OPS_PASSWORD','DB_NOTIFICATION_PASSWORD']
    for key in required:
        if not config.get(key) or config[key]=='GENERATE_ME':changes[key]=secrets.token_hex(32)
    effective={**config,**changes}
    if args.rotate_login or not config.get('OPS_PASSWORD_HASH'):
        username=input('Operator username (ASCII, default operator): ').strip() or 'operator'
        if not re.fullmatch(r'[A-Za-z0-9_.@-]{1,80}',username):parser.error('Invalid username.')
        password=getpass.getpass('Operator password (at least 12 characters; hidden): ')
        if len(password)<12 or len(password)>256:parser.error('Password length must be 12–256.')
        if getpass.getpass('Confirm password: ')!=password:parser.error('Passwords differ.')
        salt=secrets.token_bytes(16)
        digest=hashlib.pbkdf2_hmac('sha256',password.encode(),salt,600000).hex()
        changes.update(OPS_USERNAME=username,OPS_PASSWORD_HASH='pbkdf2_sha256:600000:'+salt.hex()+':'+digest)
    if 'FEISHU_NOTIFICATIONS_ENABLED' not in config:changes['FEISHU_NOTIFICATIONS_ENABLED']='0'
    for key in ('FEISHU_WEBHOOK_URL','FEISHU_SIGNING_SECRET'):
        if key not in config:changes[key]=''
    if args.target=='local':
        frontend_path=ROOT/'frontend/.env.local'
        _,frontend=read(frontend_path)
        # Local and production credentials are deliberately generated separately.
        effective.update(changes)
        frontend_changes={key:effective[key] for key in ['OPS_BACKEND_KEY','OPS_SESSION_KEY','OPS_USERNAME','OPS_PASSWORD_HASH']}
        if not config.get('API_KEY'):parser.error('Set a local API_KEY first.')
        backend_url=args.backend_url.rstrip('/') if args.backend_url else frontend.get('BACKEND_BASE_URL') or 'http://127.0.0.1:8000'
        frontend_changes['BACKEND_BASE_URL']=backend_url
        # This is a copy of the existing backend key, never a key rotation.
        frontend_changes['BACKEND_API_KEY']=config['API_KEY']
        if backend_url!='http://127.0.0.1:8000':
            print('Custom local backend origin preserved. Ensure your backend uses the configured port; documented default is 8000.')
        if not config.get('OPS_SITE_ORIGIN'):changes['OPS_SITE_ORIGIN']='https://travel.example.com'
        install(frontend_path,frontend_changes)
    install(path,changes)
    print('Operations configuration saved privately. Existing application/database passwords preserved.')
    print('No services started, no database connection, no notifications sent. Follow docs/operations-guide.md.')


if __name__=='__main__':main()
