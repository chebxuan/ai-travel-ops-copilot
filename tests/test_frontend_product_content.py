"""Check public route fidelity without network or backend mutations."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class PublicContentTests(unittest.TestCase):
    def setUp(self):
        self.records = json.loads((ROOT / 'frontend/data/products.json').read_text())
        self.source = json.loads((ROOT / 'data/products/products.normalized.json').read_text())['products']
        self.by_id = {product['id']: product for product in self.records}

    def test_catalogue_and_field_whitelist(self):
        self.assertEqual(len(self.records), 21)
        self.assertEqual(len(self.by_id), 21)
        self.assertEqual(len({product['city'] for product in self.records}), 10)
        allowed = {'id', 'city', 'title', 'days', 'dayPlans', 'overview', 'notice', 'optionalItems'}
        for product in self.records:
            self.assertEqual(set(product), allowed)
        for source in self.source:
            product = self.by_id[source['product_id']]
            self.assertEqual(product['days'], source['duration_days'])
            self.assertEqual(product['optionalItems'], source['optional_items'])
            if product['id'] != 'CQ-P-03':
                self.assertEqual([day['number'] for day in product['dayPlans']], list(range(1, product['days'] + 1)))

    def test_activity_order_and_qualifiers(self):
        for source in self.source:
            if source['product_id'] == 'CQ-P-03':
                continue
            for original, public in zip(source['day_plans'], self.by_id[source['product_id']]['dayPlans']):
                if public['alternatives']:
                    continue
                # Compare full route text so parentheses and recommended/optional qualifiers survive.
                joined = '+'.join(activity['title'] for activity in public['activities'])
                self.assertEqual(''.join(joined.split()), ''.join(original['raw_text'].split()))

    def test_branches_and_incomplete_cruise(self):
        for product_id, index in [('CQ-P-01', 1), ('ZJJ-P-02', 2), ('YS-P-02', 2)]:
            day = self.by_id[product_id]['dayPlans'][index]
            self.assertEqual(len(day['alternatives']), 2)
        yangshuo = self.by_id['YS-P-02']['dayPlans'][2]
        self.assertEqual([item['title'] for item in yangshuo['activities']], ['全地形山地车', '中餐烹饪体验'])
        self.assertEqual([branch[0]['title'] for branch in yangshuo['alternatives']], ['岩洞探险', '飞拉达'])
        cruise = self.by_id['CQ-P-03']
        self.assertEqual(cruise['dayPlans'], [])
        self.assertEqual(len(cruise['overview']), 3)
        self.assertIn('待确认', cruise['notice'])


if __name__ == '__main__':
    unittest.main()
