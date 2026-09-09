from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import AuditSchemaMixin
from app.schemas.tax_rule import LocationResolutionContext, VehicleResolutionContext


# =============================================================================
# VEHICLE PRICE SCHEMAS
# =============================================================================

class VehiclePriceCreate(BaseModel):
    variant_id: int
    ex_showroom_price: Decimal = Field(..., gt=0, description="Ex-showroom price in INR")
    price_type: str = Field(default="EX_SHOWROOM", description="Price type (EX_SHOWROOM, INTRODUCTORY, PROMOTIONAL, OTHER)")
    effective_from: datetime = Field(..., description="Timestamp from which price is effective")
    effective_to: Optional[datetime] = Field(default=None, description="Timestamp until price is effective (NULL for active)")
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class VehiclePriceRead(BaseModel):
    id: int
    variant_id: int
    ex_showroom_price: Decimal
    price_type: str
    effective_from: datetime
    effective_to: Optional[datetime] = None
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ExShowroomPriceRead(AuditSchemaMixin):
    id: int
    variant_id: int
    state_id: Optional[int] = None
    city_id: Optional[int] = None
    price_inr: Decimal
    is_current: bool

    model_config = ConfigDict(from_attributes=True)


class PriceHistoryRead(BaseModel):
    id: int
    variant_id: int
    state_id: Optional[int] = None
    price_inr: Decimal
    recorded_at: str
    change_reason: Optional[str] = None
    source: Optional[str] = None
    source_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# ON-ROAD PRICING CALCULATION SCHEMAS
# =============================================================================

class OnRoadPriceCalculationRequest(BaseModel):
    variant_id: int = Field(..., description="Vehicle Variant ID")
    country_id: Optional[int] = Field(None, description="Country ID (defaults to India / resolved via state)")
    state_id: int = Field(..., description="Target State/UT ID")
    city_id: Optional[int] = Field(None, description="Optional target City ID")
    rto_id: Optional[int] = Field(None, description="Optional target RTO Office ID")
    calculation_date: Optional[datetime] = Field(None, description="Target date for historical/current calculation")
    insurance_option: str = Field(
        default="DEFAULT_ESTIMATE",
        description="Insurance calculation method: DEFAULT_ESTIMATE, USER_PROVIDED, ZERO_DEP, THIRD_PARTY_ONLY",
    )
    insurance_amount: Optional[Decimal] = Field(None, ge=0, description="User-supplied insurance quote in INR")
    is_bh_series: bool = Field(default=False, description="Whether to calculate Bharat (BH) Series road tax")
    is_financed: bool = Field(default=True, description="Whether vehicle is hypothecated under bank finance")


class PriceBreakdownItem(BaseModel):
    component: str = Field(
        ...,
        description="EX_SHOWROOM, ROAD_TAX, CESS, REGISTRATION_FEE, SMART_CARD_FEE, HSRP_FEE, HYPOTHECATION_FEE, FASTAG_FEE, GREEN_TAX, SURCHARGE, TCS, INSURANCE, OTHER",
    )
    tax_rule_id: Optional[int] = Field(None, description="Resolved TaxRule ID if statutory")
    rule_name: str = Field(..., description="Descriptive component or statutory rule name")
    calculation_method: str = Field(
        ...,
        description="BASE_PRICE, FIXED, PERCENTAGE, BRACKETED, FORMULA, ESTIMATE, USER_OVERRIDE",
    )
    base_amount: Optional[Decimal] = Field(None, description="Base amount in INR on which percentage/bracket was computed")
    rate: Optional[Decimal] = Field(None, description="Applied percentage or multiplier rate")
    fixed_amount: Optional[Decimal] = Field(None, description="Fixed statutory charge in INR")
    calculated_amount: Decimal = Field(..., description="Final computed line item amount in INR")
    source: Optional[str] = Field(None, description="Authoritative data source or gazette authority")
    source_url: Optional[str] = Field(None, description="Public verification URL")
    effective_from: Optional[datetime] = Field(None, description="Rule effective start date")
    effective_to: Optional[datetime] = Field(None, description="Rule effective end date")
    explanation: str = Field(..., description="Transparent textual explanation of derivation")
    is_estimated: bool = Field(default=False, description="True if value is an algorithmic estimate rather than exact statutory charge")
    status: str = Field(
        default="APPLIED",
        description="APPLIED, ZERO_CHARGE, NOT_APPLICABLE, USER_OVERRIDDEN",
    )


class OnRoadPriceTotals(BaseModel):
    ex_showroom_price: Decimal
    total_statutory_taxes: Decimal
    total_registration_and_fees: Decimal
    total_insurance: Decimal
    total_other_charges: Decimal
    on_road_price: Decimal


class DataQualityInfo(BaseModel):
    is_estimated: bool = True
    has_demo_rules: bool = True
    data_status: str = Field(default="DEMO", description="'DEMO' or 'AUTHORITATIVE'")
    sources: List[str] = []
    disclaimer: str = "Estimated vehicle on-road pricing computed using demonstration statutory tax & registration rules. Actual dealer invoices and RTO receipts may vary."


class OnRoadPriceResponse(BaseModel):
    vehicle: VehicleResolutionContext
    location: LocationResolutionContext
    calculation_date: datetime
    is_bh_series: bool = False
    is_financed: bool = True
    insurance_option: str = "DEFAULT_ESTIMATE"
    breakdown: List[PriceBreakdownItem]
    totals: OnRoadPriceTotals
    data_quality: DataQualityInfo


# =============================================================================
# BACKWARD-COMPATIBILITY ALIASES
# =============================================================================

class OnRoadPriceRequest(BaseModel):
    variant_id: int
    state_id: int
    city_id: Optional[int] = None
    is_bh_series: bool = False
    include_zero_dep_insurance: bool = True
    is_financed: bool = True


class OnRoadPriceBreakdown(BaseModel):
    variant_id: int
    variant_name: str
    model_name: str
    manufacturer_name: str
    state_id: int
    state_name: str
    city_name: Optional[str] = None

    # Line item pricing components
    ex_showroom_price: Decimal
    rto_road_tax: Decimal
    rto_road_tax_percent: Decimal
    rto_cess: Decimal
    registration_charges: Decimal
    fastag_charges: Decimal
    green_cess: Decimal
    hypothecation_charges: Decimal
    tcs_amount: Decimal

    # Insurance breakdown
    insurance_estimated_idv: Decimal
    insurance_third_party_3yr: Decimal
    insurance_own_damage_1yr: Decimal
    insurance_zero_dep_addon: Decimal
    insurance_total: Decimal

    # Grand total
    on_road_price: Decimal

    # Metadata / audit
    is_bh_series: bool
    calculated_at: str
