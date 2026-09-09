from decimal import Decimal
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class AffordabilityCategory(str, Enum):
    COMFORTABLE = "Comfortable"  # TCO <= 20% of net income
    BALANCED = "Balanced"        # TCO 21% - 30% of net income
    STRETCH = "Stretch"          # TCO 31% - 40% of net income
    RISKY = "Risky"              # TCO > 40% of net income


class OwnershipCostBreakdown(BaseModel):
    monthly_emi: Decimal
    monthly_fuel_cost: Decimal
    monthly_insurance_cost: Decimal
    monthly_maintenance_cost: Decimal
    total_monthly_tco: Decimal
    tco_percentage_of_income: Decimal


class AffordabilityAnalysisRequest(BaseModel):
    monthly_take_home_income: Decimal = Field(gt=0, description="Monthly take-home income in INR")
    existing_monthly_emis: Decimal = Field(default=Decimal("0.00"), ge=0, description="Existing EMIs")
    available_down_payment: Decimal = Field(ge=0, description="Cash available for down payment in INR")
    state_id: int = Field(description="State ID for on-road pricing")
    city_id: Optional[int] = Field(default=None, description="City ID")
    desired_tenure_months: int = Field(default=60, ge=12, le=84, description="Desired loan tenure in months")
    cibil_score: Optional[int] = Field(default=750, ge=300, le=900)
    monthly_commute_km: Optional[int] = Field(default=1000, ge=100, le=10000, description="Expected monthly driving in km")
    preferred_body_types: Optional[List[str]] = None
    preferred_fuel_types: Optional[List[str]] = None
    preferred_transmission: Optional[List[str]] = None
    min_seating: Optional[int] = None
    min_safety_rating: Optional[int] = None


class AffordabilityBudgetSummary(BaseModel):
    monthly_take_home_income: Decimal
    existing_monthly_emis: Decimal
    max_total_emi_allowed: Decimal
    available_car_emi_budget: Decimal
    available_down_payment: Decimal
    max_affordable_loan: Decimal
    max_affordable_on_road_price: Decimal
    recommended_on_road_budget: Decimal  # Safe comfortable budget (typically 20% lower than max limit)
    estimated_interest_rate: Decimal
    tenure_months: int
    cibil_score: int
    foir_used_percent: Decimal
