from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from app.core.affordability_constants import AffordabilityProfile, AffordabilityStatus
from app.core.recommendation_constants import (
    DEFAULT_RECOMMENDATION_LIMIT,
    MAX_RECOMMENDATION_LIMIT,
    MIN_RECOMMENDATION_LIMIT,
    RecommendationCategory,
    ScoringWeights,
)
from app.schemas.affordability import AffordabilityBudgetBreakdown, AffordabilityCategory, OwnershipCostBreakdown
from app.schemas.pricing import OnRoadPriceBreakdown


# =============================================================================
# SCORING CONFIG SCHEMAS
# =============================================================================

class ScoringConfigResponse(BaseModel):
    weights: ScoringWeights
    categories: Dict[str, str]
    default_limit: int = DEFAULT_RECOMMENDATION_LIMIT
    max_limit: int = MAX_RECOMMENDATION_LIMIT
    data_status: str = "DEMO"
    disclaimer: str


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class RecommendationRequest(BaseModel):
    # Required Financial Profile
    monthly_take_home_income: Decimal = Field(..., gt=0, description="Net monthly take-home income in INR")
    existing_monthly_emi: Decimal = Field(Decimal("0.00"), ge=0, description="Existing monthly debt obligations in INR")
    available_down_payment: Decimal = Field(Decimal("0.00"), ge=0, description="Available upfront down payment in INR")
    state_id: int = Field(..., description="Target State/UT ID for on-road pricing and taxes")
    city_id: Optional[int] = Field(None, description="Optional target City ID")
    rto_id: Optional[int] = Field(None, description="Optional target RTO ID")
    credit_score: Optional[int] = Field(750, ge=300, le=900, description="CIBIL / Credit Score")
    preferred_loan_tenure_months: Optional[int] = Field(60, ge=12, le=84, description="Preferred loan tenure in months")
    affordability_profile: Optional[AffordabilityProfile] = Field(
        AffordabilityProfile.BALANCED,
        description="Affordability profile heuristic (CONSERVATIVE, BALANCED, STRETCH)",
    )

    # Driving & Energy Preferences
    monthly_driving_distance_km: Optional[Decimal] = Field(None, ge=0, le=20000)
    annual_driving_distance_km: Optional[Decimal] = Field(None, ge=0, le=200000)
    fuel_preference: Optional[str] = Field(None, description="Petrol, Diesel, CNG, Electric, Hybrid")
    
    # Vehicle Spec Preferences
    body_type: Optional[str] = Field(None, description="Hatchback, Sedan, SUV, MUV, etc.")
    transmission: Optional[str] = Field(None, description="Manual, Automatic, AMT, CVT, DCT")
    seating_capacity: Optional[int] = Field(None, ge=2, le=10)
    minimum_safety_rating: Optional[int] = Field(None, ge=1, le=5)
    automatic_required: Optional[bool] = Field(None)
    ev_preferred: Optional[bool] = Field(None)
    manufacturer_id: Optional[int] = Field(None)
    minimum_price: Optional[Decimal] = Field(None, ge=0)
    maximum_price: Optional[Decimal] = Field(None, ge=0)

    # Result limits and targets
    variant_ids: Optional[List[int]] = Field(None, description="Optional target variant IDs to evaluate")
    limit: Optional[int] = Field(DEFAULT_RECOMMENDATION_LIMIT, ge=MIN_RECOMMENDATION_LIMIT, le=MAX_RECOMMENDATION_LIMIT)
    calculation_date: Optional[datetime] = None

    # Backward compatibility aliases
    @model_validator(mode="before")
    @classmethod
    def reconcile_legacy_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Map legacy existing_monthly_emis -> existing_monthly_emi
            if "existing_monthly_emis" in data and "existing_monthly_emi" not in data:
                data["existing_monthly_emi"] = data["existing_monthly_emis"]
            # Map legacy desired_tenure_months -> preferred_loan_tenure_months
            if "desired_tenure_months" in data and "preferred_loan_tenure_months" not in data:
                data["preferred_loan_tenure_months"] = data["desired_tenure_months"]
            # Map legacy cibil_score -> credit_score
            if "cibil_score" in data and "credit_score" not in data:
                data["credit_score"] = data["cibil_score"]
            # Map legacy monthly_commute_km / annual_commute_km
            if "monthly_commute_km" in data and "monthly_driving_distance_km" not in data:
                data["monthly_driving_distance_km"] = data["monthly_commute_km"]
            # Map legacy preferred_fuel_types list to fuel_preference
            if "preferred_fuel_types" in data and data["preferred_fuel_types"] and "fuel_preference" not in data:
                fuels = data["preferred_fuel_types"]
                data["fuel_preference"] = fuels[0] if isinstance(fuels, list) and len(fuels) > 0 else str(fuels)
            # Map legacy preferred_body_types list to body_type
            if "preferred_body_types" in data and data["preferred_body_types"] and "body_type" not in data:
                btypes = data["preferred_body_types"]
                data["body_type"] = btypes[0] if isinstance(btypes, list) and len(btypes) > 0 else str(btypes)
            # Map legacy preferred_transmission list to transmission
            if "preferred_transmission" in data and data["preferred_transmission"] and "transmission" not in data:
                trans = data["preferred_transmission"]
                data["transmission"] = trans[0] if isinstance(trans, list) and len(trans) > 0 else str(trans)
        return data

    @model_validator(mode="after")
    def reconcile_distances(self) -> "RecommendationRequest":
        if self.monthly_driving_distance_km is None and self.annual_driving_distance_km is None:
            self.monthly_driving_distance_km = Decimal("1000.00")
            self.annual_driving_distance_km = Decimal("12000.00")
        elif self.annual_driving_distance_km is not None and self.monthly_driving_distance_km is None:
            self.monthly_driving_distance_km = (self.annual_driving_distance_km / Decimal("12.0")).quantize(Decimal("0.01"))
        elif self.monthly_driving_distance_km is not None and self.annual_driving_distance_km is None:
            self.annual_driving_distance_km = (self.monthly_driving_distance_km * Decimal("12.0")).quantize(Decimal("0.01"))
        return self


