"""Review and import only authoritative runtime sources; never merge private payments."""
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path
from psycopg.types.json import Jsonb
from backend.app.core.paths import ROOT
from backend.app.engines.city_config import CITY_COST_FILES
from backend.app.engines.cost_engine import safe_float
from scripts.normalize_product_library import build_product_record


def read_sources():
    base = ROOT / 'data/products'
    payload = json.loads((base / 'products.normalized.json').read_text())
    with (base / 'product_library.csv').open(encoding='utf-8-sig') as f:
        rebuilt = [build_product_record(row) for row in csv.DictReader(f, skipinitialspace=True)]
    if rebuilt != payload['products']:
        raise ValueError('CSV and normalized products differ. Review/rebuild before importing.')
    products = payload['products']
    if len({p['product_id'] for p in products}) != len(products): raise ValueError('Duplicate product IDs')
    services, seen = [], set()
    for city, relative in CITY_COST_FILES.items():
        with (ROOT / relative).open(encoding='utf-8-sig', newline='') as f:
            for row in csv.DictReader(f):
                code = (row.get('项目编号') or '').strip()
                if not code: continue
                if code in seen: raise ValueError('Duplicate service code: ' + code)
                seen.add(code)
                raw = (row.get('单价') or '').strip()
                raw_peak = (row.get('单价（旺季）') or '').strip()
                note = (row.get('项目备注') or '').strip()
                free = raw in ('免费', '0', '0.0') or ('用户确认' in note and '免费' in note)
                state = 'confirmed_free' if free else 'range_estimate' if '-' in raw else 'missing' if not raw else 'fixed'
                price = Decimal(str(safe_float(raw))) if raw or free else None
                peak = Decimal(str(safe_float(raw_peak))) if raw_peak else price
                if (price is not None and price < 0) or (peak is not None and peak < 0): raise ValueError('Negative price: ' + code)
                services.append({'code': code, 'city': city, 'name': (row.get('项目名称') or '').strip(), 'category': (row.get('服务类目') or '').strip(), 'unit': (row.get('单位') or '').strip(), 'note': note, 'description': (row.get('项目说明') or '').strip(), 'source_file': relative, 'price': price, 'price_peak': peak, 'state': state, 'raw_price': raw, 'raw_peak': raw_peak})
    missing = [code for p in products for code in p['regular_item_codes'] + p['optional_item_codes'] if code not in seen]
    if missing: raise ValueError('Unresolved service references: ' + ', '.join(sorted(set(missing))))
    scope = json.loads((base / 'cost_scope.json').read_text())
    for spec in scope['products'].values():
        for branch in spec.get('branches', {}).values():
            for code in spec.get('common_codes', []) + branch['codes'] + ([branch['car_code']] if branch.get('car_code') else []):
                if code not in seen: raise ValueError('Unresolved branch service: ' + code)
    documents = {key: json.loads((base / name).read_text()) for key,name in [('highlights','attraction_highlights.json'),('presentation','menu_presentation.json')]}
    paths = [base / name for name in ['product_library.csv','products.normalized.json','cost_scope.json','attraction_highlights.json','menu_presentation.json']] + [ROOT/path for path in CITY_COST_FILES.values()]
    sources = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    fingerprint = hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
    review = {'products': len(products), 'cities': len(CITY_COST_FILES), 'services': len(services), 'branches': sum(len(s.get('branches', {})) for s in scope['products'].values()), 'suppliers_imported': 0, 'missing_prices': [s['code'] for s in services if s['state']=='missing'], 'range_estimates': [s['code'] for s in services if s['state']=='range_estimate'], 'unresolved_optional_names': []}
    by_code = {s['code']:s for s in services}
    for product in products:
        for name in product['optional_items']:
            matches = [code for code in product['optional_item_codes'] if by_code[code]['name']==name]
            if len(matches) != 1: review['unresolved_optional_names'].append({'product': product['product_id'], 'name': name})
    return {'products': products, 'services': services, 'configuration': scope, 'documents': documents, 'sources': sources, 'fingerprint': fingerprint, 'review': review}


