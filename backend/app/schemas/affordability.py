from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from enum import Enum
from app.core.affordability_constants import (
    AffordabilityProfile,
    AffordabilityStatus,
    LimitingFactor,
    DATA_STATUS_DEMO,
    DISCLAIMER_TEXT,
)
from app.schemas.finance import LoanOfferItem


# Backward compatibility for existing schemas/scoring
class AffordabilityCategory(str, Enum):
    COMFORTABLE = "Comfortable"
    BALANCED = "Balanced"
    STRETCH = "Stretch"
    RISKY = "Risky"


class OwnershipCostBreakdown(BaseModel):
    monthly_emi: Decimal
    monthly_fuel_cost: Decimal
    monthly_insurance_cost: Decimal
    monthly_maintenance_cost: Decimal
    total_monthly_tco: Decimal
    tco_percentage_of_income: Decimal


# Core Affordability Domain Schemas
class AffordabilityCalculateRequest(BaseModel):
    monthly_take_home_income: Decimal = Field(
        ..., gt=0, description="Monthly net take-home salary in INR"
    )
    existing_monthly_emi: Decimal = Field(
        default=Decimal("0.00"), ge=0, description="Total existing monthly debt obligations in INR"
    )
    available_down_payment: Decimal = Field(
        default=Decimal("0.00"), ge=0, description="Available upfront cash for down payment in INR"
    )
    state_id: int = Field(..., description="Target registration State ID")
    city_id: Optional[int] = Field(default=None, description="Optional City ID within the State")
    rto_id: Optional[int] = Field(default=None, description="Optional RTO ID within the City/State")
    credit_score: int = Field(
        default=750, ge=300, le=900, description="CIBIL / Experian credit score (300-900)"
    )
    preferred_loan_tenure_months: int = Field(
        default=60, ge=12, le=84, description="Desired car loan tenure in months (12-84)"
    )
    affordability_profile: AffordabilityProfile = Field(
        default=AffordabilityProfile.BALANCED,
        description="Affordability risk profile: CONSERVATIVE (30%), BALANCED (35%), or STRETCH (40%)",
    )
    # Optional preference and filter fields
    employment_type: Optional[str] = Field(
        default="SALARIED", description="Employment type (SALARIED, SELF_EMPLOYED)"
    )
    monthly_driving_distance: Optional[int] = Field(
        default=1000, ge=0, description="Estimated monthly driving in km"
    )
    fuel_preference: Optional[str] = Field(
        default=None, description="Preferred fuel type (PETROL, DIESEL, ELECTRIC, CNG)"
    )
    body_type: Optional[str] = Field(
        default=None, description="Preferred body type (SUV, SEDAN, HATCHBACK)"
    )
    transmission: Optional[str] = Field(
        default=None, description="Preferred transmission (MANUAL, AUTOMATIC)"
    )
    preferred_body_types: Optional[List[str]] = None
    preferred_fuel_types: Optional[List[str]] = None
    preferred_transmission: Optional[List[str]] = None
    min_seating: Optional[int] = None
    min_safety_rating: Optional[int] = None

    # Backward compatibility aliases
    model_config = ConfigDict(populate_by_name=True)

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "existing_monthly_emis" in data and "existing_monthly_emi" not in data:
                data["existing_monthly_emi"] = data["existing_monthly_emis"]
            if "desired_tenure_months" in data and "preferred_loan_tenure_months" not in data:
                data["preferred_loan_tenure_months"] = data["desired_tenure_months"]
            if "cibil_score" in data and "credit_score" not in data:
                data["credit_score"] = data["cibil_score"]
            if "monthly_commute_km" in data and "monthly_driving_distance" not in data:
                data["monthly_driving_distance"] = data["monthly_commute_km"]
        return data

    @property
    def existing_monthly_emis(self) -> Decimal:
        return self.existing_monthly_emi

    @property
    def desired_tenure_months(self) -> int:
        return self.preferred_loan_tenure_months

    @property
    def cibil_score(self) -> int:
        return self.credit_score

    @property
    def monthly_commute_km(self) -> Optional[int]:
        return self.monthly_driving_distance


class AffordabilityFinancingAssumption(BaseModel):
    bank_id: Optional[int] = None
    bank_name: Optional[str] = None
    loan_product_id: Optional[int] = None
    loan_product_name: Optional[str] = None
    interest_rate: Decimal
    tenure_months: int
    product_max_ltv_percent: Decimal
    product_max_loan_amount: Optional[Decimal] = None
    estimated_processing_fee: Decimal = Decimal("0.00")


class AffordabilityBudgetBreakdown(BaseModel):
    affordability_profile: AffordabilityProfile
    monthly_take_home_income: Decimal
    existing_monthly_emi: Decimal
    maximum_total_emi: Decimal
    available_car_emi: Decimal
    available_down_payment: Decimal
    maximum_affordable_loan: Decimal
    maximum_affordable_on_road_price: Decimal
    recommended_safe_budget: Decimal
    stretch_budget: Decimal
    limiting_factor: LimitingFactor
    limiting_factor_reason: str
    applicable_financing_assumptions: AffordabilityFinancingAssumption
    data_status: str = DATA_STATUS_DEMO
    warnings: List[str] = []
    disclaimer: str = DISCLAIMER_TEXT

    # Backward compatibility properties
    @computed_field
    @property
    def max_affordable_loan(self) -> Decimal:
        return self.maximum_affordable_loan

    @computed_field
    @property
    def max_affordable_on_road_price(self) -> Decimal:
        return self.maximum_affordable_on_road_price

    @computed_field
    @property
    def recommended_on_road_budget(self) -> Decimal:
        return self.recommended_safe_budget

    @computed_field
    @property
    def available_car_emi_budget(self) -> Decimal:
        return self.available_car_emi

    @computed_field
    @property
    def max_total_emi_allowed(self) -> Decimal:
        return self.maximum_total_emi


