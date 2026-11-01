import os
from contextlib import contextmanager
from fastapi import HTTPException
from backend.app.core.paths import ROOT


def settings():
    from dotenv import dotenv_values
    local = dotenv_values(ROOT / '.env.database.local')
    def value(name, default=None):
        return os.environ.get(name, local.get(name, default))
    return {'source': value('TRAVEL_DATA_SOURCE', 'files'),
            'url': value('TRAVEL_DATABASE_URL'), 'admin_url': value('TRAVEL_ADMIN_DATABASE_URL'),
            'intake_url': value('TRAVEL_INTAKE_DATABASE_URL'),
            'ops_url': value('TRAVEL_OPS_DATABASE_URL'),
            'notification_url': value('TRAVEL_NOTIFICATION_DATABASE_URL')}


@contextmanager
def intake_connection():
    import psycopg
    from psycopg.rows import dict_row
    url = settings()['intake_url']
    if not url:
        raise RuntimeError('Enquiry storage is not configured')
    with psycopg.connect(url, connect_timeout=5, row_factory=dict_row) as connection:
        yield connection


@contextmanager
def connect(admin=False):
    import psycopg
    from psycopg.rows import dict_row
    url = settings()['admin_url' if admin else 'url']
    if not url:
        raise RuntimeError('Database connection is not configured')
    with psycopg.connect(url, connect_timeout=5, row_factory=dict_row) as connection:
        yield connection


@contextmanager
def read_connection():
    import psycopg
    try:
        with connect() as connection:
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            yield connection
    except (RuntimeError, psycopg.Error):
        # Never expose connection strings or silently read obsolete CSV totals.
        raise HTTPException(503, detail={'code': 'DATABASE_UNAVAILABLE'}) from None


@contextmanager
def restricted_connection(kind):
    import psycopg
    from psycopg.rows import dict_row
    if kind not in ('ops', 'notification'):
        raise ValueError('Unknown database role')
    url = settings()[kind + '_url']
    if not url:
        raise RuntimeError('Restricted connection is not configured')
    with psycopg.connect(url, connect_timeout=5, row_factory=dict_row) as connection:
        yield connection
