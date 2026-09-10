from decimal import Decimal
import pytest

from app.core.ingestion_constants import DataSourceType, IngestionEntityType
from app.ingestion.adapters.tco_data_adapter import (
    FADADepreciationBenchmarkAdapter,
    IndustryMaintenanceBenchmarkAdapter,
    IRDAIInsuranceRenewalAdapter,
    PPACFuelPriceAdapter,
    StateDiscomTariffAdapter,
)
from app.ingestion.validators.tco_validator import TCOValidator
from app.services.tco_service import TCOService


@pytest.mark.asyncio
async def test_ppac_fuel_price_adapter_pipeline():
    adapter = PPACFuelPriceAdapter()
    assert adapter.source_slug == "fuel_prices"
    assert adapter.source_type == DataSourceType.OFFICIAL_GOVERNMENT
    assert adapter.entity_type == IngestionEntityType.FUEL_PRICE

    raw_items = await adapter.get_fetcher().fetch()
    assert len(raw_items) >= 15

    parser = adapter.get_parser()
    normalizer = adapter.get_normalizer()
    validator = adapter.get_validator()
    mapper = adapter.get_mapper()

    for item in raw_items:
        parsed = parser.parse(item)
        normalized = normalizer.normalize(parsed)
        is_valid, errors = validator.validate(normalized)
        assert is_valid, f"Validation failed for {normalized}: {errors}"
        mapped = mapper.map_to_canonical(normalized)
        assert isinstance(mapped["price_per_unit"], Decimal)
        assert mapped["fuel_type"] in ["PETROL", "DIESEL", "CNG"]


@pytest.mark.asyncio
async def test_state_electricity_tariff_adapter_pipeline():
    adapter = StateDiscomTariffAdapter()
    assert adapter.source_slug == "electricity_tariffs"
    assert adapter.entity_type == IngestionEntityType.ELECTRICITY_TARIFF

    raw_items = await adapter.get_fetcher().fetch()
    assert len(raw_items) >= 5

    normalizer = adapter.get_normalizer()
    validator = adapter.get_validator()

    for item in raw_items:
        normalized = normalizer.normalize(item)
        is_valid, errors = validator.validate(normalized)
        assert is_valid, f"Validation failed: {errors}"
        assert isinstance(normalized["rate_per_kwh"], Decimal)
        assert normalized["rate_per_kwh"] > 0


@pytest.mark.asyncio
async def test_maintenance_and_insurance_and_depreciation_adapters():
    # 1. Maintenance
    m_adapter = IndustryMaintenanceBenchmarkAdapter()
    m_items = await m_adapter.get_fetcher().fetch()
    assert len(m_items) >= 5
    m_val = m_adapter.get_validator()
    for item in m_items:
        norm = m_adapter.get_normalizer().normalize(item)
        is_valid, errors = m_val.validate(norm)
        assert is_valid, errors
        assert norm["annual_base_cost"] > 0

    # 2. Insurance
    ins_adapter = IRDAIInsuranceRenewalAdapter()
    ins_items = await ins_adapter.get_fetcher().fetch()
    for item in ins_items:
        norm = ins_adapter.get_normalizer().normalize(item)
        is_valid, errors = ins_adapter.get_validator().validate(norm)
        assert is_valid, errors
        assert norm["year_2_factor"] < Decimal("1.00")

    # 3. Depreciation
    dep_adapter = FADADepreciationBenchmarkAdapter()
    dep_items = await dep_adapter.get_fetcher().fetch()
    for item in dep_items:
        norm = dep_adapter.get_normalizer().normalize(item)
        is_valid, errors = dep_adapter.get_validator().validate(norm)
        assert is_valid, errors
        assert norm["year_1_depreciation_pct"] < norm["year_5_depreciation_pct"]


def test_tco_validator_error_cases():
    validator = TCOValidator()

    # Invalid fuel price
    bad_fuel = {
        "tco_category": "fuel_price",
        "fuel_type": "KEROSENE",
        "price_per_unit": Decimal("500.00"),
        "unit": "Gallon",
    }
    is_valid, errors = validator.validate(bad_fuel)
    assert not is_valid
    assert len(errors) >= 3

    # Non-monotonic depreciation
    bad_dep = {
        "tco_category": "depreciation",
        "year_1_depreciation_pct": Decimal("30.00"),
        "year_2_depreciation_pct": Decimal("20.00"),  # Error: less than year 1
        "year_3_depreciation_pct": Decimal("40.00"),
        "year_4_depreciation_pct": Decimal("50.00"),
        "year_5_depreciation_pct": Decimal("60.00"),
    }
    is_valid, errors = validator.validate(bad_dep)
    assert not is_valid
    assert any("greater than previous year" in e for e in errors)