def migrate(connection):
    connection.execute('CREATE TABLE IF NOT EXISTS schema_migrations (version text PRIMARY KEY, checksum text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())')
    for path in sorted((Path(__file__).parent / 'migrations').glob('*.sql')):
        checksum = hashlib.sha256(path.read_bytes()).hexdigest()
        old = connection.execute('SELECT checksum FROM schema_migrations WHERE version=%s',(path.stem,)).fetchone()
        if old:
            if old['checksum'] != checksum: raise ValueError('Applied migration was modified: ' + path.name)
            continue
        connection.execute(path.read_text())
        connection.execute('INSERT INTO schema_migrations(version,checksum) VALUES(%s,%s)',(path.stem,checksum))
    connection.execute('REVOKE CREATE ON SCHEMA public FROM PUBLIC')
    connection.execute('GRANT USAGE ON SCHEMA public TO travel_app')
    connection.execute('GRANT SELECT ON ALL TABLES IN SCHEMA public TO travel_app')
    connection.execute('REVOKE ALL ON journey_enquiries,enquiry_status_events,enquiry_notifications FROM travel_app')
    connection.execute('ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO travel_app')


def import_data(connection, data):
    connection.execute('SELECT pg_advisory_xact_lock(83109001)')
    existing = connection.execute('SELECT id FROM import_batches WHERE fingerprint=%s',(data['fingerprint'],)).fetchone()
    if existing: return {'status': 'already_imported', 'batch': existing['id']}
    if connection.execute('SELECT count(*) AS n FROM products').fetchone()['n']:
        raise ValueError('Database already contains maintained data. Re-import cannot overwrite it; use maintenance commands.')
    batch = connection.execute('INSERT INTO import_batches(fingerprint,sources) VALUES(%s,%s) RETURNING id',(data['fingerprint'],Jsonb(data['sources']))).fetchone()['id']
    for service in data['services']:
        connection.execute('INSERT INTO service_items(code,city,name,category,unit,note,description,source_file,import_batch) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)', tuple(service[key] for key in ['code','city','name','category','unit','note','description','source_file'])+(batch,))
        connection.execute('INSERT INTO service_prices(service_code,price,price_peak,state,raw_price,raw_peak,actor) VALUES(%s,%s,%s,%s,%s,%s,%s)', tuple(service[key] for key in ['code','price','price_peak','state','raw_price','raw_peak'])+('initial-import',))
    for product in data['products']:
        id = product['product_id']
        connection.execute('INSERT INTO products(id,city,name,days,itinerary,metadata,import_batch) VALUES(%s,%s,%s,%s,%s,%s,%s)',(id,product['city'],product['product_name'],product['duration_days'],product['itinerary_text'],Jsonb(product['metadata']),batch))
        for day in product['day_plans']:
            connection.execute('INSERT INTO product_days VALUES(%s,%s,%s,%s)',(id,day['day_number'],day['raw_text'],Jsonb(day['activity_names'])))
        for kind in ('regular','optional'):
            for position,name in enumerate(product[kind+'_items']): connection.execute('INSERT INTO product_item_names VALUES(%s,%s,%s,%s)',(id,kind,position,name))
            for position,code in enumerate(product[kind+'_item_codes']): connection.execute('INSERT INTO product_code_refs VALUES(%s,%s,%s,%s)',(id,kind,position,code))
    for id, spec in data['configuration']['products'].items():
        rules = {key:value for key,value in spec.items() if key not in ['branches','common_codes','day']}
        connection.execute('INSERT INTO cost_scopes VALUES(%s,%s)',(id,Jsonb(rules)))
        for position,(choice,branch) in enumerate(spec.get('branches', {}).items()):
            connection.execute('INSERT INTO route_branches VALUES(%s,%s,%s,%s,%s,%s,%s)',(id,choice,spec['day'],position,branch['label'],branch.get('car_code'),Jsonb(branch.get('excluded_optional',[]))))
            for kind,codes in [('common',spec['common_codes']),('branch',branch['codes'])]:
                for index,code in enumerate(codes):connection.execute('INSERT INTO branch_items VALUES(%s,%s,%s,%s,%s)',(id,choice,kind,index,code))
    for key,document in data['documents'].items():connection.execute('INSERT INTO content_documents VALUES(%s,%s)',(key,Jsonb(document)))
    policy = data['configuration']['sales_policy']
    connection.execute('INSERT INTO pricing_policies(id,multiplier,currency,rounding,decimal_places,supplier_surcharge,actor) VALUES(%s,%s,%s,%s,%s,%s,%s)',tuple(policy[key] for key in ['id','multiplier','currency','rounding','decimal_places','supplier_surcharge'])+('initial-import',))
    connection.execute('INSERT INTO audit_events(actor,operation,object_key,after_data) VALUES(%s,%s,%s,%s)',('initial-import','import','catalogue',Jsonb(data['review'])))
    return {'status': 'imported', 'batch': batch}
