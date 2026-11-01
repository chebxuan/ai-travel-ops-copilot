"""Traveller quote projection. Cost, markup and supplier data stay server-side."""
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from backend.app.services import travel_catalog
from backend.app.services.cost_scope import configuration


def quote(request):
    product = travel_catalog.find_product(request)
    policy = configuration()['sales_policy']
    scope = configuration()['products'].get(product['product_id'], {})
    routes = [scope['branches'][choice.choice]['label'] for choice in request.route_choices
              if choice.choice in scope.get('branches', {})]
    selected = travel_catalog.selection(request, product)
    included = ['Standard activities in the selected route']
    included.extend('Selected experience: ' + travel_catalog.experience_content(product, item['name'])['name'] for item in selected)
    service_days = scope.get('land_service_days', request.days)
    if request.need_guide:
        included.append(f'Requested land guide service ({service_days} days)')
    if request.need_private_car:
        included.append(f'Requested land vehicle service ({service_days} days)')
    excluded = ['Hotels booked separately', 'Airport transfers', 'Unselected optional experiences',
                'Personal spending', *scope.get('excluded', [])]
    common = {'currency': policy['currency'], 'basis': 'group_total',
              'travellers': request.adults + request.children + request.seniors,
              'included': included, 'excluded': excluded, 'selected_routes': routes}
    try:
        estimate = travel_catalog.estimate(request)
    except HTTPException as error:
        if error.status_code != 409:
            raise
        reason = error.detail.get('code', 'COST_DATA_REQUIRES_REVIEW')
        return {'kind': 'traveller_sales_quote', 'product_id': product['product_id'],
                'sales_quote': {**common, 'status': 'pending_confirmation', 'amount': None,
                                'reason': reason, 'notice': 'Your route or service costs need confirmation before a price can be estimated.'}}
    amount = (Decimal(str(estimate['cost']['summary']['grand_total'])) * Decimal(policy['multiplier'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if amount <= 0:
        return {'kind': 'traveller_sales_quote', 'product_id': product['product_id'],
                'sales_quote': {**common, 'status': 'pending_confirmation', 'amount': None,
                                'reason': 'NO_PRICED_SERVICES', 'notice': 'No priced services are selected. Please confirm the services needed for your journey.'}}
    return {'kind': 'traveller_sales_quote', 'product_id': product['product_id'],
            'sales_quote': {**common, 'status': 'estimated', 'amount': float(amount), 'reason': None,
                            'notice': 'Estimated group price for the listed services. Availability and final booking price require confirmation.'}}
