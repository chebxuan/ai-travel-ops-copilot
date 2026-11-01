"""Provision a separate insert-only intake role without granting catalogue maintenance."""
import json
import secrets
from psycopg import sql
from psycopg.conninfo import make_conninfo
from backend.app.core.paths import ROOT
from backend.app.storage.connection import settings


def configure(connection):
    config = settings()
    role = connection.execute("SELECT 1 FROM pg_roles WHERE rolname='travel_intake'").fetchone()
    new_url = None
    if not role or not config['intake_url']:
        password = secrets.token_urlsafe(32)
        command = 'ALTER ROLE' if role else 'CREATE ROLE'
        connection.execute(sql.SQL(command + ' travel_intake LOGIN PASSWORD {}').format(sql.Literal(password)))
        new_url = make_conninfo(config['admin_url'], user='travel_intake', password=password)
    connection.execute('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM travel_intake')
    connection.execute('GRANT USAGE ON SCHEMA public TO travel_intake')
    for table in ['products','product_days','product_item_names','product_code_refs','service_items','service_prices','cost_scopes','route_branches','branch_items','pricing_policies','content_documents']:
        connection.execute(sql.SQL('GRANT SELECT ON {} TO travel_intake').format(sql.Identifier(table)))
    connection.execute('GRANT SELECT, INSERT ON journey_enquiries TO travel_intake')
    connection.execute('GRANT INSERT ON quote_snapshots,enquiry_notifications TO travel_intake')
    # Commit privileges before installing usable connection credentials.
    connection.commit()
    if new_url:
        path = ROOT / '.env.database.local'
        lines = [line for line in path.read_text().splitlines() if not line.startswith('TRAVEL_INTAKE_DATABASE_URL=')]
        path.write_text('\n'.join(lines) + '\nTRAVEL_INTAKE_DATABASE_URL=' + json.dumps(new_url) + '\n')
        path.chmod(0o600)
