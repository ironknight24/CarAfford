from decimal import Decimal
from enum import Enum
from typing import Dict, Any


class AffordabilityProfile(str, Enum):
    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    STRETCH = "STRETCH"


class AffordabilityStatus(str, Enum):
    COMFORTABLE = "COMFORTABLE"
    AFFORDABLE = "AFFORDABLE"
    STRETCH = "STRETCH"
    NOT_AFFORDABLE = "NOT_AFFORDABLE"
    NO_FINANCING_OPTION = "NO_FINANCING_OPTION"


class LimitingFactor(str, Enum):
    EMI_CAP = "EMI_CAP"
    LTV_CAP = "LTV_CAP"
    LOAN_MAXIMUM = "LOAN_MAXIMUM"
    ELIGIBILITY = "ELIGIBILITY"
    DOWN_PAYMENT = "DOWN_PAYMENT"
    NO_ELIGIBLE_LOAN = "NO_ELIGIBLE_LOAN"


# Configurable Affordability Profiles and their respective FOIR and Safe Multiplier thresholds
AFFORDABILITY_PROFILES: Dict[AffordabilityProfile, Dict[str, Any]] = {
    AffordabilityProfile.CONSERVATIVE: {
        "code": AffordabilityProfile.CONSERVATIVE,
        "name": "Conservative",
        "max_foir_ratio": Decimal("0.30"),
        "safe_budget_multiplier": Decimal("0.85"),
        "stretch_budget_multiplier": Decimal("1.00"),
        "description": "Allocates up to 30% of take-home income to total monthly debt payments. Ideal for maximizing savings and minimizing financial stress.",
    },
    AffordabilityProfile.BALANCED: {
        "code": AffordabilityProfile.BALANCED,
        "name": "Balanced",
        "max_foir_ratio": Decimal("0.35"),
        "safe_budget_multiplier": Decimal("0.80"),
        "stretch_budget_multiplier": Decimal("1.10"),
        "description": "Allocates up to 35% of take-home income to total monthly debt payments. Standard benchmark balancing automotive aspirations and everyday living costs.",
    },
    AffordabilityProfile.STRETCH: {
        "code": AffordabilityProfile.STRETCH,
        "name": "Stretch",
        "max_foir_ratio": Decimal("0.40"),
        "safe_budget_multiplier": Decimal("0.75"),
        "stretch_budget_multiplier": Decimal("1.15"),
        "description": "Allocates up to 40% of take-home income to total monthly debt payments. Maximizes purchasing capacity; recommended only with stable emergency reserves.",
    },
}

# Thresholds for classifying specific vehicle affordability
# Headroom ratio = (available_car_emi - required_emi) / available_car_emi
HEADROOM_COMFORTABLE_THRESHOLD = Decimal("0.20")  # >= 20% unused EMI capacity

DISCLAIMER_TEXT = (
    "Estimated financing capacity, EMI, and affordability ranges are calculated using standard Indian personal "
    "finance heuristics and demo/seed banking data. This does NOT constitute a loan pre-approval, credit guarantee, "
    "or formal financial advice from any bank or financial institution."
)

DATA_STATUS_DEMO = "DEMO"
