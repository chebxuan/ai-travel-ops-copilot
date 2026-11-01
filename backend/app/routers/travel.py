from fastapi import APIRouter, Depends, Query

from backend.app.services import travel_catalog
from backend.app.services import sales_pricing
from backend.app.services import enquiry_tokens, journey_enquiries
from backend.app.storage.repository import runtime_snapshot
from backend.app.travel_schemas import (
    CatalogueResponse, CostEstimateRequest, InternalCostResponse,
    TripPreviewRequest, TripPreviewResponse,
    SalesQuoteResponse,
    JourneyEnquiryRequest, JourneyEnquiryReceipt, CustomEnquiryRequest,
)


def create_travel_router(auth_dependency, signing_key):
    # Reuse server authentication without importing main.py (no circular imports).
    router = APIRouter(prefix='/api/v3', tags=['Travel catalogue and preview'], dependencies=[Depends(auth_dependency)])

    @router.get('/products', response_model=CatalogueResponse)
    def catalogue(city: str | None = Query(None, max_length=100)):
        with runtime_snapshot():
            products = [product for product in travel_catalog.source_products() if city is None or product['city'] == city]
            days = {}
            for product in products:
                days.setdefault(product['city'], set()).add(product['duration_days'])
            return {'products': [travel_catalog.public_product(product) for product in products],
                    'available_days': {name: sorted(values) for name, values in days.items()}}

    @router.post('/trips/preview', response_model=TripPreviewResponse)
    def preview(request: TripPreviewRequest):
        with runtime_snapshot():
            result = TripPreviewResponse.model_validate(travel_catalog.preview(request)).model_dump(mode='json', exclude={'preview_token'})
            result['preview_token'] = enquiry_tokens.issue('preview', result, signing_key)
            return result

    @router.post('/internal/cost-estimate', response_model=InternalCostResponse)
    def cost_estimate(request: CostEstimateRequest):
        with runtime_snapshot():
            return travel_catalog.estimate(request)

    @router.post('/trips/quote', response_model=SalesQuoteResponse)
    def sales_quote(request: CostEstimateRequest):
        with runtime_snapshot():
            result = SalesQuoteResponse.model_validate(sales_pricing.quote(request)).model_dump(mode='json', exclude={'quote_token'})
            result['quote_token'] = enquiry_tokens.issue('quote', {'request': request.model_dump(mode='json'), 'quote': result}, signing_key)
            return result

    @router.post('/trips/enquiries', response_model=JourneyEnquiryReceipt, status_code=201)
    def enquiry(request: JourneyEnquiryRequest):
        return journey_enquiries.submit(request, signing_key)

    @router.post('/trips/custom-enquiries', response_model=JourneyEnquiryReceipt, status_code=201)
    def custom_enquiry(request: CustomEnquiryRequest):
        return journey_enquiries.submit(request, custom=True)

    return router
