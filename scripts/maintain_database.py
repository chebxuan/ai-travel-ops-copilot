"""Inspect and maintain local master data with history; owner credentials stay server-side."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.storage.connection import connect
from backend.app.storage import maintenance


def main():
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='action',required=True)
    for action in ['services','history']:
        command=sub.add_parser(action);command.add_argument('--city');command.add_argument('--code')
    sub.add_parser('products');sub.add_parser('suppliers')
    sub.add_parser('quotes')
    sub.add_parser('enquiries')
    command=sub.add_parser('notifications');command.add_argument('--state',choices=['pending','sending','sent','failed'])
    command=sub.add_parser('notification-retry');command.add_argument('--reference',required=True);command.add_argument('--actor',required=True)
    command=sub.add_parser('enquiry');command.add_argument('--reference',required=True)
    command=sub.add_parser('quote');command.add_argument('--id',required=True)
    command=sub.add_parser('audit');command.add_argument('--limit',type=int,default=20)
    command=sub.add_parser('set-price');command.add_argument('--code',required=True);command.add_argument('--standard',required=True);command.add_argument('--peak',required=True);command.add_argument('--expected-version',required=True,type=int);command.add_argument('--actor',required=True)
    command=sub.add_parser('product-copy');command.add_argument('--id',required=True);command.add_argument('--title');command.add_argument('--intro');command.add_argument('--actor',required=True)
    command=sub.add_parser('supplier-add');command.add_argument('--name',required=True);command.add_argument('--email',default='');command.add_argument('--notes',default='');command.add_argument('--actor',required=True)
    command=sub.add_parser('supplier-link');command.add_argument('--supplier',type=int,required=True);command.add_argument('--code',required=True);command.add_argument('--actor',required=True)
    command=sub.add_parser('save-quote');command.add_argument('--request',type=Path,required=True);command.add_argument('--actor',required=True)
    args=parser.parse_args()
    if hasattr(args,'actor') and not args.actor.strip():raise ValueError('Actor cannot be empty')
    with connect(admin=True) as conn:
        if args.action=='services':
            rows=conn.execute('SELECT * FROM current_service_costs WHERE (%s::text IS NULL OR city=%s) AND (%s::text IS NULL OR code=%s) ORDER BY code',(args.city,args.city,args.code,args.code)).fetchall()
            for row in rows:print(json.dumps(row,ensure_ascii=False,default=str))
        elif args.action=='history':
            if not args.code:raise ValueError('history requires --code')
            for row in conn.execute('SELECT id,price,price_peak,state,active,valid_from,valid_to,actor FROM service_prices WHERE service_code=%s ORDER BY id',(args.code,)):print(json.dumps(row,ensure_ascii=False,default=str))
        elif args.action=='products':
            for row in conn.execute('SELECT id,city,name,days FROM products ORDER BY id'):print(json.dumps(row,ensure_ascii=False))
        elif args.action=='suppliers':
            for row in conn.execute('SELECT id,name,notes FROM suppliers ORDER BY id'):print(json.dumps(row,ensure_ascii=False))
        elif args.action=='quotes':
            for row in conn.execute('SELECT id,product_id,policy_id,actor,created_at FROM quote_snapshots ORDER BY created_at DESC LIMIT 50'):print(json.dumps(row,ensure_ascii=False,default=str))
        elif args.action=='enquiries':
            for row in conn.execute('SELECT reference,created_at,name,email,enquiry_kind,product_id,preferences,status,quote_changed,review_reason FROM journey_enquiries ORDER BY created_at DESC LIMIT 50'):print(json.dumps(row,ensure_ascii=False,default=str))
        elif args.action=='notifications':
            for row in conn.execute("SELECT n.id,e.reference,n.state,n.attempts,n.available_at,n.sent_at,n.last_error FROM enquiry_notifications n JOIN journey_enquiries e ON e.id=n.enquiry_id WHERE (%s::text IS NULL OR n.state=%s) ORDER BY n.created_at DESC LIMIT 50",(args.state,args.state)):
                print(json.dumps(row,ensure_ascii=False,default=str))
        elif args.action=='notification-retry':
            row=conn.execute("SELECT n.id,n.state,n.attempts FROM enquiry_notifications n JOIN journey_enquiries e ON e.id=n.enquiry_id WHERE e.reference=%s FOR UPDATE OF n",(args.reference,)).fetchone()
            if not row or row['state']!='failed':raise ValueError('Only failed notification jobs can be retried')
            conn.execute("UPDATE enquiry_notifications SET state='pending',attempts=0,available_at=now(),lease_id=NULL,lease_until=NULL,last_error=NULL WHERE id=%s",(row['id'],))
            from psycopg.types.json import Jsonb
            conn.execute('INSERT INTO audit_events(actor,operation,object_key,before_data,after_data) VALUES(%s,%s,%s,%s,%s)',(args.actor,'notification-retry',str(row['id']),Jsonb({'state':row['state'],'attempts':row['attempts']}),Jsonb({'state':'pending','attempts':0})))
            print('Failed notification scheduled for another delivery cycle; audit saved.')
        elif args.action=='enquiry':
            row=conn.execute('SELECT * FROM journey_enquiries WHERE reference=%s',(args.reference,)).fetchone()
            if not row:raise ValueError('Enquiry not found')
            print(json.dumps(row,ensure_ascii=False,default=str,indent=2))
        elif args.action=='quote':
            row=conn.execute('SELECT * FROM quote_snapshots WHERE id=%s',(args.id,)).fetchone()
            if not row:raise ValueError('Quote not found')
            print(json.dumps(row,ensure_ascii=False,default=str,indent=2))
        elif args.action=='audit':
            if not 1<=args.limit<=100:raise ValueError('Limit must be between 1 and 100')
            for row in conn.execute('SELECT * FROM audit_events ORDER BY id DESC LIMIT %s',(args.limit,)):print(json.dumps(row,ensure_ascii=False,default=str))
        elif args.action=='set-price':print('New price version:',maintenance.set_price(conn,args.code,args.standard,args.peak,args.expected_version,args.actor))
        elif args.action=='product-copy':
            if args.title is None and args.intro is None:raise ValueError('Provide --title or --intro')
            maintenance.set_product_copy(conn,args.id,args.title,args.intro,args.actor);print('Product copy updated with audit record.')
        elif args.action=='supplier-add':print('Supplier ID:',maintenance.add_supplier(conn,args.name,args.email,args.notes,args.actor))
        elif args.action=='supplier-link':maintenance.link_supplier(conn,args.supplier,args.code,args.actor);print('Supplier linked.')
        elif args.action=='save-quote':
            from backend.app.travel_schemas import CostEstimateRequest
            request=CostEstimateRequest.model_validate(json.loads(args.request.read_text()))
            print('Saved quote ID:',maintenance.save_quote(conn,request,args.actor))


if __name__=='__main__':
    try:main()
    except Exception as error:
        if isinstance(error,ValueError):raise SystemExit(str(error))
        raise SystemExit('Maintenance failed ('+type(error).__name__+'). Check server, IDs and configuration.') from None
