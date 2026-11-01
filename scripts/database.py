"""Database review, schema migration, non-overwriting import and maintenance."""
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from backend.app.storage.connection import connect
from backend.app.storage.importer import read_sources, migrate, import_data


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    for action in ['audit','migrate','import','status','activate','use-files','intake','operations']: sub.add_parser(action)
    args = parser.parse_args()
    if args.action in ('activate','use-files'):
        path = ROOT / '.env.database.local'
        if not path.exists(): raise SystemExit('Initialize the local database first')
        if args.action == 'activate':
            report = ROOT / '.local/database/verification.json'
            if not report.exists() or not json.loads(report.read_text()).get('passed'): raise SystemExit('Run database verification before activation')
            from scripts.verify_database import digest
            from backend.app.storage.repository import read_dataset
            verified = json.loads(report.read_text())
            with connect(admin=True) as connection:
                current = digest(read_dataset(connection))
            if current != verified['database_digest'] or read_sources()['fingerprint'] != verified['source_fingerprint']:
                raise SystemExit('Data changed since verification. Run database verification again before activation.')
        lines = [line for line in path.read_text().splitlines() if not line.startswith('TRAVEL_DATA_SOURCE=')]
        path.write_text('\n'.join(lines)+ '\nTRAVEL_DATA_SOURCE='+('postgres' if args.action=='activate' else 'files')+'\n');path.chmod(0o600)
        print('Data source selected. Restart the backend to ensure the configuration is reloaded.');return
    if args.action in ('audit','import'):
        data = read_sources()
        review = ROOT / '.local/database/import-review.json';review.parent.mkdir(parents=True,exist_ok=True)
        review.write_text(json.dumps(data['review'],ensure_ascii=False,indent=2));print(json.dumps(data['review'],ensure_ascii=False,indent=2))
        if args.action=='audit':return
    with connect(admin=True) as connection:
        if args.action=='migrate': migrate(connection);print('Schema migrations applied; runtime role is read-only.')
        elif args.action=='intake':
            from backend.app.storage.intake_setup import configure
            configure(connection)
            print('Restricted enquiry intake role configured. Credentials remain server-side.')
        elif args.action=='operations':
            from backend.app.storage.operations_setup import configure
            configure(connection)
            print('Restricted operations and notification roles configured.')
        elif args.action=='import': print(json.dumps(import_data(connection,data)))
        elif args.action=='status':
            for table in ['products','product_days','service_items','service_prices','route_branches','suppliers','supplier_services','quote_snapshots','journey_enquiries']:
                from psycopg import sql
                result=connection.execute(sql.SQL('SELECT count(*) AS n FROM {}').format(sql.Identifier(table))).fetchone();print(table,result['n'])


if __name__=='__main__':
    try:main()
    except Exception as error:
        # Database exceptions may contain credentials; disclose only a stable diagnosis.
        if isinstance(error, ValueError):raise SystemExit(str(error))
        raise SystemExit('Database operation failed ('+type(error).__name__+'). Check the local server and configuration.') from None
