from decimal import Decimal
from enum import Enum
from typing import Dict
from pydantic import BaseModel


class RecommendationCategory(str, Enum):
    BEST_OVERALL = "BEST_OVERALL"
    BEST_VALUE = "BEST_VALUE"
    LOWEST_MONTHLY_COST = "LOWEST_MONTHLY_COST"
    LOWEST_5_YEAR_TCO = "LOWEST_5_YEAR_TCO"
    BEST_FIT = "BEST_FIT"
    STRETCH_OPTIONS = "STRETCH_OPTIONS"


class ScoringWeights(BaseModel):
    affordability_weight: Decimal = Decimal("0.30")       # 30%
    tco_weight: Decimal = Decimal("0.25")                 # 25%
    preference_match_weight: Decimal = Decimal("0.20")    # 20%
    monthly_cost_weight: Decimal = Decimal("0.15")        # 15%
    vehicle_value_weight: Decimal = Decimal("0.10")       # 10%


DEFAULT_SCORING_WEIGHTS = ScoringWeights()

DEFAULT_RECOMMENDATION_LIMIT = 5
MAX_RECOMMENDATION_LIMIT = 20
MIN_RECOMMENDATION_LIMIT = 1

CATEGORY_DESCRIPTIONS: Dict[str, str] = {
    RecommendationCategory.BEST_OVERALL.value: "Highest composite score across affordability, ownership cost, and vehicle specs.",
    RecommendationCategory.BEST_VALUE.value: "Exceptional price-to-feature value with comfortable financial headroom.",
    RecommendationCategory.LOWEST_MONTHLY_COST.value: "Lowest monthly recurring expense (EMI + Fuel).",
    RecommendationCategory.LOWEST_5_YEAR_TCO.value: "Lowest 5-year total cash outflow and operating cost.",
    RecommendationCategory.BEST_FIT.value: "Closest alignment with your fuel, transmission, body type, and seating preferences.",
    RecommendationCategory.STRETCH_OPTIONS.value: "Vehicles exceeding balanced budget but within your configured stretch capacity.",
}

DATA_STATUS_DEMO = "DEMO"

RECOMMENDATION_DISCLAIMER = (
    "Recommendations are algorithmic suggestions generated using Indian automotive benchmarks, demo bank interest rates, "
    "and location-specific on-road tax rules. They do not constitute formal credit sanctions or dealer price guarantees. "
    "Actual dealer discounts, insurance quotes, and bank underwriting decisions may vary."
)
