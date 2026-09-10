from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import AuditSchemaMixin


# ==========================================
# Country Schemas
# ==========================================
class CountryBase(BaseModel):
    name: str = Field(..., max_length=100, description="Country official name (e.g., India)")
    iso_code: str = Field(
        ..., min_length=2, max_length=2, description="2-letter ISO 3166-1 alpha-2 code (e.g., IN)"
    )
    iso3_code: str = Field(
        ..., min_length=3, max_length=3, description="3-letter ISO 3166-1 alpha-3 code (e.g., IND)"
    )
    active: bool = Field(default=True, description="Whether country is active for vehicle pricing")


class CountryCreate(CountryBase):
    pass


class CountrySimple(BaseModel):
    id: int
    name: str
    iso_code: str
    iso3_code: str
    active: bool

    model_config = ConfigDict(from_attributes=True)


class CountryRead(CountryBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# State / Administrative Region Schemas
# ==========================================
class StateBase(BaseModel):
    country_id: int = Field(default=1, description="Country identifier")
    name: str = Field(..., max_length=100, description="State/UT name (e.g., Karnataka, Delhi)")
    code: str = Field(..., max_length=10, description="State abbreviation/code (e.g., KA, DL, MH)")
    region_type: str = Field(
        default="STATE", description="Administrative region type: STATE or UNION_TERRITORY"
    )
    active: bool = Field(default=True, description="Whether state/UT is active")
    source_id: Optional[int] = Field(default=None, description="Provenance data source identifier")
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class StateCreate(StateBase):
    pass


class StateSimple(BaseModel):
    id: int
    country_id: int
    name: str
    code: str
    region_type: str
    active: bool
    is_ut: bool

    model_config = ConfigDict(from_attributes=True)


class StateRead(BaseModel):
    id: int
    country_id: int
    name: str
    code: str
    region_type: str
    active: bool
    is_ut: bool
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    country: Optional[CountrySimple] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# City Schemas
# ==========================================
class CityBase(BaseModel):
    state_id: int = Field(..., description="State identifier")
    name: str = Field(
        ..., max_length=100, description="City official name (e.g., Bengaluru, Mumbai)"
    )
    slug: str = Field(..., max_length=100, description="Unique slug (e.g., bengaluru, mumbai)")
    tier: str = Field(
        default="Tier 1", max_length=10, description="City classification (Tier 1, Tier 2, Tier 3)"
    )
    active: bool = Field(default=True, description="Whether city is active")
    source_id: Optional[int] = Field(default=None, description="Provenance data source identifier")
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class CityCreate(CityBase):
    pass


class CitySimple(BaseModel):
    id: int
    state_id: int
    name: str
    slug: str
    tier: str
    active: bool

    model_config = ConfigDict(from_attributes=True)


class CityRead(BaseModel):
    id: int
    state_id: int
    name: str
    slug: str
    tier: str
    active: bool
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    state: Optional[StateSimple] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# RTO (Regional Transport Office) Schemas
# ==========================================
class RtoOfficeBase(BaseModel):
    state_id: int = Field(..., description="State identifier")
    city_id: Optional[int] = Field(default=None, description="Optional city identifier")
    code: str = Field(
        ..., max_length=20, description="RTO registration series code (e.g., KA-01, MH-01, DL-01)"
    )
    name: str = Field(..., max_length=150, description="RTO official name / office designation")
    jurisdiction: Optional[str] = Field(
        default=None, max_length=255, description="Jurisdiction area / boundaries"
    )
    active: bool = Field(default=True, description="Whether RTO office is active")
    source_id: Optional[int] = Field(default=None, description="Provenance data source identifier")
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class RtoOfficeCreate(RtoOfficeBase):
    pass


class RtoOfficeSimple(BaseModel):
    id: int
    state_id: int
    city_id: Optional[int] = None
    code: str
    name: str
    jurisdiction: Optional[str] = None
    active: bool

    model_config = ConfigDict(from_attributes=True)


class RtoOfficeRead(BaseModel):
    id: int
    state_id: int
    city_id: Optional[int] = None
    code: str
    name: str
    jurisdiction: Optional[str] = None
    active: bool
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    state: Optional[StateSimple] = None
    city: Optional[CitySimple] = None

    model_config = ConfigDict(from_attributes=True)


RtoOfficeDetailRead = RtoOfficeRead
RTORead = RtoOfficeRead


# ==========================================
# Hierarchical / Detail Schemas
# ==========================================
class CityDetailRead(CityRead):
    rtos: List[RtoOfficeSimple] = []


class StateDetailRead(StateRead):
    cities_count: int = 0
    rtos_count: int = 0
    cities: List[CitySimple] = []
    rtos: List[RtoOfficeSimple] = []


class CountryDetailRead(CountryRead):
    states_count: int = 0
    states: List[StateSimple] = []


# ==========================================
# Location Search Schemas
# ==========================================
class LocationSearchItem(BaseModel):
    country_id: int
    country_name: str
    country_iso: str
    state_id: int
    state_name: str
    state_code: str
    region_type: str
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    city_slug: Optional[str] = None
    rto_id: Optional[int] = None
    rto_code: Optional[str] = None
    rto_name: Optional[str] = None
    rto_jurisdiction: Optional[str] = None
    match_type: str  # "rto", "city", "state", "country"
    active: bool

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Tax Slab Schema
# ==========================================
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