def test_tco_economic_cost_mathematical_integrity_and_negative_tco_prevention():
    """Verifies that 1-year, 3-year, and 5-year economic costs are strictly positive and accurate.

    Tests that:
    Economic Cost = (Total Initial On-Road Price - Resale Value) + Interest Paid + Fees + Operating Costs
    And Net Equity upon sale = max(0, Resale Value - Outstanding Principal)
    """
    ex_showroom = Decimal("1000000.00")
    total_on_road = Decimal("1150000.00")
    down_payment = Decimal("230000.00")
    loan_principal = Decimal("920000.00")
    loan_tenure_months = 60
    loan_fees = Decimal("4600.00")
    annual_fuel = Decimal("60000.00")
    annual_maint = Decimal("10000.00")
    first_year_ins = Decimal("35000.00")

    # Mock Amortization items for 60 months at ~8.75%
    from app.schemas.finance import AmortizationScheduleItem

    amort_items = []
    current_bal = loan_principal
    monthly_emi = Decimal("19000.00")
    for m in range(1, 61):
        interest = (current_bal * Decimal("0.0875") / Decimal("12")).quantize(Decimal("0.01"))
        principal = monthly_emi - interest
        current_bal = max(Decimal("0.00"), current_bal - principal)
        amort_items.append(
            AmortizationScheduleItem(
                month=m,
                emi=monthly_emi,
                principal_component=principal,
                interest_component=interest,
                remaining_principal=current_bal,
            )
        )

    ins_factors = (Decimal("0.65"), Decimal("0.60"), Decimal("0.75"), Decimal("0.70"))
    dep_percentages = (
        Decimal("15.00"),
        Decimal("25.00"),
        Decimal("35.00"),
        Decimal("43.00"),
        Decimal("50.00"),
    )

    # Evaluate 1-Year Period Breakdown
    pb_1yr = TCOService.build_period_breakdown(
        period_key="1_year",
        years=1,
        months=12,
        label="1 Year (12 Months)",
        annual_fuel_cost=annual_fuel,
        first_year_insurance=first_year_ins,
        annual_maintenance_cost=annual_maint,
        down_payment=down_payment,
        amortization_schedule=amort_items,
        loan_tenure_months=loan_tenure_months,
        loan_processing_fees=loan_fees,
        ex_showroom_price=ex_showroom,
        total_on_road_price=total_on_road,
        is_financed=True,
        ins_factors=ins_factors,
        dep_percentages=dep_percentages,
    )

    # 1. Economic cost MUST be positive!
    assert pb_1yr.estimated_economic_cost > Decimal(
        "0.00"
    ), f"1-Year economic cost must be positive, got {pb_1yr.estimated_economic_cost}"
    # 2. Resale value at Year 1 is 85% of ex-showroom (15% dep)
    assert pb_1yr.estimated_resale_value == Decimal("850000.00")
    # 3. Outstanding loan principal exists at month 12 (~₹7.67L)
    assert pb_1yr.loan_outstanding_principal > Decimal("700000.00")
    # 4. Net equity on liquidation = Resale Value - Outstanding Principal (~₹83K)
    assert pb_1yr.net_equity_on_resale == (
        pb_1yr.estimated_resale_value - pb_1yr.loan_outstanding_principal
    )
    # 5. Economic cost == Total Cash Outflow - Net Equity
    expected_economic_via_liquidation = pb_1yr.total_cash_outflow - pb_1yr.net_equity_on_resale
    assert abs(pb_1yr.estimated_economic_cost - expected_economic_via_liquidation) <= Decimal(
        "0.05"
    )

    # Evaluate 5-Year Period Breakdown
    pb_5yr = TCOService.build_period_breakdown(
        period_key="5_years",
        years=5,
        months=60,
        label="5 Years (60 Months)",
        annual_fuel_cost=annual_fuel,
        first_year_insurance=first_year_ins,
        annual_maintenance_cost=annual_maint,
        down_payment=down_payment,
        amortization_schedule=amort_items,
        loan_tenure_months=loan_tenure_months,
        loan_processing_fees=loan_fees,
        ex_showroom_price=ex_showroom,
        total_on_road_price=total_on_road,
        is_financed=True,
        ins_factors=ins_factors,
        dep_percentages=dep_percentages,
    )

    assert pb_5yr.estimated_economic_cost > pb_1yr.estimated_economic_cost
    assert pb_5yr.loan_outstanding_principal == Decimal("0.00")  # Fully paid off at month 60
    assert pb_5yr.net_equity_on_resale == pb_5yr.estimated_resale_value
