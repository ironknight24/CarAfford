from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import PaginatedResponse
from app.schemas.data_source import DataSourceRead
from app.schemas.location import CitySimple, RtoOfficeSimple, StateSimple


# =============================================================================
# TAX RULE BRACKET SCHEMAS
# =============================================================================

class TaxRuleBracketBase(BaseModel):
    bracket_order: int = Field(default=1, ge=1, description="Ascending execution order of slab")
    minimum_value: Decimal = Field(default=Decimal("0.00"), ge=0, description="Minimum price / CC for slab")
    maximum_value: Optional[Decimal] = Field(None, description="Maximum price / CC for slab, None for unbounded upper limit")
    rate: Optional[Decimal] = Field(None, ge=0, description="Percentage rate for slab (e.g., 14.00 for 14%)")
    fixed_amount: Optional[Decimal] = Field(default=Decimal("0.00"), ge=0, description="Fixed charge for slab")
    calculation_method: str = Field(default="PERCENTAGE", description="PERCENTAGE, FIXED, FORMULA")

    @model_validator(mode="after")
    def validate_bounds(self) -> "TaxRuleBracketBase":
        if self.maximum_value is not None and self.maximum_value <= self.minimum_value:
            raise ValueError(
                f"maximum_value ({self.maximum_value}) must be strictly greater than minimum_value ({self.minimum_value})"
            )
        return self


class TaxRuleBracketCreate(TaxRuleBracketBase):
    pass


class TaxRuleBracketRead(TaxRuleBracketBase):
    id: int
    tax_rule_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# TAX RULE SCHEMAS
# =============================================================================

class TaxRuleBase(BaseModel):
    name: str = Field(..., max_length=150, description="Descriptive name of rule")
    description: Optional[str] = Field(None, max_length=500)
    state_id: int = Field(..., description="Target State ID")
    city_id: Optional[int] = Field(None, description="Optional target City ID")
    rto_id: Optional[int] = Field(None, description="Optional target RTO office ID")

    rule_category: str = Field(default="TAX", description="TAX, REGISTRATION, FEE, CESS")
    tax_type: str = Field(
        ...,
        description="ROAD_TAX, MOTOR_VEHICLE_TAX, REGISTRATION_FEE, SMART_CARD_FEE, HSRP_FEE, HYPOTHECATION_FEE, CESS, SURCHARGE, GREEN_TAX, FASTAG_FEE, OTHER",
    )
    calculation_method: str = Field(
        default="PERCENTAGE",
        description="FIXED, PERCENTAGE, BRACKETED, FORMULA",
    )

    vehicle_type: str = Field(default="CAR", description="CAR, TWO_WHEELER, COMMERCIAL, ANY")
    fuel_type: Optional[str] = Field(None, description="Petrol, Diesel, CNG, Electric, Hybrid, ANY, or None")
    is_ev: Optional[bool] = Field(None, description="EV status constraint")
    usage_type: str = Field(default="PRIVATE", description="PRIVATE, COMMERCIAL, ANY")

    min_price: Optional[Decimal] = Field(None, ge=0)
    max_price: Optional[Decimal] = Field(None, ge=0)
    min_engine_cc: Optional[int] = Field(None, ge=0)
    max_engine_cc: Optional[int] = Field(None, ge=0)
    min_seating_capacity: Optional[int] = Field(None, ge=1)
    max_seating_capacity: Optional[int] = Field(None, ge=1)

    rate: Optional[Decimal] = Field(None, ge=0, description="Percentage rate when calculation_method=PERCENTAGE")
    fixed_amount: Optional[Decimal] = Field(default=Decimal("0.00"), ge=0, description="Fixed charge in INR")
    base_amount_type: str = Field(default="EX_SHOWROOM", description="EX_SHOWROOM, ROAD_TAX, BASE_TAX, FIXED, CUSTOM")

    formula_definition: Optional[Dict[str, Any]] = Field(None, description="Safe structured AST parameter dictionary")
    priority: int = Field(default=100, ge=0, description="Rule resolution priority weight")

    effective_from: datetime = Field(..., description="Start of rule validity period")
    effective_to: Optional[datetime] = Field(None, description="End of rule validity period, None for ongoing")
    active: bool = Field(default=True)

    source_id: Optional[int] = Field(None, description="Provenance DataSource ID")
    source_record_id: Optional[str] = Field(None, max_length=255)
    retrieved_at: Optional[datetime] = None

    @model_validator(mode="after")
    def validate_rule(self) -> "TaxRuleBase":
        if self.effective_to is not None and self.effective_to < self.effective_from:
            raise ValueError(
                f"effective_to ({self.effective_to}) cannot be earlier than effective_from ({self.effective_from})"
            )
        if self.max_price is not None and self.min_price is not None and self.max_price < self.min_price:
            raise ValueError(
                f"max_price ({self.max_price}) cannot be less than min_price ({self.min_price})"
            )
        if self.max_engine_cc is not None and self.min_engine_cc is not None and self.max_engine_cc < self.min_engine_cc:
            raise ValueError(
                f"max_engine_cc ({self.max_engine_cc}) cannot be less than min_engine_cc ({self.min_engine_cc})"
            )
        return self


