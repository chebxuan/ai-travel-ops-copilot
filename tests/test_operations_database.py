"""User-run on an isolated migrated test database; all writes explicitly roll back."""
import os
import unittest
import uuid
from unittest.mock import patch
from fastapi import HTTPException
from backend.app.routers.operations import change_status, StatusChange
from backend.app.services import journey_enquiries, enquiry_notifications
from backend.app.storage.connection import connect
from backend.app.travel_schemas import CustomEnquiryRequest


@unittest.skipUnless(os.environ.get('RUN_DATABASE_TESTS')=='1','Requires an isolated PostgreSQL test database')
class OperationsDatabaseTests(unittest.TestCase):
    def save(self,conn):
        payload=CustomEnquiryRequest(request_id=uuid.uuid4(),name='Rollback operations test',email='ops-test@example.invalid')
        reference=journey_enquiries.save_custom_in_connection(conn,payload)['reference']
        row=conn.execute('SELECT * FROM journey_enquiries WHERE reference=%s',(reference,)).fetchone()
        return row

    def test_atomic_outbox_rollback(self):
        with connect(admin=True) as conn,conn.transaction(force_rollback=True):
            payload=CustomEnquiryRequest(request_id=uuid.uuid4(),name='Rollback',email='rollback@example.invalid')
            with self.assertRaises(RuntimeError):
                with conn.transaction():
                    with patch('backend.app.services.journey_enquiries.enqueue',side_effect=RuntimeError('Simulated outbox failure')):
                        journey_enquiries.save_custom_in_connection(conn,payload)
            self.assertEqual(conn.execute('SELECT count(*) AS n FROM journey_enquiries WHERE idempotency_key=%s',(payload.request_id,)).fetchone()['n'],0)

    def test_status_version_audit_and_original_data(self):
        with connect(admin=True) as conn,conn.transaction(force_rollback=True):
            row=self.save(conn)
            conn.execute('SET LOCAL ROLE travel_ops')
            result=change_status(conn,row['reference'],StatusChange(status='following_up',expected_version=1),'test-operator')
            self.assertEqual(result['status_version'],2)
            with self.assertRaises(HTTPException) as caught:
                change_status(conn,row['reference'],StatusChange(status='closed',expected_version=1),'test-operator')
            self.assertEqual(caught.exception.status_code,409)
            current=conn.execute('SELECT * FROM journey_enquiries WHERE id=%s',(row['id'],)).fetchone()
            for field in ('name','email','message','preferences','shown_quote','verified_quote','preview_snapshot'):
                self.assertEqual(current[field],row[field])
            events=conn.execute('SELECT * FROM enquiry_status_events WHERE enquiry_id=%s',(row['id'],)).fetchall()
            self.assertEqual(len(events),1);self.assertEqual(events[0]['actor'],'test-operator')

    def test_notification_lease_recovery_and_stale_ack(self):
        with connect(admin=True) as conn,conn.transaction(force_rollback=True):
            row=self.save(conn)
            conn.execute("UPDATE enquiry_notifications SET available_at='-infinity' WHERE enquiry_id=%s",(row['id'],))
            conn.execute('SET LOCAL ROLE travel_notifier')
            first=enquiry_notifications.claim(conn)
            conn.execute("UPDATE enquiry_notifications SET lease_until=now()-interval '6 minutes' WHERE id=%s",(first['id'],))
            second=enquiry_notifications.claim(conn)
            self.assertEqual(first['id'],second['id']);self.assertNotEqual(first['lease_id'],second['lease_id'])
            enquiry_notifications.finish(conn,first,True)
            state=conn.execute('SELECT state FROM enquiry_notifications WHERE id=%s',(first['id'],)).fetchone()['state']
            self.assertEqual(state,'sending')
            enquiry_notifications.finish(conn,second,True)
            state=conn.execute('SELECT state FROM enquiry_notifications WHERE id=%s',(first['id'],)).fetchone()['state']
            self.assertEqual(state,'sent')

    def test_least_privilege_roles(self):
        with connect(admin=True) as conn,conn.transaction(force_rollback=True):
            for role,table,privilege in [('travel_app','journey_enquiries','SELECT'),('travel_app','enquiry_notifications','SELECT'),('travel_intake','enquiry_notifications','SELECT'),('travel_ops','service_prices','UPDATE'),('travel_ops','quote_snapshots','SELECT'),('travel_notifier','journey_enquiries','SELECT'),('travel_notifier','enquiry_notifications','INSERT')]:
                self.assertFalse(conn.execute('SELECT has_table_privilege(%s,%s,%s) AS allowed',(role,table,privilege)).fetchone()['allowed'],(role,table,privilege))
            self.assertTrue(conn.execute("SELECT has_column_privilege('travel_ops','journey_enquiries','status','UPDATE') AS allowed").fetchone()['allowed'])
            self.assertFalse(conn.execute("SELECT has_column_privilege('travel_ops','journey_enquiries','email','UPDATE') AS allowed").fetchone()['allowed'])
            self.assertFalse(conn.execute("SELECT has_column_privilege('travel_notifier','enquiry_notifications','payload','UPDATE') AS allowed").fetchone()['allowed'])
