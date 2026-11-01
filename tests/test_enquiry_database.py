"""Real enquiry persistence checks; transaction writes roll back unless using a disposable database."""
import os
import uuid
import unittest
import psycopg
from fastapi import HTTPException
from backend.app.services import journey_enquiries, enquiry_tokens, travel_catalog, sales_pricing
from backend.app.storage.connection import connect, intake_connection
from backend.app.storage.repository import _snapshot, read_dataset
from backend.app.travel_schemas import JourneyEnquiryRequest, TripPreviewRequest, TripPreviewResponse, CostEstimateRequest, SalesQuoteResponse, RouteChoice, CustomEnquiryRequest


@unittest.skipUnless(os.environ.get('RUN_DATABASE_TESTS')=='1','Requires explicit PostgreSQL test opt-in')
class EnquiryDatabaseTests(unittest.TestCase):
    def payload(self, conn, branch=False):
        key='rollback-enquiry-key'
        data=read_dataset(conn);token=_snapshot.set(data)
        try:
            preview_request=TripPreviewRequest(city='重庆' if branch else '上海',days=2 if branch else 3,need_guide=True)
            preview=TripPreviewResponse.model_validate(travel_catalog.preview(preview_request)).model_dump(mode='json',exclude={'preview_token'})
            request=CostEstimateRequest(**{**preview_request.model_dump(),'product_id':preview['product']['product_id'],'is_peak':False,'guide_code':'CQ-GUIDE-01' if branch else 'SH-GUIDE-01'})
            quote=SalesQuoteResponse.model_validate(sales_pricing.quote(request)).model_dump(mode='json',exclude={'quote_token'})
            payload=JourneyEnquiryRequest(request_id=uuid.uuid4(),name='Rollback Enquiry Test',email='rollback-test@example.invalid',message='Test only',preview_token=enquiry_tokens.issue('preview',preview,key),quote_token=enquiry_tokens.issue('quote',{'request':request.model_dump(mode='json'),'quote':quote},key))
            return payload,key
        finally:_snapshot.reset(token)

    def test_atomic_save_idempotence_and_snapshot(self):
        with connect(admin=True) as conn,conn.transaction(force_rollback=True):
            payload,key=self.payload(conn)
            payload=payload.model_copy(update={'hotel_preference':'arrange'})
            response=journey_enquiries.save_in_connection(conn,payload,key)
            again=journey_enquiries.save_in_connection(conn,payload,key)
            self.assertEqual(response,again)
            row=conn.execute('SELECT * FROM journey_enquiries WHERE reference=%s',(response['reference'],)).fetchone()
            self.assertEqual(row['email'],payload.email)
            self.assertEqual(row['preferences']['hotel_preference'],'arrange')
            self.assertEqual(row['preferences']['hotel_quote_status'],'not_included')
            self.assertFalse(row['quote_changed'])
            self.assertIsNotNone(row['quote_snapshot_id'])
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM enquiry_notifications WHERE enquiry_id=%s',(row['id'],)).fetchone()['n'],1)
            self.assertEqual(row['preview_snapshot']['request']['guide_code'],'SH-GUIDE-01')
            self.assertEqual(row['verified_quote'],row['shown_quote'])
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM journey_enquiries WHERE idempotency_key=%s',(payload.request_id,)).fetchone()['n'],1)
            with self.assertRaises(HTTPException) as error:
                journey_enquiries.save_in_connection(conn,payload.model_copy(update={'message':'Different'}),key)
            self.assertEqual(error.exception.status_code,409)

    def test_pending_and_changed_prices(self):
        from backend.app.storage.maintenance import set_price
        with connect(admin=True) as conn,conn.transaction(force_rollback=True):
            pending,key=self.payload(conn,True)
            response=journey_enquiries.save_in_connection(conn,pending,key)
            row=conn.execute('SELECT * FROM journey_enquiries WHERE reference=%s',(response['reference'],)).fetchone()
            self.assertIsNone(row['quote_snapshot_id'])
            self.assertEqual(row['verified_quote']['sales_quote']['status'],'pending_confirmation')
            payload,key=self.payload(conn)
            version=conn.execute("SELECT id FROM service_prices WHERE service_code='SH-TICKET-06' AND active").fetchone()['id']
            set_price(conn,'SH-TICKET-06','50','70',version,'rollback-test')
            response=journey_enquiries.save_in_connection(conn,payload,key)
            row=conn.execute('SELECT * FROM journey_enquiries WHERE reference=%s',(response['reference'],)).fetchone()
            self.assertTrue(row['quote_changed'])
            self.assertGreater(row['verified_quote']['sales_quote']['amount'],row['shown_quote']['sales_quote']['amount'])

    def test_invalid_snapshot_and_route(self):
        with connect(admin=True) as conn,conn.transaction(force_rollback=True):
            payload,key=self.payload(conn)
            for invalid in [payload.model_copy(update={'preview_token':payload.preview_token+'x'}), payload.model_copy(update={'quote_token':enquiry_tokens.issue('quote',{'request':{},'quote':{}},key)}),payload.model_copy(update={'route_choices':[RouteChoice(day=1,choice='made-up')]})]:
                with self.assertRaises(HTTPException) as error:journey_enquiries.save_in_connection(conn,invalid,key)
                self.assertEqual(error.exception.status_code,422)
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM journey_enquiries WHERE idempotency_key=%s',(payload.request_id,)).fetchone()['n'],0)

    def test_intake_and_reader_privileges(self):
        with intake_connection() as conn:
            try:conn.execute("UPDATE service_prices SET price=price WHERE service_code='SH-TICKET-06'")
            except psycopg.errors.InsufficientPrivilege:conn.rollback()
            else:self.fail('Intake may not update prices')
        with connect() as conn:
            try:conn.execute('SELECT * FROM journey_enquiries LIMIT 1')
            except psycopg.errors.InsufficientPrivilege:conn.rollback()
            else:self.fail('Catalogue reader may not read customer enquiries')
        with intake_connection() as conn,conn.transaction(force_rollback=True):
            payload,key=self.payload(conn)
            response=journey_enquiries.save_in_connection(conn,payload,key)
            self.assertEqual(response['status'],'received')

    def test_custom_enquiry_without_product_or_quote(self):
        with intake_connection() as conn, conn.transaction(force_rollback=True):
            payload = CustomEnquiryRequest(request_id=uuid.uuid4(), name='Rollback Custom Test', email='custom-rollback@example.invalid', destinations='Shanghai and Yunnan', interests='Tea and crafts', hotel_preference='arrange')
            response = journey_enquiries.save_custom_in_connection(conn, payload)
            self.assertEqual(journey_enquiries.save_custom_in_connection(conn, payload), response)
            row = conn.execute('SELECT * FROM journey_enquiries WHERE reference=%s', (response['reference'],)).fetchone()
            self.assertEqual(row['enquiry_kind'], 'custom')
            self.assertIsNone(row['product_id'])
            self.assertIsNone(row['quote_snapshot_id'])
            self.assertIsNone(row['shown_quote'])
            self.assertIsNone(row['verified_quote']['amount'])
            self.assertEqual(row['preferences']['hotel_preference'], 'arrange')
            self.assertEqual(row['preferences']['interests'], 'Tea and crafts')
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM journey_enquiries WHERE idempotency_key=%s', (payload.request_id,)).fetchone()['n'], 1)
            with self.assertRaises(HTTPException) as error:
                journey_enquiries.save_custom_in_connection(conn, payload.model_copy(update={'interests': 'Different'}))
            self.assertEqual(error.exception.status_code, 409)


if __name__=='__main__':unittest.main()
