from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

# =============================================================================
# ASSUMPTION SCHEMAS
# =============================================================================


class FuelPriceAssumption(BaseModel):
    fuel_type: str
    price_per_unit: Decimal
    unit: str  # "Litre", "kg", "kWh"
    currency: str = "INR"
    effective_from: datetime
    source: str
    verification_status: str = "DEMO"
    data_status: str = "DEMO"
    state_code: Optional[str] = None
    city_name: Optional[str] = None


class ElectricityTariffAssumption(BaseModel):
    tariff_type: str
    rate_per_kwh: Decimal
    fixed_charge_per_month: Optional[Decimal] = None
    discom_name: Optional[str] = None
    currency: str = "INR"
    effective_from: datetime
    source: str
    verification_status: str = "DEMO"
    data_status: str = "DEMO"


class MaintenanceAssumption(BaseModel):
    fuel_type: str
    annual_base_cost: Decimal
    cost_per_km: Decimal
    service_interval_km: int = 10000
    service_interval_months: int = 12
    source: str
    verification_status: str = "DEMO"
    data_status: str = "DEMO"


class InsuranceAssumption(BaseModel):
    year_2_factor: Decimal
    year_3_factor: Decimal
    year_4_factor: Decimal
    year_5_factor: Decimal
    source: str
    verification_status: str = "DEMO"
    data_status: str = "DEMO"


class DepreciationAssumption(BaseModel):
    year_1_depreciation_pct: Decimal
    year_2_depreciation_pct: Decimal
    year_3_depreciation_pct: Decimal
    year_4_depreciation_pct: Decimal
    year_5_depreciation_pct: Decimal
    methodology: str = "EMPIRICAL_MARKET_RESALE"
    source: str
    verification_status: str = "DEMO"
    data_status: str = "DEMO"


class TCOAssumptionsResponse(BaseModel):
    fuel_prices: Dict[str, FuelPriceAssumption]
    electricity_tariffs: Optional[Dict[str, ElectricityTariffAssumption]] = None
    maintenance_rates: Dict[str, MaintenanceAssumption]
    insurance_renewal: InsuranceAssumption
    depreciation: DepreciationAssumption
    data_status: str = "DEMO"
    disclaimer: str


# =============================================================================
# CALCULATION REQUEST SCHEMAS
# =============================================================================


class TCOCalculationRequest(BaseModel):
    variant_id: Optional[int] = Field(None, description="Vehicle Variant ID")
    state_id: int = Field(..., description="Target State/UT ID for on-road pricing and taxes")
    city_id: Optional[int] = Field(None, description="Optional target City ID")
    rto_id: Optional[int] = Field(None, description="Optional target RTO ID")

    # Driving distance (either monthly or annual)
    monthly_driving_distance_km: Optional[Decimal] = Field(
        None, ge=0, le=20000, description="Monthly driving distance in km"
    )
    annual_driving_distance_km: Optional[Decimal] = Field(
        None, ge=0, le=200000, description="Annual driving distance in km"
    )

    # Financing & Down payment
    down_payment: Optional[Decimal] = Field(
        None, ge=0, description="Available upfront down payment in INR"
    )
    credit_score: Optional[int] = Field(750, ge=300, le=900, description="CIBIL / Credit Score")
    preferred_loan_tenure_months: Optional[int] = Field(
        60, ge=12, le=84, description="Preferred loan tenure in months"
    )
    is_financed: bool = Field(True, description="Whether the purchase is financed via an auto loan")

    # Optional manual overrides / generic calculation inputs
    fuel_type: Optional[str] = Field(None, description="Petrol, Diesel, CNG, Electric, Hybrid")
    mileage_kmpl: Optional[Decimal] = Field(
        None, gt=0, description="Fuel efficiency in km/l (or km/kWh for EV)"
    )
    custom_fuel_price: Optional[Decimal] = Field(
        None, gt=0, description="User-supplied fuel/energy price per unit in INR"
    )
    custom_on_road_price: Optional[Decimal] = Field(
        None, gt=0, description="User-supplied total on-road price in INR"
    )
    custom_ex_showroom_price: Optional[Decimal] = Field(
        None, gt=0, description="User-supplied ex-showroom price in INR"
    )
    calculation_date: Optional[datetime] = Field(
        None, description="Calculation date for rules & rates"
    )

    @model_validator(mode="after")
    def validate_and_reconcile_distances(self) -> "TCOCalculationRequest":
        if self.monthly_driving_distance_km is None and self.annual_driving_distance_km is None:
            # Default to benchmark 1,000 km/month (12,000 km/year)
            self.monthly_driving_distance_km = Decimal("1000.00")
            self.annual_driving_distance_km = Decimal("12000.00")
        elif (
            self.annual_driving_distance_km is not None and self.monthly_driving_distance_km is None
        ):
            self.monthly_driving_distance_km = (
                self.annual_driving_distance_km / Decimal("12.0")
            ).quantize(Decimal("0.01"))
        elif (
            self.monthly_driving_distance_km is not None and self.annual_driving_distance_km is None
        ):
            self.annual_driving_distance_km = (
                self.monthly_driving_distance_km * Decimal("12.0")
            ).quantize(Decimal("0.01"))
        else:
            # Both supplied: verify consistency or synchronize from annual
            expected_annual = self.monthly_driving_distance_km * Decimal("12.0")
            if abs(self.annual_driving_distance_km - expected_annual) > Decimal("10.0"):
                # Prefer annual distance if specifically specified
                self.monthly_driving_distance_km = (
                    self.annual_driving_distance_km / Decimal("12.0")
                ).quantize(Decimal("0.01"))
        return self


