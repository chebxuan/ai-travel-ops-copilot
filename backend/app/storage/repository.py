"""Reconstruct existing domain shapes from normalized relational tables."""
from contextlib import contextmanager
from contextvars import ContextVar
from backend.app.storage.connection import settings, read_connection

_snapshot = ContextVar('travel_catalog_snapshot', default=None)


def database_enabled():
    if _snapshot.get() is not None:
        return True
    source = settings()['source']
    if source not in ('files', 'postgres'):
        raise RuntimeError('TRAVEL_DATA_SOURCE must be files or postgres')
    return source == 'postgres'


def read_dataset(connection):
    products = []
    for row in connection.execute('SELECT * FROM products ORDER BY id').fetchall():
        id = row['id']
        plans = connection.execute('SELECT day AS day_number, raw_text, activity_names FROM product_days WHERE product_id=%s ORDER BY day', (id,)).fetchall()
        product = {'product_id': id, 'city': row['city'], 'product_name': row['name'], 'duration_days': row['days'], 'itinerary_text': row['itinerary'], 'day_plans': plans, 'metadata': row['metadata']}
        for kind in ('regular', 'optional'):
            product[kind + '_items'] = [r['name'] for r in connection.execute('SELECT name FROM product_item_names WHERE product_id=%s AND kind=%s ORDER BY position', (id,kind))]
            product[kind + '_item_codes'] = [r['service_code'] for r in connection.execute('SELECT service_code FROM product_code_refs WHERE product_id=%s AND kind=%s ORDER BY position', (id,kind))]
        products.append(product)
    costs, versions = {}, {}
    for row in connection.execute('SELECT s.*,p.price,p.price_peak,p.state,p.id AS price_version FROM service_items s JOIN service_prices p ON p.service_code=s.code AND p.active ORDER BY s.code'):
        costs.setdefault(row['city'], {})[row['code']] = {'name': row['name'], 'category': row['category'], 'price': float(row['price'] or 0), 'price_peak': float(row['price_peak'] or 0), 'unit': row['unit'], 'note': row['note']}
        versions[row['code']] = row['price_version']
    scopes = {row['product_id']: row['rules'] for row in connection.execute('SELECT * FROM cost_scopes')}
    for row in connection.execute('SELECT * FROM route_branches ORDER BY product_id,position'):
        spec = scopes[row['product_id']]
        spec['day'] = row['day']
        branch = {'label': row['label'], 'excluded_optional': row['excluded_optional']}
        if row['car_code']: branch['car_code'] = row['car_code']
        for kind, target in [('common', 'common_codes'),('branch', 'codes')]:
            codes = [r['service_code'] for r in connection.execute('SELECT service_code FROM branch_items WHERE product_id=%s AND choice=%s AND kind=%s ORDER BY position', (row['product_id'],row['choice'],kind))]
            if kind == 'common': spec[target] = codes
            else: branch[target] = codes
        spec.setdefault('branches', {})[row['choice']] = branch
    policies = connection.execute('SELECT * FROM pricing_policies WHERE active').fetchall()
    if len(policies) != 1 or not products:
        raise RuntimeError('Database catalogue has not been imported')
    policy = policies[0]
    policy = {key: str(policy[key]) if key == 'multiplier' else policy[key] for key in ['id','multiplier','currency','rounding','decimal_places','supplier_surcharge']}
    documents = {row['key']: row['document'] for row in connection.execute('SELECT * FROM content_documents')}
    return {'products': products, 'costs': costs, 'configuration': {'version': 'postgres-v1', 'products': scopes, 'sales_policy': policy}, 'documents': documents, 'price_versions': versions}


def dataset():
    cached = _snapshot.get()
    if cached is not None: return cached
    with read_connection() as connection:
        return read_dataset(connection)


@contextmanager
def runtime_snapshot():
    if not database_enabled():
        yield
        return
    with read_connection() as connection:
        token = _snapshot.set(read_dataset(connection))
        try: yield
        finally: _snapshot.reset(token)
