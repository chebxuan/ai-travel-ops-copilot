"""Local owner operations; append history and record actors in one transaction."""
from decimal import Decimal
import uuid
from psycopg.types.json import Jsonb
from backend.app.storage.repository import read_dataset, _snapshot


def jsonable(value):
    import json
    return json.loads(json.dumps(value,default=str))


def audit(connection,actor,operation,key,before,after):
    if not actor.strip(): raise ValueError('An actor is required')
    connection.execute('INSERT INTO audit_events(actor,operation,object_key,before_data,after_data) VALUES(%s,%s,%s,%s,%s)',(actor,operation,key,Jsonb(jsonable(before)) if before is not None else None,Jsonb(jsonable(after))))


def set_price(connection,code,standard,peak,expected_version,actor):
    standard,peak=Decimal(standard),Decimal(peak)
    if not standard.is_finite() or not peak.is_finite() or standard < 0 or peak < 0 or standard.as_tuple().exponent < -2 or peak.as_tuple().exponent < -2:raise ValueError('Prices must be non-negative, finite and have at most two decimal places')
    connection.execute('SELECT code FROM service_items WHERE code=%s FOR UPDATE',(code,))
    old=connection.execute('SELECT * FROM service_prices WHERE service_code=%s AND active FOR UPDATE',(code,)).fetchone()
    if not old:raise ValueError('Service not found')
    if old['id']!=expected_version:raise ValueError('Price was changed by another operation. Read the current version again.')
    if old['state']=='confirmed_free' and (standard!=0 or peak!=0):raise ValueError('Confirmed-free items require business scope review before charging')
    if old['price']==standard and old['price_peak']==peak:return old['id']
    connection.execute('UPDATE service_prices SET active=false,valid_to=now() WHERE id=%s',(old['id'],))
    state='confirmed_free' if standard==peak==0 else 'fixed'
    new=connection.execute('INSERT INTO service_prices(service_code,supplier_id,price,price_peak,state,raw_price,raw_peak,actor) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *',(code,old['supplier_id'],standard,peak,state,str(standard),str(peak),actor)).fetchone()
    audit(connection,actor,'price-update',code,old,new)
    return new['id']


def set_product_copy(connection,id,title,intro,actor):
    row=connection.execute('SELECT id FROM products WHERE id=%s FOR UPDATE',(id,)).fetchone()
    if not row:raise ValueError('Product not found')
    row=connection.execute("SELECT document FROM content_documents WHERE key='presentation' FOR UPDATE").fetchone()
    document=row['document'];before={'title':document['product_titles'][id],'intro':document.get('introductions',{}).get(id)}
    if title is not None:
        if not title.strip():raise ValueError('Title cannot be empty')
        document['product_titles'][id]=title.strip()
    if intro is not None:
        if not intro.strip():raise ValueError('Introduction cannot be empty')
        if id in ('GZH-P-01','YN-P-01'):
            # These long-route introductions use the source highlights document.
            row=connection.execute("SELECT document FROM content_documents WHERE key='highlights' FOR UPDATE").fetchone()
            highlights=row['document'];city='贵州' if id=='GZH-P-01' else '云南'
            before['intro']=highlights[city]['routes']['Route 1']['description']
            highlights[city]['routes']['Route 1']['description']=intro.strip()
            connection.execute("UPDATE content_documents SET document=%s WHERE key='highlights'",(Jsonb(highlights),))
        else:document.setdefault('introductions',{})[id]=intro.strip()
    connection.execute("UPDATE content_documents SET document=%s WHERE key='presentation'",(Jsonb(document),))
    audit(connection,actor,'product-copy-update',id,before,{'title':document['product_titles'][id],'intro':intro if intro is not None else before['intro']})


def add_supplier(connection,name,email,notes,actor):
    if not name.strip():raise ValueError('Supplier name is required')
    row=connection.execute('INSERT INTO suppliers(name,contact,notes) VALUES(%s,%s,%s) RETURNING id,name',(name.strip(),Jsonb({'email':email} if email else {}),notes)).fetchone()
    audit(connection,actor,'supplier-add',str(row['id']),None,{'name':row['name']})
    return row['id']


def link_supplier(connection,supplier,code,actor):
    connection.execute('INSERT INTO supplier_services VALUES(%s,%s) ON CONFLICT DO NOTHING',(supplier,code))
    audit(connection,actor,'supplier-link',code,None,{'supplier_id':supplier})


def save_quote(connection,request,actor):
    from backend.app.services.travel_catalog import estimate
    from backend.app.services.sales_pricing import quote
    connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ')
    data=read_dataset(connection);token=_snapshot.set(data)
    try:
        internal=estimate(request);public=quote(request)
        if public['sales_quote']['status']!='estimated':raise ValueError('Only successfully estimated quotes can be saved')
        id=uuid.uuid4()
        codes={line['code'] for line in internal['cost']['line_items']}
        versions={code:version for code,version in data['price_versions'].items() if code in codes}
        connection.execute('INSERT INTO quote_snapshots(id,product_id,policy_id,request_data,internal_cost,public_quote,service_price_versions,actor) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)',(id,internal['product_id'],data['configuration']['sales_policy']['id'],Jsonb(request.model_dump(mode='json')),Jsonb(internal),Jsonb(public),Jsonb(versions),actor))
        audit(connection,actor,'quote-saved',str(id),None,{'product_id':internal['product_id']})
        return str(id)
    finally:_snapshot.reset(token)