class AffordabilityProfileInfo(BaseModel):
    code: AffordabilityProfile
    name: str
    max_foir_ratio: Decimal
    max_foir_percent: Decimal
    safe_budget_multiplier: Decimal
    stretch_budget_multiplier: Decimal
    description: str


class VehicleAffordabilityRequest(BaseModel):
    variant_id: int = Field(..., description="Vehicle variant ID to evaluate")
    monthly_take_home_income: Decimal = Field(
        ..., gt=0, description="Monthly net take-home salary in INR"
    )
    existing_monthly_emi: Decimal = Field(
        default=Decimal("0.00"), ge=0, description="Total existing monthly EMIs"
    )
    available_down_payment: Decimal = Field(
        default=Decimal("0.00"), ge=0, description="Available down payment in INR"
    )
    state_id: int = Field(..., description="Target registration State ID")
    city_id: Optional[int] = Field(default=None, description="Optional City ID")
    rto_id: Optional[int] = Field(default=None, description="Optional RTO ID")
    credit_score: int = Field(default=750, ge=300, le=900, description="Credit score (300-900)")
    preferred_loan_tenure_months: int = Field(
        default=60, ge=12, le=84, description="Tenure in months"
    )
    affordability_profile: AffordabilityProfile = Field(
        default=AffordabilityProfile.BALANCED,
        description="Affordability profile (CONSERVATIVE, BALANCED, STRETCH)",
    )
    down_payment_override: Optional[Decimal] = Field(
        default=None, ge=0, description="Optional specific down payment for this vehicle"
    )


class VehicleAffordabilityResponse(BaseModel):
    variant_id: int
    variant_name: str
    model_name: str
    manufacturer_name: str
    fuel_type: str
    transmission: str
    ex_showroom_price: Decimal
    on_road_price: Decimal
    down_payment: Decimal
    required_loan: Decimal
    estimated_emi: Decimal
    available_car_emi: Decimal
    emi_headroom: Decimal
    affordable: bool
    affordability_status: AffordabilityStatus
    affordability_rationale: str
    limiting_factor: Optional[LimitingFactor] = None
    selected_loan_offer: Optional[LoanOfferItem] = None
    all_eligible_loan_offers: List[LoanOfferItem] = []
    data_status: str = DATA_STATUS_DEMO
    disclaimer: str = DISCLAIMER_TEXT


class MultiVehicleAffordabilityRequest(BaseModel):
    variant_ids: List[int] = Field(
        ..., min_length=1, max_length=20, description="List of variant IDs to evaluate"
    )
    monthly_take_home_income: Decimal = Field(..., gt=0)
    existing_monthly_emi: Decimal = Field(default=Decimal("0.00"), ge=0)
    available_down_payment: Decimal = Field(default=Decimal("0.00"), ge=0)
    state_id: int
    city_id: Optional[int] = None
    rto_id: Optional[int] = None
    credit_score: int = Field(default=750, ge=300, le=900)
    preferred_loan_tenure_months: int = Field(default=60, ge=12, le=84)
    affordability_profile: AffordabilityProfile = AffordabilityProfile.BALANCED


class MultiVehicleAffordabilityResponse(BaseModel):
    results: List[VehicleAffordabilityResponse]
    total_evaluated: int
    affordable_count: int
    stretch_count: int
    unaffordable_count: int
    data_status: str = DATA_STATUS_DEMO
    disclaimer: str = DISCLAIMER_TEXT


class AffordabilityComparisonRequest(BaseModel):
    variant_ids: List[int] = Field(
        ..., min_length=2, max_length=5, description="2 to 5 variant IDs to compare"
    )
    monthly_take_home_income: Decimal = Field(..., gt=0)
    existing_monthly_emi: Decimal = Field(default=Decimal("0.00"), ge=0)
    available_down_payment: Decimal = Field(default=Decimal("0.00"), ge=0)
    state_id: int
    city_id: Optional[int] = None
    rto_id: Optional[int] = None
    credit_score: int = Field(default=750, ge=300, le=900)
    preferred_loan_tenure_months: int = Field(default=60, ge=12, le=84)
    affordability_profile: AffordabilityProfile = AffordabilityProfile.BALANCED


class AffordabilityComparisonResponse(BaseModel):
    user_budget_summary: AffordabilityBudgetBreakdown
    vehicles: List[VehicleAffordabilityResponse]
    comparison_notes: List[str]
    data_status: str = DATA_STATUS_DEMO
    disclaimer: str = DISCLAIMER_TEXT


# Legacy Budget Summary schema for backwards compatibility
class AffordabilityBudgetSummary(BaseModel):
    monthly_take_home_income: Decimal
    existing_monthly_emis: Decimal
    max_total_emi_allowed: Decimal
    available_car_emi_budget: Decimal
    available_down_payment: Decimal
    max_affordable_loan: Decimal
    max_affordable_on_road_price: Decimal
    recommended_on_road_budget: Decimal
    estimated_interest_rate: Decimal
    tenure_months: int
    cibil_score: int
    foir_used_percent: Decimal


# Backward compatibility aliases
AffordabilityAnalysisRequest = AffordabilityCalculateRequest
