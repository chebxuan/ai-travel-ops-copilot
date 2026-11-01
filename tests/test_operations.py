"""No services or database: auth boundary, status conflict, commit and delivery failure tests."""
import base64
from contextlib import contextmanager
import hashlib
import hmac
import json
import os
import time
import unittest
import uuid
from unittest.mock import Mock, patch
import psycopg
from fastapi import HTTPException
from fastapi.testclient import TestClient
from backend.app.routers import operations
from backend.app.services import enquiry_notifications as notifications, journey_enquiries
from backend.app.travel_schemas import CustomEnquiryRequest

KEY='separate-operations-key-for-tests-32-characters'


def assertion(method='GET',path='/api/ops/enquiries',body=b'',query='',actor='operator',exp=None):
    encoded=base64.urlsafe_b64encode(json.dumps({'method':method,'path':path,'query':query,'body':hashlib.sha256(body).hexdigest(),'actor':actor,'exp':exp if exp is not None else int(time.time())+60}).encode()).decode().rstrip('=')
    return encoded+'.'+hmac.new(KEY.encode(),encoded.encode(),hashlib.sha256).hexdigest()


class OperationsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from backend.app.main import app
        cls.client=TestClient(app)

    def test_public_key_cannot_read_customer_data(self):
        with patch.dict(os.environ,{'OPS_BACKEND_KEY':KEY}),patch('backend.app.routers.operations.storage_call') as storage:
            for headers in [{},{'X-API-Key':os.environ.get('API_KEY','')},{'X-Ops-Assertion':'invalid'}, {'X-Ops-Assertion':assertion(exp=1)},{'X-Ops-Assertion':assertion(path='/api/ops/other')}]:
                self.assertEqual(self.client.get('/api/ops/enquiries',headers=headers).status_code,401)
            storage.assert_not_called()

    def test_signature_binds_actor_body_query_and_method(self):
        body=b'{"status":"closed","expected_version":1}'
        path='/api/ops/enquiries/TC-0123456789ABCDEF/status'
        with patch.dict(os.environ,{'OPS_BACKEND_KEY':KEY}),patch('backend.app.routers.operations.storage_call',return_value={'status':'closed','status_version':2}) as storage:
            signed=assertion('POST',path,body)
            response=self.client.post(path,headers={'X-Ops-Assertion':signed,'Content-Type':'application/json'},content=body)
            self.assertEqual(response.status_code,200)
            for bad in [assertion('GET',path,body),assertion('POST',path,b'changed'),assertion('POST',path,body,actor='invalid actor')]:
                self.assertEqual(self.client.post(path,headers={'X-Ops-Assertion':bad,'Content-Type':'application/json'},content=body).status_code,401)
            self.assertEqual(self.client.get('/api/ops/enquiries?page=2',headers={'X-Ops-Assertion':assertion()}).status_code,401)
            self.assertEqual(storage.call_count,1)

    def test_disabled_operations_fail_closed(self):
        with patch.dict(os.environ,{'OPS_BACKEND_KEY':''}):
            self.assertEqual(self.client.get('/api/ops/enquiries').status_code,503)

    def test_status_conflict_and_noop_do_not_append_history(self):
        conn=Mock();conn.execute.return_value.fetchone.return_value={'id':uuid.uuid4(),'status':'new','status_version':2}
        with self.assertRaises(HTTPException) as caught:
            operations.change_status(conn,'TC-0123456789ABCDEF',operations.StatusChange(status='closed',expected_version=1),'operator')
        self.assertEqual(caught.exception.status_code,409)
        self.assertEqual(conn.execute.call_count,1)
        conn.reset_mock()
        result=operations.change_status(conn,'TC-0123456789ABCDEF',operations.StatusChange(status='new',expected_version=2),'operator')
        self.assertEqual(result['status_version'],2)
        self.assertEqual(conn.execute.call_count,1)

    def test_status_change_records_authenticated_actor(self):
        conn=Mock();id=uuid.uuid4();conn.execute.return_value.fetchone.return_value={'id':id,'status':'new','status_version':2}
        result=operations.change_status(conn,'TC-0123456789ABCDEF',operations.StatusChange(status='following_up',expected_version=2),'operator')
        self.assertEqual(result,{'status':'following_up','status_version':3})
        parameters=conn.execute.call_args_list[-1].args[1]
        self.assertEqual(parameters[1:],(id,'operator','new','following_up',3))

    def test_commit_failure_cannot_return_success(self):
        @contextmanager
        def failure():
            yield Mock()
            raise psycopg.OperationalError('simulated commit failure')
        payload=CustomEnquiryRequest(request_id=uuid.uuid4(),name='Example',email='example@example.invalid')
        with patch('backend.app.services.journey_enquiries.settings',return_value={'source':'postgres'}),patch('backend.app.services.journey_enquiries.intake_connection',failure),patch('backend.app.services.journey_enquiries.save_custom_in_connection',return_value={'reference':'TC-TEST','status':'received'}):
            with self.assertRaises(HTTPException) as caught:journey_enquiries.submit(payload,custom=True)
        self.assertEqual(caught.exception.status_code,503)

    def test_custom_retry_does_not_create_another_notification(self):
        payload=CustomEnquiryRequest(request_id=uuid.uuid4(),name='Example',email='example@example.invalid')
        conn=Mock();conn.execute.return_value.fetchone.return_value=None
        with patch('backend.app.services.journey_enquiries.enqueue') as enqueue:
            result=journey_enquiries.save_custom_in_connection(conn,payload)
            enqueue.assert_called_once()
        fingerprint=conn.execute.call_args_list[1].args[1][3]
        conn.execute.return_value.fetchone.return_value={'reference':result['reference'],'request_hash':fingerprint}
        with patch('backend.app.services.journey_enquiries.enqueue') as enqueue:
            self.assertEqual(journey_enquiries.save_custom_in_connection(conn,payload),result)
            enqueue.assert_not_called()


