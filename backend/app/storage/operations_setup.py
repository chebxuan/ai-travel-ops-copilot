"""Least privilege grants shared by local setup and container bootstrap."""
import json
import secrets
from psycopg import sql
from psycopg.conninfo import make_conninfo
from backend.app.core.paths import ROOT
from backend.app.storage.connection import settings


def grant_operations(conn):
    for role in ('travel_ops', 'travel_notifier'):
        conn.execute(sql.SQL('REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}').format(sql.Identifier(role)))
        conn.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(role)))
    conn.execute('GRANT SELECT ON journey_enquiries,enquiry_status_events,enquiry_notifications TO travel_ops')
    conn.execute('GRANT UPDATE(status,status_version,updated_at) ON journey_enquiries TO travel_ops')
    conn.execute('GRANT INSERT ON enquiry_status_events TO travel_ops')
    conn.execute('GRANT SELECT ON enquiry_notifications TO travel_notifier')
    conn.execute('GRANT UPDATE(state,attempts,available_at,lease_id,lease_until,sent_at,last_error) ON enquiry_notifications TO travel_notifier')
    conn.execute('GRANT INSERT ON enquiry_notifications TO travel_intake')


def configure(conn):
    config = settings()
    additions = {}
    for role, key in [('travel_ops','ops_url'),('travel_notifier','notification_url')]:
        exists = conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s',(role,)).fetchone()
        if not exists or not config[key]:
            password = secrets.token_urlsafe(32)
            command = 'ALTER ROLE' if exists else 'CREATE ROLE'
            conn.execute(sql.SQL(command + ' {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}').format(sql.Identifier(role),sql.Literal(password)))
            variable = 'TRAVEL_OPS_DATABASE_URL' if key == 'ops_url' else 'TRAVEL_NOTIFICATION_DATABASE_URL'
            additions[variable] = make_conninfo(config['admin_url'],user=role,password=password)
    grant_operations(conn)
    conn.commit()
    if additions:
        path = ROOT / '.env.database.local'
        lines = [line for line in path.read_text().splitlines() if line.split('=',1)[0] not in additions]
        path.write_text('\n'.join(lines) + '\n' + ''.join(key+'='+json.dumps(value)+'\n' for key,value in additions.items()))
        path.chmod(0o600)
