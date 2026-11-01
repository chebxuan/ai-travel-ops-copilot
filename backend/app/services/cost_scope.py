"""Reviewed route scopes, separate from legacy totals and marketing copy."""
import json
from copy import deepcopy
from fastapi import HTTPException
from backend.app.core.paths import ROOT
from backend.app.engines.cost_engine import get_effective_price, load_cost_db
from backend.app.engines.city_config import get_transport_code_for_city


def configuration():
    from backend.app.storage.repository import database_enabled, dataset
    if database_enabled():
        return dataset()['configuration']
    return json.loads((ROOT / 'data/products/cost_scope.json').read_text(encoding='utf-8'))


def resolve_scope(request, product, selected):
    spec = configuration()['products'].get(product['product_id'], {})
    choices = request.route_choices
    branch = None
    if spec.get('branches'):
        if not choices:
            raise HTTPException(409, detail={'code': 'ROUTE_SCOPE_REQUIRES_REVIEW', 'required_day': spec['day'], 'choices': list(spec['branches'])})
        if len(choices) != 1 or choices[0].day != spec['day'] or choices[0].choice not in spec['branches']:
            raise HTTPException(422, detail={'code': 'INVALID_ROUTE_SELECTION'})
        branch = spec['branches'][choices[0].choice]
        if any(item['name'] in branch.get('excluded_optional', []) for item in selected):
            raise HTTPException(422, detail={'code': 'OPTION_NOT_IN_SELECTED_ROUTE'})
    elif choices:
        raise HTTPException(422, detail={'code': 'ROUTE_SELECTION_NOT_APPLICABLE'})
    review = spec.get('review') or (branch or {}).get('review')
    if review:
        raise HTTPException(409, detail={'code': review})
    db = load_cost_db(city=product['city'])
    expected = spec.get('expected_names', {})
    for code, name in expected.items():
        item = db.get(code)
        if not item or item['name'] != name or (item['price'] <= 0 and code not in spec.get('confirmed_free_codes', [])):
            raise HTTPException(409, detail={'code': 'CONTENT_COST_MAPPING_REQUIRES_REVIEW'})
        if code in spec.get('confirmed_free_codes', []) and (item['price'] != 0 or item['price_peak'] != 0):
            raise HTTPException(409, detail={'code': 'CONTENT_COST_MAPPING_REQUIRES_REVIEW'})
    if expected:
        for names, codes in [(product['regular_items'], product['regular_item_codes']), (product['optional_items'], product['optional_item_codes'])]:
            if len(names) != len(codes) or any(db.get(code, {}).get('name') != name for name, code in zip(names, codes)):
                raise HTTPException(409, detail={'code': 'CONTENT_COST_MAPPING_REQUIRES_REVIEW'})
    if spec.get('regular_codes') and product['regular_item_codes'] != spec['regular_codes']:
        raise HTTPException(409, detail={'code': 'CONTENT_COST_MAPPING_REQUIRES_REVIEW'})
    for code in ['YS-ACTIVITY-02', 'CQ-ACTIVITY-02']:
        if code in expected and db[code]['unit'] != '人/次':
            raise HTTPException(409, detail={'code': 'COST_UNIT_REQUIRES_REVIEW'})
    effective = deepcopy(product)
    if branch:
        effective['regular_item_codes'] = spec['common_codes'] + branch['codes']
    elif spec.get('regular_codes'):
        effective['regular_item_codes'] = spec['regular_codes']
    return effective, spec, branch


def apply_route_transport(result, request, product, spec, branch, db):
    """Replace one city-car day with reviewed excursion transport; never add both."""
    if not request.need_private_car or not branch or not branch.get('car_code'):
        return result
    regular = get_transport_code_for_city(product['city'], request.adults + request.children + request.seniors)
    schedule = [(regular, request.days - 1), (branch['car_code'], 1)]
    lines = [line for line in result['line_items'] if line['category'] != 'transport']
    total = 0
    for code, days in schedule:
        if not days:
            continue
        if code not in db:
            raise HTTPException(409, detail={'code': 'COST_DATA_REQUIRES_REVIEW'})
        item = db[code]; price = get_effective_price(item, request.is_peak)
        if price <= 0:
            raise HTTPException(409, detail={'code': 'VEHICLE_COST_REQUIRES_REVIEW'})
        subtotal = round(price * days, 2); total += subtotal
        lines.append({'category': 'transport', 'code': code, 'name': item['name'], 'unit': 'day', 'unit_price': price, 'quantity': float(days), 'subtotal': subtotal, 'notes': [item['note']] if item['note'] else [], 'metadata': {}})
    result['line_items'] = lines
    result['category_subtotals']['transport'] = round(total, 2)
    result['transport'] = {**result['transport'], 'car_code': None, 'car_name': 'Route-specific vehicle schedule', 'car_daily_price': 0, 'car_subtotal': round(total, 2), 'subtotal': round(total, 2), 'car_note': 'See transport line_items for per-day vehicles.'}
    amount = round(sum(result['category_subtotals'].values()), 2)
    result['summary']['grand_total'] = amount
    result['summary']['per_person'] = round(amount / result['summary']['total_people'], 2)
    return result
