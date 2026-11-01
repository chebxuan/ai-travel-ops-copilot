"""Real PostgreSQL tests. Every mutation rolls back; opt in explicitly."""
import os
import unittest
from unittest.mock import patch
from backend.app.storage.connection import connect
from backend.app.storage import maintenance
from backend.app.storage.repository import read_dataset, _snapshot
from backend.app.services.sales_pricing import quote
from backend.app.travel_schemas import CostEstimateRequest


@unittest.skipUnless(os.environ.get('RUN_DATABASE_TESTS')=='1','Requires explicit PostgreSQL test opt-in')
class DatabaseTests(unittest.TestCase):
    def test_price_history_quote_snapshot_and_concurrency(self):
        # Explicit database snapshot saving must work before runtime activation too.
        with patch.dict(os.environ,{'TRAVEL_DATA_SOURCE':'files'}),connect(admin=True) as conn,conn.transaction(force_rollback=True):
            request=CostEstimateRequest(city='上海',days=3,is_peak=False)
            id=maintenance.save_quote(conn,request,'rollback-test')
            before=conn.execute('SELECT * FROM quote_snapshots WHERE id=%s',(id,)).fetchone()
            initial_amount = before['public_quote']['sales_quote']['amount']
            self.assertGreater(initial_amount, 0)
            current=conn.execute("SELECT * FROM service_prices WHERE service_code='SH-TICKET-06' AND active").fetchone()
            new=maintenance.set_price(conn,'SH-TICKET-06','900','950',current['id'],'rollback-test')
            self.assertNotEqual(new,current['id'])
            self.assertFalse(conn.execute('SELECT active FROM service_prices WHERE id=%s',(current['id'],)).fetchone()['active'])
            with self.assertRaises(ValueError):maintenance.set_price(conn,'SH-TICKET-06','60','80',current['id'],'rollback-test')
            data=read_dataset(conn);token=_snapshot.set(data)
            try:self.assertGreater(quote(request)['sales_quote']['amount'],initial_amount)
            finally:_snapshot.reset(token)
            preserved=conn.execute('SELECT public_quote FROM quote_snapshots WHERE id=%s',(id,)).fetchone()
            self.assertEqual(preserved['public_quote'],before['public_quote'])
            self.assertGreater(conn.execute("SELECT count(*) AS n FROM audit_events WHERE actor='rollback-test'").fetchone()['n'],0)

    def test_supplier_and_copy_maintenance(self):
        with connect(admin=True) as conn,conn.transaction(force_rollback=True):
            supplier=maintenance.add_supplier(conn,'Rollback Test Supplier','','Not a real supplier','rollback-test')
            maintenance.link_supplier(conn,supplier,'SH-TICKET-06','rollback-test')
            self.assertEqual(conn.execute('SELECT service_code FROM supplier_services WHERE supplier_id=%s',(supplier,)).fetchone()['service_code'],'SH-TICKET-06')
            maintenance.set_product_copy(conn,'SH-P-02','Test Title','Test introduction','rollback-test')
            document=conn.execute("SELECT document FROM content_documents WHERE key='presentation'").fetchone()['document']
            self.assertEqual(document['product_titles']['SH-P-02'],'Test Title')
            maintenance.set_product_copy(conn,'YN-P-01',None,'Test Yunnan intro','rollback-test')
            highlights=conn.execute("SELECT document FROM content_documents WHERE key='highlights'").fetchone()['document']
            self.assertEqual(highlights['云南']['routes']['Route 1']['description'],'Test Yunnan intro')
            for standard,peak in [('-1','5'),('NaN','5'),('5.123','5')]:
                with self.assertRaises(ValueError):maintenance.set_price(conn,'SH-TICKET-06',standard,peak,1,'rollback-test')

    def test_database_unavailable_never_falls_back(self):
        from fastapi import HTTPException
        from backend.app.storage.repository import runtime_snapshot
        with patch.dict(os.environ,{'TRAVEL_DATA_SOURCE':'postgres','TRAVEL_DATABASE_URL':'postgresql://invalid@127.0.0.1:1/missing'}):
            with self.assertRaises(HTTPException) as error:
                with runtime_snapshot():pass
            self.assertEqual(error.exception.status_code,503)
            self.assertEqual(error.exception.detail,{'code':'DATABASE_UNAVAILABLE'})


if __name__=='__main__':unittest.main()
