"""Signed handoff/API validation; no database writes or external calls."""
import os
import unittest
import uuid
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.app.services import enquiry_tokens


class EnquiryApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {'API_KEY': 'enquiry-test-only'}):
            from backend.app import main
        cls.api = main
        cls.client = TestClient(main.app)
        cls.headers = {'X-API-Key': main.API_KEY}

    def preview(self):
        return self.client.post('/api/v3/trips/preview', headers=self.headers, json={'city':'上海','days':3,'need_guide':True}).json()

    def payload(self):
        return {'request_id':str(uuid.uuid4()),'name':'Example Traveller','email':'test@example.invalid','preview_token':self.preview()['preview_token']}

    def test_public_signed_snapshot(self):
        result=self.preview()
        data=enquiry_tokens.verify(result['preview_token'],'preview',self.api.API_KEY)
        self.assertEqual(data['product']['product_id'],'SH-P-02')
        self.assertTrue(data['request']['need_guide'])
        text=str(data)
        for field in ['unit_price','grand_total','supplier','multiplier']:
            self.assertNotIn(field,text)

    def test_signature_type_and_expiry(self):
        signed=enquiry_tokens.issue('preview',{'public':'only'},'secret')
        for value,kind,key in [(signed+'x','preview','secret'),(signed,'quote','secret'),(signed,'preview','wrong')]:
            with self.assertRaises(Exception) as error:enquiry_tokens.verify(value,kind,key)
            self.assertEqual(error.exception.status_code,422)
        with patch('backend.app.services.enquiry_tokens.time.time',return_value=1):
            expired=enquiry_tokens.issue('preview',{},'secret')
        with self.assertRaises(Exception) as error:enquiry_tokens.verify(expired,'preview','secret')
        self.assertEqual(error.exception.status_code,409)

    def test_validation_auth_and_file_mode(self):
        payload=self.payload()
        for extra in [{'name':' '},{'email':'bad address'},{'message':'x'*2001},{'request_id':'not-a-uuid'},{'website':'spam'},{'amount':1},{'hotel_preference':'invented'}]:
            response=self.client.post('/api/v3/trips/enquiries',headers=self.headers,json={**payload,**extra})
            self.assertEqual(response.status_code,422)
        self.assertEqual(self.client.post('/api/v3/trips/enquiries',headers={'X-API-Key':'wrong'},json=payload).status_code,401)
        with patch.dict(os.environ,{'TRAVEL_DATA_SOURCE':'files'}):
            result=self.client.post('/api/v3/trips/enquiries',headers=self.headers,json=payload)
        self.assertEqual(result.status_code,503)
        self.assertEqual(result.json()['detail']['code'],'ENQUIRY_UNAVAILABLE')

    def test_receipt_projection_and_storage_failure(self):
        payload=self.payload()
        with patch('backend.app.services.journey_enquiries.submit',return_value={'reference':'TC-TEST','status':'received','internal_cost':123,'email':'private'}):
            response=self.client.post('/api/v3/trips/enquiries',headers=self.headers,json=payload)
        self.assertEqual(response.status_code,201)
        self.assertEqual(response.json(),{'reference':'TC-TEST','status':'received'})
        with patch.dict(os.environ,{'TRAVEL_DATA_SOURCE':'postgres'}),patch('backend.app.services.journey_enquiries.intake_connection',side_effect=RuntimeError('No config')):
            response=self.client.post('/api/v3/trips/enquiries',headers=self.headers,json=payload)
        self.assertEqual(response.status_code,503)

    def test_custom_enquiry_validation_and_receipt(self):
        payload = {'request_id': str(uuid.uuid4()), 'name': 'Example', 'email': 'custom@example.invalid', 'hotel_preference': 'arrange', 'destinations': 'Shanghai and Yunnan'}
        path = '/api/v3/trips/custom-enquiries'
        for extra in [{'email': 'bad'}, {'travellers': 0}, {'travellers': 61}, {'hotel_preference': 'invented'}, {'website': 'spam'}, {'amount': 100}, {'destinations': 'x'*301}]:
            self.assertEqual(self.client.post(path, headers=self.headers, json={**payload, **extra}).status_code, 422)
        self.assertEqual(self.client.post(path, headers={"X-API-Key":"wrong"}, json=payload).status_code, 401)
        with patch('backend.app.services.journey_enquiries.submit', return_value={'reference': 'TC-CUSTOM', 'status': 'received', 'email': 'private'} ) as submit:
            response = self.client.post(path, headers=self.headers, json=payload)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.json(), {'reference': 'TC-CUSTOM', 'status': 'received'})
            self.assertTrue(submit.call_args.kwargs['custom'])
        with patch.dict(os.environ, {'TRAVEL_DATA_SOURCE': 'files'}):
            self.assertEqual(self.client.post(path, headers=self.headers, json=payload).status_code, 503)


if __name__=='__main__':unittest.main()
