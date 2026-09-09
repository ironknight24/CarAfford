from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, List
from pydantic import BaseModel


class FuelPriceConfig(BaseModel):
    fuel_type: str
    price_per_unit: Decimal
    unit: str  # "Litre", "kg", "kWh"
    currency: str = "INR"
    effective_from: datetime = datetime(2024, 1, 1, tzinfo=timezone.utc)
    source: str = "Petroleum Planning & Analysis Cell (PPAC) / State Electricity Regulators"
    data_status: str = "DEMO"


class MaintenanceConfig(BaseModel):
    fuel_type: str
    annual_base_cost: Decimal  # Annual scheduled service & fluids
    cost_per_km: Decimal       # Per-km tyre, brake pads, consumables wear
    service_interval_km: int = 10000
    service_interval_months: int = 12
    data_status: str = "DEMO"
    source: str = "Industry Standard Service Cost Benchmark (Automotive Research Association of India & OEM Manuals)"


class InsuranceRenewalConfig(BaseModel):
    """Annual insurance renewal multipliers relative to Year 1 insurance or IDV deprecation."""
    year_2_factor: Decimal = Decimal("0.65")  # OD only (3-Yr TP already covered in Year 1)
    year_3_factor: Decimal = Decimal("0.60")  # OD only
    year_4_factor: Decimal = Decimal("0.75")  # OD + 1-Yr TP Renewal
    year_5_factor: Decimal = Decimal("0.70")  # OD + 1-Yr TP Renewal
    data_status: str = "DEMO"
    source: str = "IRDAI Motor Tariff Guidelines & General Insurance Council"


class DepreciationConfig(BaseModel):
    """Cumulative depreciation schedule on vehicle Ex-Showroom price for economic cost estimation."""
    year_1_depreciation_pct: Decimal = Decimal("15.00")
    year_2_depreciation_pct: Decimal = Decimal("25.00")
    year_3_depreciation_pct: Decimal = Decimal("35.00")
    year_4_depreciation_pct: Decimal = Decimal("43.00")
    year_5_depreciation_pct: Decimal = Decimal("50.00")
    data_status: str = "DEMO"
    source: str = "Federation of Automobile Dealers Associations (FADA) Used Vehicle Valuation Index"


# =============================================================================
# DEFAULT DEMO ASSUMPTIONS
# =============================================================================

DEFAULT_FUEL_PRICES: Dict[str, FuelPriceConfig] = {
    "PETROL": FuelPriceConfig(
        fuel_type="PETROL",
        price_per_unit=Decimal("102.50"),
        unit="Litre",
    ),
    "DIESEL": FuelPriceConfig(
        fuel_type="DIESEL",
        price_per_unit=Decimal("88.50"),
        unit="Litre",
    ),
    "CNG": FuelPriceConfig(
        fuel_type="CNG",
        price_per_unit=Decimal("85.00"),
        unit="kg",
    ),
    "ELECTRIC": FuelPriceConfig(
        fuel_type="ELECTRIC",
        price_per_unit=Decimal("8.50"),  # Blended Home 16A + Commercial DC Fast Charging
        unit="kWh",
    ),
    "HYBRID": FuelPriceConfig(
        fuel_type="HYBRID",
        price_per_unit=Decimal("102.50"),
        unit="Litre",
    ),
}

DEFAULT_MAINTENANCE_RATES: Dict[str, MaintenanceConfig] = {
    "PETROL": MaintenanceConfig(
        fuel_type="PETROL",
        annual_base_cost=Decimal("6000.00"),
        cost_per_km=Decimal("0.40"),
    ),
    "DIESEL": MaintenanceConfig(
        fuel_type="DIESEL",
        annual_base_cost=Decimal("8000.00"),
        cost_per_km=Decimal("0.50"),
    ),
    "CNG": MaintenanceConfig(
        fuel_type="CNG",
        annual_base_cost=Decimal("6500.00"),
        cost_per_km=Decimal("0.45"),
    ),
    "ELECTRIC": MaintenanceConfig(
        fuel_type="ELECTRIC",
        annual_base_cost=Decimal("3500.00"),  # EV has ~45% lower routine maintenance
        cost_per_km=Decimal("0.25"),
    ),
    "HYBRID": MaintenanceConfig(
        fuel_type="HYBRID",
        annual_base_cost=Decimal("7000.00"),
        cost_per_km=Decimal("0.40"),
    ),
}

DEFAULT_INSURANCE_RENEWAL = InsuranceRenewalConfig()
DEFAULT_DEPRECIATION = DepreciationConfig()

# Standard TCO evaluation terms
TCO_PERIODS_CONFIG = {
    "1_year": {"years": 1, "months": 12, "label": "1 Year (12 Months)"},
    "3_years": {"years": 3, "months": 36, "label": "3 Years (36 Months)"},
    "5_years": {"years": 5, "months": 60, "label": "5 Years (60 Months)"},
}

DATA_STATUS_DEMO = "DEMO"

TCO_DISCLAIMER = (
    "Total Cost of Ownership (TCO) figures are estimated financial projections based on user-provided "
    "driving distance, standard Indian automotive benchmarks, demo fuel prices, and empirical depreciation schedules. "
    "Actual costs will vary based on real-world driving style, local fuel tariff changes, dealer maintenance policies, "
    "and prevailing used car market conditions."
)
