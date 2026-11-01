"""Verify synthetic Menu structure and product-day membership."""
import json
import unittest

from backend.app.core.paths import ROOT
from backend.app.services.menu_content import product_menu, experience_content
from backend.app.services.travel_catalog import source_products


class MenuContentTests(unittest.TestCase):
    def setUp(self):
        self.content = json.loads((ROOT / 'data/products/attraction_highlights.json').read_text())
        self.products = {p['product_id']: p for p in source_products()}

    def test_demo_content_structure(self):
        pdf_cities = [city for city in self.content if city != '成都']
        self.assertEqual(sum(len(self.content[city]['routes']) for city in pdf_cities), 26)
        self.assertEqual(sum(len(self.content[city]['activities']) for city in pdf_cities), 19)
        self.assertIn('Hands-on silver-making workshop', self.content['贵州']['activities'])
        self.assertIn('Xiasi Ancient Town', [a['name'] for a in self.content['贵州']['routes']['Route 1']['attractions']])
        self.assertIn('Black Dragon Pool', [a['name'] for a in self.content['云南']['routes']['Route 1']['attractions']])
        self.assertNotIn('Tianmen', self.content['贵州']['routes']['Route 1']['description'])
        self.assertIn('Synthetic', self.content['西安']['routes']['Route 2']['description'])

    def test_shanghai_day_order_and_demo_copy(self):
        menu = product_menu(self.products['SH-P-02'])
        self.assertEqual([day['title'] for day in menu['days']], ['上海 / Route 1 / demo', '上海 / Route 3 / demo', '上海 / Route 2 / demo'])
        self.assertEqual(menu['days'][1]['description'], self.content['上海']['routes']['Route 3']['description'])
        self.assertNotIn('Disneyland', json.dumps(menu))

    def test_special_days_and_membership(self):
        beijing = product_menu(self.products['BJ-P-03'])
        self.assertNotIn('Summer Palace', json.dumps(beijing['days'][1]))
        self.assertNotIn('Great Wall', json.dumps(beijing['days'][3]))
        xian = product_menu(self.products['XA-P-02'])
        self.assertEqual(xian['days'][2]['title'], 'Demonstration route option')
        yunnan = product_menu(self.products['YN-P-01'])
        self.assertNotIn('Black Dragon Pool', json.dumps(yunnan))
        self.assertNotIn('Xizhou', json.dumps(yunnan))
        guizhou = product_menu(self.products['GZH-P-01'])
        self.assertEqual(len(guizhou['days'][2]['highlights']), 1)
        self.assertNotEqual(guizhou['days'][0]['description'], guizhou['days'][3]['description'])

    def test_all_products_and_experiences(self):
        for product in self.products.values():
            menu = product_menu(product)
            self.assertTrue(menu['introduction'])
            self.assertEqual(len(menu['days']), 0 if product['product_id'] == 'CQ-P-03' else product['duration_days'])
            for name in product['optional_items']:
                experience = experience_content(product, name)
                self.assertTrue(experience['description'])
                self.assertNotIn('price', experience)
                self.assertNotIn('RMB', json.dumps(experience))
        cruise = product_menu(self.products['CQ-P-03'])
        self.assertEqual(len(cruise['overview']), 3)
        self.assertTrue(cruise['notice'])


if __name__ == '__main__':
    unittest.main()