class NotificationTests(unittest.TestCase):
    def test_minimal_payload_and_signature(self):
        payload={'reference':'TC-0123456789ABCDEF','kind':'custom','product_id':None,'received_at':'2026-10-13T00:00:00Z','review':True}
        value=notifications.message(payload,'demo','https://example.invalid',1599360473)
        expected=base64.b64encode(hmac.new(b'1599360473\ndemo',b'',hashlib.sha256).digest()).decode()
        self.assertEqual(value['sign'],expected)
        self.assertIn('/ops?reference=TC-',value['content']['text'])
        self.assertNotIn('email',value['content']['text'])
        conn=Mock();notifications.enqueue(conn,uuid.uuid4(),payload['reference'],'custom',review=True)
        saved=conn.execute.call_args.args[1][2].obj
        self.assertEqual(set(saved),{'reference','kind','product_id','received_at','review'})

    def test_disabled_and_invalid_destination_claim_nothing(self):
        cases=[{'FEISHU_NOTIFICATIONS_ENABLED':'0'}, {'FEISHU_NOTIFICATIONS_ENABLED':'1','FEISHU_WEBHOOK_URL':'http://open.feishu.cn/open-apis/bot/v2/hook/test'}, {'FEISHU_NOTIFICATIONS_ENABLED':'1','FEISHU_WEBHOOK_URL':'https://example.invalid/open-apis/bot/v2/hook/test'}]
        for env in cases:
            with patch.dict(os.environ,env,clear=True),self.assertRaises(ValueError):notifications.configuration()

    def test_failed_delivery_schedules_retry_and_never_calls_intake(self):
        job={'id':uuid.uuid4(),'lease_id':uuid.uuid4(),'attempts':1,'payload':{}}
        @contextmanager
        def connection(kind):
            self.assertEqual(kind,'notification');yield Mock()
        with patch('backend.app.services.enquiry_notifications.restricted_connection',connection),patch('backend.app.services.enquiry_notifications.claim',return_value=job),patch('backend.app.services.enquiry_notifications.deliver',side_effect=TimeoutError()),patch('backend.app.services.enquiry_notifications.finish') as finish,patch('backend.app.services.journey_enquiries.intake_connection') as intake:
            self.assertTrue(notifications.process_one(('url','secret','origin')))
            self.assertFalse(finish.call_args.args[-1]);intake.assert_not_called()
        conn=Mock();notifications.finish(conn,job,False)
        self.assertEqual(conn.execute.call_args.args[1][0:2],('pending',60))
        notifications.finish(conn,{**job,'attempts':8},False)
        self.assertEqual(conn.execute.call_args.args[1][0],'failed')

    def test_lease_acknowledgement_and_bot_application_error(self):
        conn=Mock();job={'id':uuid.uuid4(),'lease_id':uuid.uuid4(),'attempts':1}
        notifications.finish(conn,job,True)
        self.assertEqual(conn.execute.call_args.args[1],(job['id'],job['lease_id']))
        response=Mock();response.read.return_value=b'{"code":19021,"msg":"private detail"}'
        response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        opener=Mock();opener.open.return_value=response
        payload={'reference':'TC-0123456789ABCDEF','kind':'custom','received_at':'now','review':True}
        with patch('backend.app.services.enquiry_notifications.build_opener',return_value=opener),self.assertRaises(RuntimeError) as caught:
            notifications.deliver(payload,('https://open.feishu.cn/open-apis/bot/v2/hook/test','secret','https://example.invalid'))
        self.assertNotIn('private detail',str(caught.exception))
