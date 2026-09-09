from enum import Enum
from typing import Dict, Any
from decimal import Decimal


class DataSourceType(str, Enum):
    OFFICIAL_GOVERNMENT = "OFFICIAL_GOVERNMENT"
    OFFICIAL_MANUFACTURER = "OFFICIAL_MANUFACTURER"
    OFFICIAL_BANK = "OFFICIAL_BANK"
    LICENSED_COMMERCIAL = "LICENSED_COMMERCIAL"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    DEMO_SEED = "DEMO_SEED"
    OTHER = "OTHER"


class IngestionRunStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class VerificationStatus(str, Enum):
    DEMO = "DEMO"
    UNVERIFIED = "UNVERIFIED"
    PENDING_REVIEW = "PENDING_REVIEW"
    VERIFIED = "VERIFIED"
    EXPIRED = "EXPIRED"
    REJECTED = "REJECTED"


class DataFreshnessStatus(str, Enum):
    CURRENT = "CURRENT"
    STALE = "STALE"
    EXPIRED = "EXPIRED"
    UNKNOWN = "UNKNOWN"


class ConflictStatus(str, Enum):
    UNRESOLVED = "UNRESOLVED"
    RESOLVED = "RESOLVED"
    IGNORED = "IGNORED"


class IngestionEntityType(str, Enum):
    VEHICLE = "VEHICLE"
    VEHICLE_PRICE = "VEHICLE_PRICE"
    TAX_RULE = "TAX_RULE"
    BANK_RATE = "BANK_RATE"
    LOAN_FEE = "LOAN_FEE"
    LOCATION = "LOCATION"
    TCO_ASSUMPTION = "TCO_ASSUMPTION"


# Freshness SLA Policies in Days
DATASET_FRESHNESS_SLA_DAYS: Dict[str, int] = {
    "bank_rates": 7,          # Banking interest rates change weekly/monthly
    "vehicle_prices": 30,     # Ex-showroom prices update monthly/quarterly
    "tax_rules": 180,         # RTO/State budgets update semiannually/annually
    "vehicle_specs": 365,     # Vehicle technical specs are stable per model year
    "locations": 365,         # States/Cities/RTOs are structurally stable
    "tco_assumptions": 30,    # Fuel and maintenance benchmarks
}

# Trust level defaults (0 to 100)
DATA_SOURCE_DEFAULT_TRUST_LEVELS: Dict[DataSourceType, int] = {
    DataSourceType.OFFICIAL_GOVERNMENT: 100,
    DataSourceType.OFFICIAL_MANUFACTURER: 95,
    DataSourceType.OFFICIAL_BANK: 95,
    DataSourceType.LICENSED_COMMERCIAL: 85,
    DataSourceType.MANUAL_REVIEW: 90,
    DataSourceType.DEMO_SEED: 70,
    DataSourceType.OTHER: 50,
}

# Data quality scoring dimension weights
DATA_QUALITY_WEIGHTS = {
    "source_trust": Decimal("0.35"),
    "freshness": Decimal("0.25"),
    "completeness": Decimal("0.20"),
    "validation": Decimal("0.20"),
}

INGESTION_DISCLAIMER = (
    "CarAfford ingestion and provenance framework verifies authenticity, tracks historical "
    "effective date ranges, and classifies trust level across government, OEM, and banking datasets."
)
