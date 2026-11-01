"""Public route projection and validated internal cost estimates.

This service reads backend source data only; it never depends on frontend files.
"""
import json
import re

from fastapi import HTTPException

from backend.app.core.paths import ROOT
from backend.app.engines.cost_engine import calculate_total_cost, load_cost_db, get_effective_price
from backend.app.engines.city_config import get_transport_code_for_city
from backend.app.services.menu_content import product_menu, experience_content
from backend.app.services.cost_scope import configuration, resolve_scope, apply_route_transport


def source_products():
    from backend.app.storage.repository import database_enabled, dataset
    if database_enabled():
        return dataset()['products']
    return json.loads((ROOT / 'data/products/products.normalized.json').read_text(encoding='utf-8'))['products']


def split_activities(text):
    result, start, depth = [], 0, 0
    for index, char in enumerate(text):
        if char in '(（':
            depth += 1
        elif char in ')）':
            depth -= 1
        elif char == '+' and depth == 0:
            result.append(text[start:index].strip())
            start = index + 1
    result.append(text[start:].strip())
    return [part for part in result if part]


def route_days(product):
    days = []
    for day in product['day_plans']:
        branches = re.split(r'\s+或\s+', day['raw_text'])
        common = []
        if product['product_id'] == 'YS-P-02' and day['day_number'] == 3:
            common = ['全地形山地车', '中餐烹饪体验']
            branches = ['岩洞探险', '飞拉达']
        alternatives = [split_activities(branch) for branch in branches] if len(branches) > 1 else []
        days.append({'day': day['day_number'], 'activities': common if alternatives else split_activities(day['raw_text']), 'alternatives': alternatives})
    return days


def optional_choices(product, db):
    # Match by name among this product's allowed codes. Never zip unequal arrays.
    choices = []
    for name in product['optional_items']:
        matches = [code for code in product['optional_item_codes'] if db.get(code, {}).get('name') == name]
        choices.append({'name': name, 'code': matches[0] if len(matches) == 1 else None, 'cost_available': len(matches) == 1})
    return choices


def public_product(product):
    days = route_days(product)
    incomplete = len(days) != product['duration_days']
    db = load_cost_db(city=product['city'])
    choices = optional_choices(product, db)
    scope = configuration()['products'].get(product['product_id'], {})
    notices = []
    if incomplete:
        notices.append('游轮分日安排与返程衔接待确认，暂展示路线概览。')
    if any(not choice['cost_available'] for choice in choices):
        notices.append('部分可选体验的费用映射待复核，暂不能自动计算费用。')
    if any(db.get(code, {}).get('name') in product['optional_items'] for code in product['regular_item_codes']):
        notices.append('常规项目编号与可选项目名称冲突，产品费用需人工复核。')
    return {
        'product_id': product['product_id'], 'city': product['city'],
        'name': product['product_name'], 'days': product['duration_days'],
        'day_plans': [] if incomplete else days,
        'overview': [day['raw_text'] for day in product['day_plans']] if incomplete else [],
        'optional_choices': choices, 'notices': notices,
        'sales_quote': {'status': 'pending_confirmation', 'amount': None, 'currency': 'CNY'},
        'menu': product_menu(product),
        'quote_route_options': [{'day': scope['day'], 'choice': key, 'label': branch['label'], 'excluded_optional_items': branch.get('excluded_optional', [])} for key, branch in scope.get('branches', {}).items()],
        'quote_guide_options': [{'code': code, 'label': {'英文导游-初级': 'English-speaking guide', '英文导游-高级': 'Senior English-speaking guide'}[item['name']]} for code, item in db.items() if '-GUIDE-' in code and item['name'] in {'英文导游-初级', '英文导游-高级'}],
    }


def find_product(request):
    candidates = [product for product in source_products() if product['city'] == request.city and product['duration_days'] == request.days]
    if request.product_id:
        selected = next((product for product in source_products() if product['product_id'] == request.product_id), None)
        if selected is None:
            raise HTTPException(404, detail={'code': 'PRODUCT_NOT_FOUND'})
        if selected not in candidates:
            raise HTTPException(422, detail={'code': 'PRODUCT_DESTINATION_DURATION_MISMATCH'})
        return selected
    if not candidates:
        raise HTTPException(404, detail={'code': 'NO_STANDARD_ROUTE', 'available_days': sorted({product['duration_days'] for product in source_products() if product['city'] == request.city})})
    return candidates[0]