class TaxRuleCreate(TaxRuleBase):
    brackets: Optional[List[TaxRuleBracketCreate]] = None


class TaxRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    state_id: Optional[int] = None
    city_id: Optional[int] = None
    rto_id: Optional[int] = None
    rule_category: Optional[str] = None
    tax_type: Optional[str] = None
    calculation_method: Optional[str] = None
    vehicle_type: Optional[str] = None
    fuel_type: Optional[str] = None
    is_ev: Optional[bool] = None
    usage_type: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    min_engine_cc: Optional[int] = None
    max_engine_cc: Optional[int] = None
    rate: Optional[Decimal] = None
    fixed_amount: Optional[Decimal] = None
    base_amount_type: Optional[str] = None
    formula_definition: Optional[Dict[str, Any]] = None
    priority: Optional[int] = None
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    active: Optional[bool] = None
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    brackets: Optional[List[TaxRuleBracketCreate]] = None


class TaxRuleRead(TaxRuleBase):
    id: int
    created_at: datetime
    updated_at: datetime
    brackets: List[TaxRuleBracketRead] = []

    model_config = ConfigDict(from_attributes=True)


class TaxRuleDetailRead(TaxRuleRead):
    state: StateSimple
    city: Optional[CitySimple] = None
    rto: Optional[RtoOfficeSimple] = None
    source: Optional[DataSourceRead] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# RULE RESOLUTION SCHEMAS (Clean DTOs for Rule Resolution Service & API)
# =============================================================================

class LocationResolutionContext(BaseModel):
    state_id: int
    state_name: str
    state_code: str
    city_id: Optional[int] = None
    city_name: Optional[str] = None
    rto_id: Optional[int] = None
    rto_code: Optional[str] = None
    rto_name: Optional[str] = None


class VehicleResolutionContext(BaseModel):
    variant_id: Optional[int] = None
    variant_name: Optional[str] = None
    model_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    fuel_type: str
    engine_cc: Optional[int] = None
    ex_showroom_price: Decimal
    is_ev: bool = False
    vehicle_type: str = "CAR"
    usage_type: str = "PRIVATE"


class ResolvedTaxRuleItem(BaseModel):
    rule_id: int
    name: str
    description: Optional[str] = None
    rule_category: str
    tax_type: str
    calculation_method: str
    rate: Optional[Decimal] = None
    fixed_amount: Optional[Decimal] = None
    base_amount_type: str
    brackets: List[TaxRuleBracketRead] = []
    formula_definition: Optional[Dict[str, Any]] = None
    priority: int
    precedence_tier: int = Field(..., description="300=RTO, 200=City, 100=State, 0=Default")
    precedence_label: str = Field(..., description="'RTO-specific', 'City-specific', 'State-level', 'National'")
    effective_from: datetime
    effective_to: Optional[datetime] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None


class TaxRuleResolveResponse(BaseModel):
    location: LocationResolutionContext
    vehicle: VehicleResolutionContext
    calculation_date: datetime
    is_bh_series: bool = False
    is_financed: bool = True
    rules: List[ResolvedTaxRuleItem]
    rules_count: int


class TaxRuleValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []


PaginatedTaxRuleResponse = PaginatedResponse[TaxRuleRead]
