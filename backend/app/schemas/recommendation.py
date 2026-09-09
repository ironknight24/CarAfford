from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel
from app.schemas.affordability import (
    AffordabilityBudgetSummary,
    AffordabilityCategory,
    OwnershipCostBreakdown,
)
from app.schemas.pricing import OnRoadPriceBreakdown


class RecommendedVehicleItem(BaseModel):
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

    # Financial breakdown
    ex_showroom_price: Decimal
    on_road_price: Decimal
    down_payment_required: Decimal
    loan_amount: Decimal
    estimated_monthly_emi: Decimal
    interest_rate: Decimal
    tenure_months: int

    # TCO & Affordability
    ownership_cost: OwnershipCostBreakdown
    affordability_score: int  # 0 to 100 score (higher is safer/better fit)
    affordability_category: AffordabilityCategory
    affordability_rationale: str

    on_road_breakdown: Optional[OnRoadPriceBreakdown] = None


class RecommendationResponse(BaseModel):
    user_budget_summary: AffordabilityBudgetSummary
    recommended_vehicles: List[RecommendedVehicleItem]
    total_matches_count: int
    filter_applied_count: int