def selection(request, product):
    choices = optional_choices(product, load_cost_db(city=product['city']))
    by_name = {choice['name']: choice for choice in choices}
    by_code = {choice['code']: choice for choice in choices if choice['code']}
    if request.selected_optional_items and request.selected_optional_item_codes:
        raise HTTPException(422, detail={'code': 'USE_NAMES_OR_CODES'})
    values = request.selected_optional_items or request.selected_optional_item_codes
    mapping = by_name if request.selected_optional_items else by_code
    if len(values) != len(set(values)):
        raise HTTPException(422, detail={'code': 'DUPLICATE_OPTIONAL_SELECTION'})
    if any(value not in mapping for value in values):
        raise HTTPException(422, detail={'code': 'OPTION_NOT_IN_PRODUCT'})
    return [mapping[value] for value in values]


def preview(request):
    product = find_product(request)
    selected = selection(request, product)
    return {'product': public_product(product), 'request': request.model_dump(mode='json'), 'selected_optional_choices': selected,
            'selected_experiences': [experience_content(product, item['name']) for item in selected]}


def estimate(request):
    product = find_product(request)
    selected = selection(request, product)
    db = load_cost_db(city=product['city'])
    days = route_days(product)
    effective_product, scope, branch = resolve_scope(request, product, selected)
    if (len(days) != product['duration_days'] or any(day['alternatives'] for day in days)) and not scope:
        raise HTTPException(409, detail={'code': 'ROUTE_SCOPE_REQUIRES_REVIEW', 'message': '需先确认路线分支或游轮范围，暂不自动合并计算费用。'})
    # Prevent corrected regular codes from regressing into optional services.
    unexpected = [code for code in product['regular_item_codes'] if db.get(code, {}).get('name') in product['optional_items']]
    if unexpected or any(not choice['code'] for choice in selected):
        raise HTTPException(409, detail={'code': 'CONTENT_COST_MAPPING_REQUIRES_REVIEW', 'message': '产品项目与费用映射需要复核，暂不返回费用总额。'})
    if request.need_guide and not request.guide_code:
        raise HTTPException(422, detail={'code': 'GUIDE_CODE_REQUIRED'})
    if request.guide_code and (request.guide_code not in db or '-GUIDE-' not in request.guide_code or not request.need_guide):
        raise HTTPException(422, detail={'code': 'INVALID_GUIDE_SELECTION'})
    if request.guide_code and get_effective_price(db[request.guide_code], request.is_peak) <= 0:
        raise HTTPException(409, detail={'code': 'GUIDE_COST_REQUIRES_REVIEW'})
    if request.guide_code and db[request.guide_code]['name'] not in {'英文导游-初级', '英文导游-高级'}:
        raise HTTPException(409, detail={'code': 'GUIDE_SCOPE_REQUIRES_REVIEW'})
    if request.need_private_car and request.adults + request.children + request.seniors > 7:
        raise HTTPException(409, detail={'code': 'VEHICLE_CAPACITY_REQUIRES_REVIEW'})
    if request.need_private_car:
        car_code = get_transport_code_for_city(product['city'], request.adults + request.children + request.seniors)
        if car_code not in db or get_effective_price(db[car_code], request.is_peak) <= 0:
            raise HTTPException(409, detail={'code': 'VEHICLE_COST_REQUIRES_REVIEW'})
    service_days = scope.get('land_service_days', request.days)
    result = calculate_total_cost(effective_product, {
        'city': request.city, 'days': request.days, 'adults': request.adults,
        'children': request.children, 'seniors': request.seniors, 'is_peak': request.is_peak,
        'guide': request.guide_code, 'need_guide': request.need_guide,
        'guide_days': service_days,
        'need_private_car': request.need_private_car, 'car_days': service_days if request.need_private_car else 0,
        'hotel': None, 'hotel_nights': 0, 'transfer': None, 'transfer_times': 0,
        'selected_optional': [choice['code'] for choice in selected],
    })
    if not result['success']:
        raise HTTPException(409, detail={'code': 'COST_DATA_REQUIRES_REVIEW', 'issues': result.get('validation_issues', [])})
    result = apply_route_transport(result, request, product, scope, branch, db)
    return {'kind': 'internal_cost_estimate', 'product_id': product['product_id'],
            'included_scope': ['selected_route_regular_items', 'selected_optional_items', 'requested_guide_and_car'],
            'excluded_scope': ['hotel', 'airport_transfer', 'profit_margin', 'sales_quote', *scope.get('excluded', [])],
            'cost': result, 'sales_quote': {'status': 'pending_confirmation', 'amount': None, 'currency': 'CNY'}}
