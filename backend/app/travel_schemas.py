"""Contracts for standalone catalogue, preview and internal cost APIs."""
from datetime import date
from uuid import UUID
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator

from backend.app.schemas import PricingResultJSON

ShortText = Annotated[str, Field(min_length=1, max_length=100)]


class TripPreviewRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    city: ShortText
    days: Annotated[StrictInt, Field(ge=1, le=10)]
    product_id: ShortText | None = None
    adults: Annotated[StrictInt, Field(ge=1, le=20)] = 2
    children: Annotated[StrictInt, Field(ge=0, le=20)] = 0
    seniors: Annotated[StrictInt, Field(ge=0, le=20)] = 0
    travel_date: date | None = None
    need_guide: StrictBool = False
    need_private_car: StrictBool = False
    selected_optional_items: list[ShortText] = Field(default_factory=list, max_length=30)
    selected_optional_item_codes: list[ShortText] = Field(default_factory=list, max_length=30)
    notes: str = Field('', max_length=2000)

    @model_validator(mode='after')
    def limit_group(self):
        if self.adults + self.children + self.seniors > 20:
            raise ValueError('Total passengers must not exceed 20')
        return self


class RouteChoice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    day: Annotated[StrictInt, Field(ge=1, le=10)]
    choice: ShortText


class CostEstimateRequest(TripPreviewRequest):
    is_peak: StrictBool
    guide_code: ShortText | None = None
    route_choices: list[RouteChoice] = Field(default_factory=list, max_length=10)


class OptionalChoice(BaseModel):
    name: str
    code: str | None
    cost_available: bool


class RouteDay(BaseModel):
    day: int
    activities: list[str]
    alternatives: list[list[str]]


class MenuHighlight(BaseModel):
    name: str
    description: str


class MenuStory(BaseModel):
    title: str
    description: str
    highlights: list[MenuHighlight]
    alternatives: list['MenuStory']
    choice: str | None = None


class MenuDay(MenuStory):
    day: int


class ProductMenu(BaseModel):
    title: str
    city_name: str
    introduction: str
    days: list[MenuDay]
    overview: list[MenuStory]
    notice: str


class SelectedExperience(BaseModel):
    name: str
    description: str
    duration: str | None
    price_status: Literal['pending_confirmation']


class PendingSalesQuote(BaseModel):
    status: Literal['pending_confirmation'] = 'pending_confirmation'
    amount: None = None
    currency: Literal['CNY'] = 'CNY'


class QuoteRouteOption(BaseModel):
    day: int
    choice: str
    label: str
    excluded_optional_items: list[str]


class QuoteGuideOption(BaseModel):
    code: str
    label: str


class PublicProduct(BaseModel):
    product_id: str
    city: str
    name: str
    days: int
    day_plans: list[RouteDay]
    overview: list[str]
    optional_choices: list[OptionalChoice]
    notices: list[str]
    sales_quote: PendingSalesQuote
    menu: ProductMenu
    quote_route_options: list[QuoteRouteOption]
    quote_guide_options: list[QuoteGuideOption]


class CatalogueResponse(BaseModel):
    products: list[PublicProduct]
    available_days: dict[str, list[int]]


class TripPreviewResponse(BaseModel):
    product: PublicProduct
    request: TripPreviewRequest
    selected_optional_choices: list[OptionalChoice]
    selected_experiences: list[SelectedExperience]
    preview_token: str | None = None


class InternalCostResponse(BaseModel):
    kind: Literal['internal_cost_estimate']
    product_id: str
    included_scope: list[str]
    excluded_scope: list[str]
    cost: PricingResultJSON
    sales_quote: PendingSalesQuote


class SalesQuote(BaseModel):
    status: Literal['estimated', 'pending_confirmation']
    amount: float | None
    currency: Literal['CNY'] = 'CNY'
    basis: Literal['group_total'] = 'group_total'
    travellers: int
    included: list[str]
    excluded: list[str]
    selected_routes: list[str]
    reason: str | None = None
    notice: str


class SalesQuoteResponse(BaseModel):
    kind: Literal['traveller_sales_quote'] = 'traveller_sales_quote'
    product_id: str
    sales_quote: SalesQuote
    quote_token: str | None = None


HotelPreference = Literal['discuss', 'arrange', 'self_booked']


class JourneyEnquiryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    request_id: UUID
    name: Annotated[str, Field(min_length=1, max_length=120)]
    email: Annotated[str, Field(min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')]
    message: str = Field('', max_length=2000)
    hotel_preference: HotelPreference = 'discuss'
    preview_token: Annotated[str, Field(min_length=100, max_length=100000)]
    quote_token: Annotated[str, Field(min_length=100, max_length=20000)] | None = None
    route_choices: list[RouteChoice] = Field(default_factory=list, max_length=10)
    website: str = Field('', max_length=0)


class JourneyEnquiryReceipt(BaseModel):
    reference: str
    status: Literal['received']


class CustomEnquiryRequest(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    request_id: UUID
    name: Annotated[str, Field(min_length=1, max_length=120)]
    email: Annotated[str, Field(min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')]
    message: str = Field('', max_length=2000)
    destinations: str = Field('', max_length=300)
    travel_dates: str = Field('', max_length=120)
    duration: str = Field('', max_length=120)
    travellers: int = Field(2, ge=1, le=60)
    interests: str = Field('', max_length=1000)
    hotel_preference: HotelPreference = 'discuss'
    website: str = Field('', max_length=0)
