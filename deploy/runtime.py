"""Container startup, database provisioning and the existing maintenance CLI."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def connection_string(user, password_variable):
    from psycopg.conninfo import make_conninfo
    return make_conninfo(host=os.environ.get('DB_HOST', 'db'), port=os.environ.get('DB_PORT', '5432'),
                         dbname=os.environ.get('DB_NAME', 'travel_copilot'),
                         user=user, password=os.environ[password_variable])


def configure_connections(admin=False):
    os.environ['TRAVEL_DATA_SOURCE'] = 'postgres'
    if admin:
        os.environ['TRAVEL_ADMIN_DATABASE_URL'] = connection_string('travel_owner', 'DB_ADMIN_PASSWORD')
    else:
        os.environ['TRAVEL_DATABASE_URL'] = connection_string('travel_app', 'DB_READER_PASSWORD')
        os.environ['TRAVEL_INTAKE_DATABASE_URL'] = connection_string('travel_intake', 'DB_INTAKE_PASSWORD')
        os.environ['TRAVEL_OPS_DATABASE_URL'] = connection_string('travel_ops', 'DB_OPS_PASSWORD')


def bootstrap():
    import psycopg
    from psycopg import sql
    from psycopg.rows import dict_row
    from backend.app.storage.importer import migrate, read_sources, import_data
    with psycopg.connect(os.environ['TRAVEL_ADMIN_DATABASE_URL'], row_factory=dict_row) as conn:
        # Shared transaction lock serializes role changes, migrations and first import.
        conn.execute('SELECT pg_advisory_xact_lock(83109002)')
        for role, variable in [('travel_app', 'DB_READER_PASSWORD'), ('travel_intake', 'DB_INTAKE_PASSWORD'),
                               ('travel_ops','DB_OPS_PASSWORD'),('travel_notifier','DB_NOTIFICATION_PASSWORD')]:
            exists = conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (role,)).fetchone()
            command = 'ALTER ROLE' if exists else 'CREATE ROLE'
            conn.execute(sql.SQL(command + ' {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}').format(
                sql.Identifier(role), sql.Literal(os.environ[variable])))
        migrate(conn)
        # Seed only an empty catalogue. A deployed, maintained catalogue remains authoritative.
        if conn.execute('SELECT count(*) AS n FROM products').fetchone()['n'] == 0:
            import_data(conn, read_sources())
        conn.execute('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM travel_intake')
        conn.execute('GRANT USAGE ON SCHEMA public TO travel_intake')
        for table in ['products', 'product_days', 'product_item_names', 'product_code_refs',
                      'service_items', 'service_prices', 'cost_scopes', 'route_branches',
                      'branch_items', 'pricing_policies', 'content_documents']:
            conn.execute(sql.SQL('GRANT SELECT ON {} TO travel_intake').format(sql.Identifier(table)))
        conn.execute('GRANT SELECT, INSERT ON journey_enquiries TO travel_intake')
        conn.execute('GRANT INSERT ON quote_snapshots TO travel_intake')
        from backend.app.storage.operations_setup import grant_operations
        grant_operations(conn)
        count = conn.execute('SELECT count(*) AS n FROM products').fetchone()['n']
        if not count:
            raise RuntimeError('Empty catalogue after initialization')
    print('Database migrations, catalogue and restricted roles are ready. Products:', count)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else 'serve'
    if mode == 'check':
        import json
        import urllib.request
        request = urllib.request.Request('http://127.0.0.1:8000/api/v3/products',
                                        headers={'X-API-Key': os.environ['API_KEY']})
        with urllib.request.urlopen(request, timeout=7) as response:
            result = json.load(response)
            if not result.get('products'):
                raise RuntimeError('Catalogue unavailable')
        return
    if mode in ('bootstrap', 'maintain'):
        configure_connections(admin=True)
        if mode == 'bootstrap':
            bootstrap()
        else:
            sys.argv = ['maintain_database.py', *sys.argv[2:]]
            from scripts.maintain_database import main as maintain
            maintain()
    elif mode == 'notify':
        os.environ['TRAVEL_NOTIFICATION_DATABASE_URL'] = connection_string('travel_notifier','DB_NOTIFICATION_PASSWORD')
        from backend.app.services.enquiry_notifications import run
        run()
    elif mode == 'serve':
        configure_connections()
        os.execvp('uvicorn', ['uvicorn', 'backend.app.main:app', '--host', '0.0.0.0', '--port', '8000'])
    else:
        raise ValueError('Unknown container mode')


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        # Connection errors can contain secrets; never print them in container logs.
        raise SystemExit('Container operation failed: ' + type(error).__name__) from None
