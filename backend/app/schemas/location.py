from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.common import AuditSchemaMixin


class StateBase(BaseModel):
    name: str
    code: str
    is_ut: bool = False


class StateRead(StateBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class CityBase(BaseModel):
    name: str
    slug: str
    state_id: int
    tier: str = "Tier 1"


class CityRead(CityBase):
    id: int
    model_config = ConfigDict(from_attributes=True)


class RtoOfficeRead(BaseModel):
    id: int
    code: str
    name: str
    state_id: int
    city_id: Optional[int] = None
    model_config = ConfigDict(from_attributes=True)


class TaxSlabRead(AuditSchemaMixin):
    id: int
    state_id: int
    fuel_type: str
    min_ex_showroom: Decimal
    max_ex_showroom: Optional[Decimal] = None
    tax_percent: Decimal
    cess_percent: Decimal
    flat_registration_fee: Decimal
    fastag_fee: Decimal
    green_cess_amount: Decimal
    is_bh_series: bool

    model_config = ConfigDict(from_attributes=True)
