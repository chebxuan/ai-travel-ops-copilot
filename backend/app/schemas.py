"""Shared internal cost response models for the current travel website."""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class PricingValidationIssue(BaseModel):
    field: str
    code: Optional[str] = None
    codes: List[Any] = Field(default_factory=list)
    message: str
    severity: Literal["warning", "error"] = "error"


class PricingLineItem(BaseModel):
    category: Literal["ticket_activity", "hotel", "transport", "guide", "other"]
    code: Optional[str] = None
    name: str
    unit: Optional[str] = None
    unit_price: float = Field(0, ge=0)
    quantity: float = Field(0, ge=0)
    subtotal: float = Field(0, ge=0)
    notes: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PricingSummary(BaseModel):
    city: str
    product_name: str
    days: int = Field(..., ge=1)
    total_people: int = Field(..., ge=1)
    adults: int = Field(..., ge=1)
    children: int = Field(0, ge=0)
    seniors: int = Field(0, ge=0)
    is_peak: bool
    hotel_nights: int = Field(0, ge=0)
    car_days: int = Field(0, ge=0)
    transfer_times: int = Field(0, ge=0)
    grand_total: float = Field(..., ge=0)
    per_person: float = Field(..., ge=0)
    currency: str = Field("RMB")


class PricingResultJSON(BaseModel):
    lead_id: Optional[str] = None
    selected_product_id: Optional[str] = None
    success: bool = True
    summary: Optional[PricingSummary] = None
    line_items: List[PricingLineItem] = Field(default_factory=list)
    category_subtotals: Dict[str, float] = Field(default_factory=dict)
    regular_item_codes: List[str] = Field(default_factory=list)
    selected_optional_item_codes: List[str] = Field(default_factory=list)
    validation_issues: List[PricingValidationIssue] = Field(default_factory=list)
    error: Optional[str] = None
    generated_at: Optional[str] = None
