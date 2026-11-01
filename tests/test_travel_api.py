"""Standalone API checks: no frontend, paid model calls, or writable business data."""
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from backend.app.services.travel_catalog import source_products


class TravelApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {'API_KEY': 'standalone-test-only'}):
            from backend.app import main
        cls.api = main
        cls.client = TestClient(main.app)
        cls.headers = {'X-API-Key': main.API_KEY}

    def post(self, path, payload):
        return self.client.post('/api/v3/'+path, headers=self.headers, json=payload)

    def test_catalogue_and_safe_projection(self):
        response = self.client.get('/api/v3/products', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data['products']), 21)
        self.assertEqual(len(data['available_days']), 10)
        self.assertEqual(data['available_days']['成都'], [2])
        self.assertEqual(data['available_days']['贵州'], [4])
        self.assertEqual(data['available_days']['云南'], [5])
        for forbidden in ['unit_price', 'grand_total', 'supplier', 'metadata', 'regular_item_codes']:
            self.assertNotIn('"'+forbidden+'"', response.text)
        for product in data['products']:
            payload = {'city': product['city'], 'days': product['days'], 'product_id': product['product_id']}
            result = self.post('trips/preview', payload)
            self.assertEqual(result.status_code, 200, product['product_id'])
            route = result.json()['product']
            self.assertIsNone(route['sales_quote']['amount'])
            self.assertEqual(len(route['day_plans']), 0 if product['product_id'] == 'CQ-P-03' else product['days'])
        self.assertEqual(len(self.client.get('/api/v3/products?city=上海', headers=self.headers).json()['products']), 3)

    def test_retired_routes_are_unavailable(self):
        # The current custom-enquiries contact flow is covered separately;
        # these are the removed operational/Shanghai-planner APIs.
        for path in ["/api/v2/custom-route", "/api/lead/parse", "/api/v2/lead-text-full-chain",
                     "/api/v2/full_chain", "/api/v2/payments", "/api/llm/status"]:
            method = "get" if path in {"/api/v2/payments", "/api/llm/status"} else "post"
            response = getattr(self.client, method)(path, headers=self.headers)
            self.assertEqual(response.status_code, 404, path)

    def test_named_choices_and_shanghai_code_alignment(self):
        response = self.post('trips/preview', {'city': '上海', 'days': 3, 'selected_optional_items': ['本帮菜', '法租界小酌']})
        self.assertEqual(response.status_code, 200)
        choices = response.json()['selected_optional_choices']
        self.assertEqual([choice['code'] for choice in choices], ['SH-ACTIVITY-03', 'SH-ACTIVITY-06'])
        by_code = self.post('trips/preview', {'city': '上海', 'days': 3, 'selected_optional_item_codes': ['SH-ACTIVITY-03']})
        self.assertEqual(by_code.json()['selected_optional_choices'][0]['name'], '本帮菜')
        for payload in [
            {'selected_optional_items': ['唐乐舞表演']},
            {'selected_optional_items': ['本帮菜', '本帮菜']},
            {'selected_optional_item_codes': ['SH-ACTIVITY-05']},
            {'selected_optional_items': ['本帮菜'], 'selected_optional_item_codes': ['SH-ACTIVITY-03']},
        ]:
            self.assertEqual(self.post('trips/preview', {'city': '上海', 'days': 3, **payload}).status_code, 422)

    def test_strict_validation_and_auth(self):
        for payload in [
            {'days': 10}, {'city': '不存在'}, {'product_id': 'SH-P-01'},
            {'days': '3'}, {'adults': 0}, {'children': -1}, {'adults': 20, 'children': 1},
            {'travel_date': '2026-02-30'}, {'notes': 'x'*2001}, {'extra': True},
        ]:
            self.assertIn(self.post('trips/preview', {'city': '北京', 'days': 3, **payload}).status_code, [404, 422])
        self.assertEqual(self.client.get('/api/v3/products', headers={'X-API-Key': 'wrong'}).status_code, 401)
        self.assertEqual(self.client.get('/api/v3/products').status_code, 422)
        self.assertEqual(self.client.post('/api/v3/internal/cost-estimate', headers={'X-API-Key': 'wrong'}, json={'city': '上海', 'days': 2, 'is_peak': True}).status_code, 401)

    def test_branches_and_incomplete_route(self):
        for city, days, index in [('重庆', 2, 1), ('张家界', 3, 2), ('阳朔', 3, 2)]:
            route = self.post('trips/preview', {'city': city, 'days': days}).json()['product']
            self.assertEqual(len(route['day_plans'][index]['alternatives']), 2)
        cruise = self.post('trips/preview', {'city': '重庆', 'days': 5}).json()['product']
        self.assertEqual(cruise['day_plans'], [])
        self.assertEqual(len(cruise['overview']), 3)

    def test_cost_increment_and_review_gates(self):
        base = {'city': '上海', 'days': 3, 'is_peak': True}
        baseline = self.post('internal/cost-estimate', base)
        selected = self.post('internal/cost-estimate', {**base, 'selected_optional_items': ['黄浦江夜游']})
        self.assertEqual(baseline.status_code, 200)
        self.assertEqual(selected.status_code, 200)
        self.assertGreater(selected.json()['cost']['summary']['grand_total'], baseline.json()['cost']['summary']['grand_total'])
        self.assertEqual(selected.json()['kind'], 'internal_cost_estimate')
        self.assertIsNone(selected.json()['sales_quote']['amount'])
        self.assertEqual(baseline.json()['cost']['summary']['hotel_nights'], 0)
        self.assertEqual(baseline.json()['cost']['summary']['car_days'], 0)
        services = self.post('internal/cost-estimate', {**base, 'need_guide': True, 'guide_code': 'SH-GUIDE-01', 'need_private_car': True})
        self.assertEqual(services.status_code, 200)
        self.assertGreater(services.json()['cost']['category_subtotals']['guide'], 0)
        self.assertGreater(services.json()['cost']['category_subtotals']['transport'], 0)
        self.assertEqual(self.post('internal/cost-estimate', {**base, 'need_guide': True}).status_code, 422)
        self.assertEqual(self.post('internal/cost-estimate', {**base, 'guide_code': 'BJ-GUIDE-01', 'need_guide': True}).status_code, 422)
        self.assertEqual(self.post('internal/cost-estimate', {**base, 'adults': 8, 'need_private_car': True}).status_code, 409)
        for city, days in [('重庆', 2), ('阳朔', 3), ('张家界', 3)]:
            response = self.post('internal/cost-estimate', {'city': city, 'days': days, 'is_peak': True})
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json()['detail']['code'], 'ROUTE_SCOPE_REQUIRES_REVIEW')
        for days in [2, 3, 4]:
            response = self.post('internal/cost-estimate', {'city': '北京', 'days': days, 'is_peak': True})
            self.assertEqual(response.status_code, 200)
        review_ids = {'CQ-P-01', 'YS-P-02', 'ZJJ-P-02'}
        for product in source_products():
            result = self.post('internal/cost-estimate', {'city': product['city'], 'days': product['duration_days'], 'is_peak': False})
            self.assertEqual(result.status_code, 409 if product['product_id'] in review_ids else 200, product['product_id'])


if __name__ == '__main__':
    unittest.main()
