from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import AuditSchemaMixin


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
    tcs_amount: Decimal  # 1% if ex-showroom > 10L

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