class TCOVehicleRequest(TCOCalculationRequest):
    variant_id: int = Field(..., description="Vehicle Variant ID is required")


# =============================================================================
# OUTPUT BREAKDOWN SCHEMAS
# =============================================================================


class TCOInitialCostBreakdown(BaseModel):
    ex_showroom_price: Decimal
    total_on_road_price: Decimal
    down_payment: Decimal
    loan_principal: Decimal


class TCOFinancingBreakdown(BaseModel):
    bank_id: Optional[int] = None
    bank_name: Optional[str] = None
    loan_product_name: Optional[str] = None
    annual_interest_rate: Decimal
    tenure_months: int
    monthly_emi: Decimal
    total_interest: Decimal
    processing_fees: Decimal
    total_repayment: Decimal


class TCOOperatingCostsSummary(BaseModel):
    annual_fuel_cost: Decimal
    annual_insurance_cost: Decimal
    annual_maintenance_cost: Decimal
    annual_total_operating_cost: Decimal


class TCOPeriodBreakdown(BaseModel):
    period_years: int
    period_months: int
    label: str

    # Operating components
    fuel_cost: Decimal
    insurance_cost: Decimal
    maintenance_cost: Decimal
    total_operating_cost: Decimal

    # Financing components (stops when loan tenure ends)
    financing_interest: Decimal
    financing_fees: Decimal
    loan_principal_paid: Decimal
    total_loan_repayment_paid: Decimal

    # Cash Outflow vs Economic Cost
    initial_down_payment: Decimal
    total_cash_outflow: Decimal
    estimated_depreciation: Decimal
    estimated_resale_value: Decimal
    loan_outstanding_principal: Optional[Decimal] = None
    net_equity_on_resale: Optional[Decimal] = None
    estimated_economic_cost: Decimal

    # Averages
    average_monthly_cost: Decimal
    average_monthly_operating_cost: Decimal
    average_annual_cost: Decimal


class TCODrivingProfile(BaseModel):
    annual_distance_km: Decimal
    monthly_distance_km: Decimal
    fuel_type: str
    fuel_efficiency: Decimal
    efficiency_unit: str  # "km/l", "km/kg", "km/kWh"
    fuel_price_per_unit: Decimal
    fuel_price_unit: str
    efficiency_source: str = "OEM_CLAIMED"
    fuel_price_source: Optional[str] = None
    fuel_price_verification: Optional[str] = None
    location_match_level: Optional[str] = None  # "CITY", "STATE", "NATIONAL_FALLBACK"


class TCOCalculationResponse(BaseModel):
    vehicle: Optional[Dict[str, Any]] = None
    location: Dict[str, Any]
    driving_profile: TCODrivingProfile
    initial_cost: TCOInitialCostBreakdown
    financing: Optional[TCOFinancingBreakdown] = None
    operating_costs: TCOOperatingCostsSummary
    periods: Dict[str, TCOPeriodBreakdown]
    data_status: str = "DEMO"
    disclaimer: str


# =============================================================================
# COMPARISON SCHEMAS
# =============================================================================


class TCOComparisonItem(BaseModel):
    variant_id: int
    variant_name: str
    model_name: str
    manufacturer_name: str
    fuel_type: str
    ex_showroom_price: Decimal
    on_road_price: Decimal
    monthly_emi: Decimal
    annual_fuel_cost: Decimal
    annual_operating_cost: Decimal
    one_year_tco: Decimal
    three_year_tco: Decimal
    five_year_tco: Decimal
    five_year_monthly_average: Decimal
    five_year_economic_cost: Decimal


class TCOComparisonRequest(BaseModel):
    variant_ids: List[int] = Field(
        ..., min_length=2, max_length=10, description="List of Variant IDs to compare"
    )
    state_id: int = Field(..., description="Target State/UT ID")
    city_id: Optional[int] = Field(None, description="Optional target City ID")
    rto_id: Optional[int] = Field(None, description="Optional target RTO ID")
    monthly_driving_distance_km: Optional[Decimal] = Field(None, ge=0, le=20000)
    annual_driving_distance_km: Optional[Decimal] = Field(None, ge=0, le=200000)
    down_payment: Optional[Decimal] = Field(None, ge=0)
    credit_score: Optional[int] = Field(750, ge=300, le=900)
    preferred_loan_tenure_months: Optional[int] = Field(60, ge=12, le=84)
    is_financed: bool = True


class TCOComparisonResponse(BaseModel):
    driving_profile: Dict[str, Any]
    location: Dict[str, Any]
    compared_vehicles: List[TCOComparisonItem]
    data_status: str = "DEMO"
    disclaimer: str
