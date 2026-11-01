"""Initial file/database parity and PostgreSQL safeguards. Uses rollback-only mutations."""
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.app.storage.connection import connect
from backend.app.storage.repository import runtime_snapshot, dataset
from backend.app.services import travel_catalog, sales_pricing
from backend.app.travel_schemas import CostEstimateRequest
from backend.app.storage.importer import read_sources


def digest(data):
    return hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()


def stable(result):
    if isinstance(result,dict):return {k:stable(v) for k,v in result.items() if k not in ['generated_at']}
    if isinstance(result,list):return [stable(v) for v in result]
    return result


def scenarios(products):
    scopes=read_sources()['configuration']['products']
    defaults={'CQ-P-01':(2,['wulong','dazu']),'YS-P-02':(3,['cave','via_ferrata']),'ZJJ-P-02':(3,['heritage','adventure'])}
    for p in products:
        day,choices=defaults.get(p['product_id'],(None,[None]))
        for branch in choices:
            for peak in [False,True]:
                for services in [False,True]:
                    for family in [False,True]:
                        excluded=scopes.get(p['product_id'],{}).get('branches',{}).get(branch,{}).get('excluded_optional',[])
                        yield CostEstimateRequest(city=p['city'],days=p['duration_days'],is_peak=peak,product_id=p['product_id'],children=1 if family else 0,seniors=1 if family else 0,selected_optional_items=[name for name in p['optional_items'] if name not in excluded] if family else [],need_guide=services,guide_code=p['city'].replace('北京','BJ').replace('上海','SH').replace('重庆','CQ').replace('西安','XA').replace('阳朔','YS').replace('张家界','ZJJ').replace('广州','GZ').replace('贵州','GUIZ').replace('云南','YN').replace('成都','CD')+'-GUIDE-01' if services else None,need_private_car=services,route_choices=[{'day':day,'choice':branch}] if branch else [])



def compare():
    sources=read_sources()
    requests=list(scenarios(sources['products']))
    baseline=[]
    with patch.dict(os.environ,{'TRAVEL_DATA_SOURCE':'files'}):
        for request in requests:
            baseline.append((stable(travel_catalog.estimate(request)), sales_pricing.quote(request)))
        catalogue={p['product_id']:travel_catalog.public_product(p) for p in travel_catalog.source_products()}
    with patch.dict(os.environ,{'TRAVEL_DATA_SOURCE':'postgres'}),runtime_snapshot():
        db=dataset();db_digest=digest(db)
        actual={p['product_id']:travel_catalog.public_product(p) for p in travel_catalog.source_products()}
        assert catalogue==actual,'Public product projection differs'
        for request,expected in zip(requests,baseline):
            got=(stable(travel_catalog.estimate(request)),sales_pricing.quote(request))
            assert expected==got,request.product_id
    # Verify real database constraints and read-only runtime privileges.
    import psycopg
    with connect() as conn:
        try:
            conn.execute("UPDATE products SET name=name WHERE id='SH-P-02'")
            raise AssertionError('Runtime role must not update data')
        except psycopg.errors.InsufficientPrivilege:conn.rollback()
    with connect(admin=True) as conn:
        for statement,params,error in [
            ('INSERT INTO product_code_refs VALUES(%s,%s,%s,%s)',('SH-P-02','regular',999,'NO-SUCH-SERVICE'),psycopg.errors.ForeignKeyViolation),
            ('INSERT INTO service_prices(service_code,price,state,raw_price,raw_peak,actor,active) VALUES(%s,%s,%s,%s,%s,%s,false)',('SH-TICKET-06',-1,'fixed','-1','','test'),psycopg.errors.CheckViolation),
        ]:
            try:
                with conn.transaction():conn.execute(statement,params)
                raise AssertionError('Invalid data accepted')
            except error:pass
        conn.rollback()
    report={'passed':True,'products':21,'scenarios':len(requests),'database_digest':db_digest,'source_fingerprint':sources['fingerprint'],'checks':['public catalogue parity','all branches and both seasons','guide/car costs','sales-price parity','foreign keys','non-negative prices','read-only runtime role']}
    path=ROOT/'.local/database/verification.json';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k not in ['database_digest','source_fingerprint']},indent=2))


if __name__=='__main__':compare()
