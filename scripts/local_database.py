"""Manage this project's isolated PostgreSQL development cluster, never global services."""
import argparse
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BASE = ROOT / '.local/database'
DATA = BASE / 'pgdata'
PORT = '55432'


def run(args):
    subprocess.run(args, check=True)


def report_status(command):
    """Preserve pg_ctl exit codes without treating a stopped server as a crash."""
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode == 0:
        print('本地项目数据库正在运行（127.0.0.1:55432）。')
    elif result.returncode == 3:
        print('本地项目数据库未运行，已有数据不会因此被删除。')
        print('需要使用时，请执行：.venv/bin/python -B scripts/local_database.py start')
    else:
        print('无法确认本地数据库状态，请检查数据目录与 PostgreSQL 工具。')
        if result.stderr.strip():
            print(result.stderr.strip(), file=sys.stderr)
    return result.returncode


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['init','start','stop','status','console','backup','restore'])
    parser.add_argument('--output')
    parser.add_argument('--input')
    parser.add_argument('--database')
    args = parser.parse_args()
    for command in ['initdb','pg_ctl','psql','pg_dump','pg_restore']:
        if not shutil.which(command): raise SystemExit('Install PostgreSQL command line tools first: ' + command)
    BASE.mkdir(parents=True, exist_ok=True, mode=0o700)
    if args.action == 'init':
        if DATA.exists() or (ROOT / '.env.database.local').exists():
            raise SystemExit('Database files/config already exist. Use start; initialization never overwrites them.')
        owner_password = secrets.token_urlsafe(32)
        app_password = secrets.token_urlsafe(32)
        password_file = BASE / 'init-password'
        password_file.write_text(owner_password);password_file.chmod(0o600)
        try:
            run(['initdb','-D',str(DATA),'--username=travel_owner','--pwfile='+str(password_file),'--auth-host=scram-sha-256','--auth-local=scram-sha-256','--encoding=UTF8','--locale=C'])
        finally: password_file.unlink(missing_ok=True)
        with (DATA / 'postgresql.conf').open('a') as f:
            f.write("\nlisten_addresses = '127.0.0.1'\nport = 55432\nunix_socket_directories = ''\n")
        run(['pg_ctl','-D',str(DATA),'-l',str(BASE/'postgres.log'),'start','-w'])
        import psycopg
        from psycopg import sql
        owner_url = f'postgresql://travel_owner:{owner_password}@127.0.0.1:{PORT}/travel_copilot'
        with psycopg.connect(owner_url.replace('/travel_copilot','/postgres'), autocommit=True) as connection:
            connection.execute(sql.SQL('CREATE ROLE travel_app LOGIN PASSWORD {}').format(sql.Literal(app_password)))
            connection.execute('CREATE DATABASE travel_copilot OWNER travel_owner')
        config = ROOT / '.env.database.local'
        config.write_text(f'TRAVEL_DATA_SOURCE=files\nTRAVEL_DATABASE_URL=postgresql://travel_app:{app_password}@127.0.0.1:{PORT}/travel_copilot\nTRAVEL_ADMIN_DATABASE_URL={owner_url}\n')
        config.chmod(0o600)
        print('Local database created: 127.0.0.1:55432 / travel_copilot. Credentials saved privately; source remains files until verification.')
    elif args.action in ('start','stop','status'):
        if not DATA.exists(): raise SystemExit('Run init first')
        command = ['pg_ctl','-D',str(DATA)]
        if args.action == 'start': command += ['-l',str(BASE/'postgres.log'),'start','-w']
        elif args.action == 'stop': command += ['stop','-m','fast','-w']
        else: command += ['status']
        if args.action == 'status':
            raise SystemExit(report_status(command))
        run(command)
    else:
        from backend.app.storage.connection import settings
        from psycopg.conninfo import conninfo_to_dict
        info = conninfo_to_dict(settings()['admin_url'])
        env = {**os.environ, 'PGPASSWORD': info['password']}
        connection_args = ['-h',info['host'],'-p',info['port'],'-U',info['user'],'-d',info['dbname']]
        if args.action == 'console': subprocess.run(['psql', *connection_args],env=env,check=True)
        elif args.action == 'backup':
            if not args.output: raise SystemExit('backup requires --output path.dump')
            path = Path(args.output)
            if path.exists(): raise SystemExit('Backup path exists; choose a new file')
            path.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['pg_dump',*connection_args,'-Fc','-f',str(path)],env=env,check=True)
            path.chmod(0o600)
            print('Backup saved: ' + str(path))
        else:
            import re
            import psycopg
            from psycopg import sql
            from psycopg.conninfo import make_conninfo
            name = args.database or ''
            if not re.fullmatch(r'travel_copilot_[a-z0-9_]+', name):
                raise SystemExit('Restore requires a new database named travel_copilot_<suffix>; it never overwrites the active database.')
            path = Path(args.input or '')
            if not args.input or not path.is_file(): raise SystemExit('restore requires --input existing.dump')
            with psycopg.connect(make_conninfo(settings()['admin_url'], dbname='postgres'), autocommit=True) as connection:
                if connection.execute('SELECT 1 FROM pg_database WHERE datname=%s', (name,)).fetchone():
                    raise SystemExit('Target database exists; choose a new name')
                connection.execute(sql.SQL('CREATE DATABASE {} OWNER travel_owner').format(sql.Identifier(name)))
            target_args = ['-h',info['host'],'-p',info['port'],'-U',info['user'],'-d',name]
            subprocess.run(['pg_restore',*target_args,'--single-transaction','--exit-on-error',str(path)],env=env,check=True)
            print('Backup restored into '+name+'. Active configuration was not changed.')


if __name__ == '__main__': main()
