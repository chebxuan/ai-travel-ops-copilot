"""Export a public content whitelist; never export costs or supplier records."""
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def split_activities(text):
    parts, start, depth = [], 0, 0
    for index, char in enumerate(text):
        if char in '(（':
            depth += 1
        elif char in ')）':
            depth -= 1
        elif char == '+' and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    parts.append(text[start:].strip())
    return [part for part in parts if part]


def activity(text):
    label = '可选' if '可选' in text else '推荐' if '推荐' in text or '建议' in text else '外景' if '外景' in text else '行程'
    return {'title': text, 'label': label}


def export():
    source = ROOT / 'data/products/products.normalized.json'
    records = json.loads(source.read_text())['products']
    with (ROOT / 'data/products/product_library.csv').open(newline='') as handle:
        rows = {row['产品编号 (ProductID)']: row for row in csv.DictReader(handle)}
    products = []
    for record in records:
        row = rows[record['product_id']]
        assert record['city'] == row['城市 (City)']
        assert record['duration_days'] == int(row['行程天数 (Duration)'])
        normalize = lambda text: re.sub(r'\s+', '', text)
        assert normalize(record['itinerary_text']) == normalize(row['每日行程 (Daily Itinerary)'])
        days = []
        for day in record['day_plans']:
            text = day['raw_text']
            branches = re.split(r'\s+或\s+', text)
            common = []
            if record['product_id'] == 'YS-P-02' and day['day_number'] == 3:
                common = ['全地形山地车', '中餐烹饪体验']
                branches = ['岩洞探险', '飞拉达']
            alternatives = [[activity(item) for item in split_activities(branch)] for branch in branches] if len(branches) > 1 else []
            activities = [activity(item) for item in (common if alternatives else split_activities(text))]
            title = '不同方向，选择其一' if alternatives else ' · '.join(item['title'] for item in activities[:2])
            days.append({'number': day['day_number'], 'title': title, 'activities': activities, 'alternatives': alternatives})
        incomplete = len(days) != record['duration_days']
        products.append({
            'id': record['product_id'], 'city': record['city'], 'title': record['product_name'],
            'days': record['duration_days'], 'dayPlans': [] if incomplete else days,
            'overview': [day['raw_text'] for day in record['day_plans']] if incomplete else [],
            'notice': '山城、大足与三峡游轮组成 5 日路线，游轮分日安排与返程衔接待确认。暂展示路线概览。' if incomplete else '',
            'optionalItems': record['optional_items'],
        })
    assert len(products) == len(rows) == 21
    assert len({product['id'] for product in products}) == 21
    (ROOT / 'frontend/data/products.json').write_text(json.dumps(products, ensure_ascii=False, indent=2) + '\n')
    presentation = json.loads((ROOT / 'data/products/menu_presentation.json').read_text())
    labels = {key: presentation[key] for key in ['city_names', 'product_titles', 'optional_labels']}
    (ROOT / 'frontend/data/product_labels.json').write_text(json.dumps(labels, ensure_ascii=False, indent=2) + '\n')
    print(f'Exported {len(products)} public products; incomplete daily plans retained as overview.')


if __name__ == '__main__':
    export()