class QuickRecommendationRequest(BaseModel):
    monthly_take_home_income: Decimal = Field(..., gt=0)
    existing_monthly_emi: Decimal = Field(Decimal("0.00"), ge=0)
    available_down_payment: Decimal = Field(Decimal("0.00"), ge=0)
    state_id: int
    city_id: Optional[int] = None
    credit_score: Optional[int] = 750
    limit: Optional[int] = 5


class RecommendationCompareRequest(BaseModel):
    variant_ids: List[int] = Field(..., min_length=2, max_length=10)
    monthly_take_home_income: Decimal = Field(..., gt=0)
    existing_monthly_emi: Decimal = Field(Decimal("0.00"), ge=0)
    available_down_payment: Decimal = Field(Decimal("0.00"), ge=0)
    state_id: int
    city_id: Optional[int] = None
    rto_id: Optional[int] = None
    credit_score: Optional[int] = 750
    preferred_loan_tenure_months: Optional[int] = 60
    affordability_profile: Optional[AffordabilityProfile] = AffordabilityProfile.BALANCED
    annual_driving_distance_km: Optional[Decimal] = Decimal("12000.00")


# =============================================================================
# OUTPUT ITEM SCHEMAS
# =============================================================================

class RecommendationVehicleSummary(BaseModel):
    variant_id: int
    variant_name: str
    model_name: str
    model_slug: str
    manufacturer_name: str
    manufacturer_slug: str
    body_type: str
    fuel_type: str
    transmission: str
    seating_capacity: int
    image_url: Optional[str] = None
    arai_mileage_kmpl: Decimal
    safety_rating_stars: Optional[int] = None
    airbags_count: int
    ex_showroom_price: Decimal
    on_road_price: Decimal


class RecommendationAffordabilitySummary(BaseModel):
    status: str
    available_car_emi: Decimal
    estimated_emi: Decimal
    emi_headroom: Decimal
    loan_amount: Decimal
    down_payment: Decimal
    affordability_score: int  # 0 to 100 score


class RecommendationFinancingOption(BaseModel):
    bank_name: str
    product_name: str
    interest_rate: Decimal
    tenure_months: int
    monthly_emi: Decimal
    processing_fee: Decimal
    total_interest: Decimal


class RecommendationTCOSummary(BaseModel):
    annual_fuel_cost: Decimal
    annual_maintenance_cost: Decimal
    five_year_tco: Decimal
    five_year_monthly_average: Decimal
    tco_score: int  # 0 to 100 score


class RecommendedVehicleItem(BaseModel):
    category: str = Field(..., description="BEST_OVERALL, BEST_VALUE, LOWEST_MONTHLY_COST, LOWEST_5_YEAR_TCO, BEST_FIT, STRETCH_OPTIONS")
    rank: int
    score: Decimal = Field(..., description="Composite recommendation score (0 to 100)")
    variant_id: int

    # Structured summaries
    vehicle: RecommendationVehicleSummary
    affordability: RecommendationAffordabilitySummary
    financing: Optional[RecommendationFinancingOption] = None
    tco: RecommendationTCOSummary
    preference_match_score: int = Field(..., description="Preference alignment score (0 to 100)")

    # Explanations & Provenance
    reasons: List[str] = Field(default_factory=list, description="Transparent human-readable reasons for recommendation")
    warnings: List[str] = Field(default_factory=list, description="Financial or data status warnings")

    # Backward-compatibility flat fields for existing frontend cards and legacy tests
    variant_name: str
    model_name: str
    model_slug: str
    manufacturer_name: str
    manufacturer_slug: str
    body_type: str
    fuel_type: str
    transmission: str
    seating_capacity: int
    image_url: Optional[str] = None
    arai_mileage_kmpl: Decimal
    safety_rating_stars: Optional[int] = None
    airbags_count: int
    ex_showroom_price: Decimal
    on_road_price: Decimal
    down_payment_required: Decimal
    loan_amount: Decimal
    estimated_monthly_emi: Decimal
    interest_rate: Decimal
    tenure_months: int
    ownership_cost: OwnershipCostBreakdown
    affordability_score: int
    affordability_category: AffordabilityCategory
    affordability_rationale: str
    on_road_breakdown: Optional[OnRoadPriceBreakdown] = None


class RecommendationResponse(BaseModel):
    user_budget_summary: Any
    recommendations: List[RecommendedVehicleItem] = Field(default_factory=list)
    stretch_options: List[RecommendedVehicleItem] = Field(default_factory=list)

    total_candidates_evaluated: int
    total_affordable_count: int
    total_stretch_count: int
    total_excluded_count: int
    returned_count: int

    data_status: str = "DEMO"
    disclaimer: str

    # Backward compatibility aliases
    @computed_field
    @property
    def recommended_vehicles(self) -> List[RecommendedVehicleItem]:
        return self.recommendations

    @property
    def total_matches_count(self) -> int:
        return self.total_affordable_count

    @property
    def filter_applied_count(self) -> int:
        return self.total_candidates_evaluated


class RecommendationCompareResponse(BaseModel):
    user_budget_summary: Any
    ranked_vehicles: List[RecommendedVehicleItem]
    scoring_weights: ScoringWeights
    comparison_summary: List[str]
    data_status: str = "DEMO"
    disclaimer: str
