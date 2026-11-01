"""User-run production persistence and isolated restore checks; never expose row data."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
COMPOSE = ROOT / 'deploy/compose.sh'


def db_command(database, *args):
    if not re.fullmatch(r'travel_copilot(?:_[a-z0-9_]+)?', database):
        raise ValueError('Invalid database name')
    return ['sh', str(COMPOSE), 'exec', '-T', 'db', 'psql', '-U', 'travel_owner', '-d', database, '-v', 'ON_ERROR_STOP=1', '-qAt', *args]


def capture(database):
    names = subprocess.run(db_command(database, '-c', "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"), check=True, capture_output=True, text=True).stdout.splitlines()
    if not names or any(not re.fullmatch(r'[a-z_][a-z0-9_]*', name) for name in names):
        raise ValueError('Unexpected or empty public schema')
    statements = ['BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY;']
    for name in names:
        statements.append(f'''SELECT json_build_object('table','{name}','count',count(*),'digest',md5(coalesce(jsonb_agg(row ORDER BY row::text),'[]'::jsonb)::text)) FROM (SELECT to_jsonb(t) AS row FROM "{name}" t) source;''')
    statements.append('COMMIT;')
    result = subprocess.run(db_command(database), input='\n'.join(statements), check=True, capture_output=True, text=True)
    tables = [json.loads(line) for line in result.stdout.splitlines() if line.startswith('{')]
    if len(tables) != len(names):
        raise ValueError('Incomplete database snapshot')
    return {row['table']: {'count': row['count'], 'digest': row['digest']} for row in tables}


def write_snapshot(path, tables):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as output:
        json.dump({'captured_at': datetime.now(timezone.utc).isoformat(), 'tables': tables}, output, indent=2)
    print('Private snapshot saved: ' + str(path))


def compare(expected, actual):
    changes = sorted(name for name in set(expected) | set(actual) if expected.get(name) != actual.get(name))
    if changes:
        raise ValueError('Data changed in tables: ' + ', '.join(changes) + '. Check legitimate new enquiries/maintenance before treating this as loss.')
    print('PASS: all ' + str(len(actual)) + ' public tables have matching row counts and content digests. No customer fields printed.')


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    snapshot = sub.add_parser('snapshot'); snapshot.add_argument('--output', type=Path, required=True)
    check = sub.add_parser('compare'); check.add_argument('--baseline', type=Path, required=True)
    restore = sub.add_parser('restore'); source = restore.add_mutually_exclusive_group(required=True); source.add_argument('--backup', type=Path); source.add_argument('--latest-backup', action='store_true'); restore.add_argument('--baseline', type=Path, required=True)
    args = parser.parse_args()
    if args.action == 'snapshot':
        write_snapshot(args.output.resolve(), capture('travel_copilot'))
    elif args.action == 'compare':
        compare(json.loads(args.baseline.read_text())['tables'], capture('travel_copilot'))
    else:
        if args.latest_backup:
            backups = [p for p in (ROOT / '.local/backups').glob('*.dump') if p.is_file() and not p.is_symlink()]
            if not backups:
                raise ValueError('No project backups available; run deploy/backup.sh first.')
            backup = max(backups, key=lambda path: path.stat().st_mtime_ns).resolve()
        else:
            backup = args.backup.resolve()
        print('Verifying backup: ' + str(backup))
        if not backup.is_file() or not backup.is_relative_to(ROOT / '.local/backups'):
            raise ValueError('Use an existing backup from this project .local/backups directory.')
        name = 'travel_copilot_restore_' + datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')
        # TOC validation precedes creating a fresh database. Never overwrite a live database.
        command = ['sh', str(COMPOSE), 'exec', '-T', 'db']
        with backup.open('rb') as stream:
            subprocess.run([*command, 'pg_restore', '--list'], stdin=stream, stdout=subprocess.DEVNULL, check=True)
        subprocess.run([*command, 'createdb', '-U', 'travel_owner', name], check=True)
        print('Created isolated restore database: ' + name)
        with backup.open('rb') as stream:
            subprocess.run([*command, 'pg_restore', '-U', 'travel_owner', '-d', name, '--single-transaction', '--exit-on-error'], stdin=stream, check=True)
        compare(json.loads(args.baseline.read_text())['tables'], capture(name))
        print('Live database/configuration unchanged. Restore database retained for review: ' + name)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        # Do not echo SQL stderr or configuration, which may include private values.
        raise SystemExit('Verification failed: ' + (str(error) if isinstance(error, ValueError) else type(error).__name__)) from None
