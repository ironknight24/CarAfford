from decimal import Decimal
import pytest

from app.core.ingestion_constants import DataSourceType, IngestionEntityType, VerificationStatus
from app.ingestion.adapters.bank_finance_adapter import (
    SbiCarLoanAdapter,
    HdfcCarLoanAdapter,
    IciciCarLoanAdapter,
    AxisCarLoanAdapter,
    BankOfBarodaCarLoanAdapter,
    KotakCarLoanAdapter,
    BaseBankFinanceAdapter,
)
from app.ingestion.validators.finance_validator import FinanceDataValidator


@pytest.mark.asyncio
async def test_bank_adapter_metadata_and_source_registration():
    """Validates metadata structure and trust level across all 6 bank adapters."""
    adapters = [
        SbiCarLoanAdapter(),
        HdfcCarLoanAdapter(),
        IciciCarLoanAdapter(),
        AxisCarLoanAdapter(),
        BankOfBarodaCarLoanAdapter(),
        KotakCarLoanAdapter(),
    ]

    for adapter in adapters:
        meta = adapter.get_source_metadata()
        assert meta["source_type"] == DataSourceType.OFFICIAL_BANK.value
        assert meta["entity_type"] == IngestionEntityType.FINANCE.value
        assert meta["trust_level"] >= 90
        assert meta["is_authoritative"] is True
        assert meta["is_active"] is True
        assert meta["freshness_sla_hours"] == 168
        assert "http" in meta["source_url"]
        assert meta["name"] == adapter.source_slug


@pytest.mark.asyncio
async def test_sbi_car_loan_adapter_fetch_and_parse():
    """Validates SBI adapter product parsing, Green EV concession, and fee definitions."""
    adapter = SbiCarLoanAdapter()
    raw_items = await adapter.fetch()
    assert len(raw_items) == 2  # Standard + Green Car Loan

    # Standard car loan
    parsed_std = adapter.parse(raw_items[0])
    assert parsed_std["bank_name"] == "State Bank of India"
    assert parsed_std["product_name"] == "SBI Car Loan"
    assert parsed_std["product_category"] == "STANDARD"
    assert parsed_std["min_tenure_months"] == 12
    assert parsed_std["max_tenure_months"] == 84

    # Green EV loan
    parsed_green = adapter.parse(raw_items[1])
    assert parsed_green["product_name"] == "SBI Green Car Loan"
    assert parsed_green["product_category"] == "EV_GREEN"
    assert parsed_green["max_tenure_months"] == 96  # 8 years tenure for EV


@pytest.mark.asyncio
async def test_bank_finance_normalizer_and_starting_rate_priority():
    """Validates normalizer distinctions between benchmark starting rates (priority 100) and CIBIL tiers (priority 200)."""
    adapter = SbiCarLoanAdapter()
    raw_items = await adapter.fetch()
    normalized = adapter.normalize(adapter.parse(raw_items[0]))

    rates = normalized["rates"]
    assert len(rates) == 5

    # Benchmark rate (priority 100, no cibil constraint)
    benchmark_rate = [r for r in rates if r["priority"] == 100][0]
    assert benchmark_rate["annual_interest_rate"] == Decimal("8.65")
    assert benchmark_rate.get("min_credit_score") is None

    # CIBIL specific rates (priority 200)
    tiered_rates = [r for r in rates if r["priority"] == 200]
    assert len(tiered_rates) == 4
    top_tier = [r for r in tiered_rates if r["min_credit_score"] == 775][0]
    assert top_tier["annual_interest_rate"] == Decimal("8.65")

    low_tier = [r for r in tiered_rates if r["min_credit_score"] == 300][0]
    assert low_tier["annual_interest_rate"] == Decimal("9.40")


@pytest.mark.asyncio
async def test_fee_structure_and_capped_percentage_normalization():
    """Validates processing fee, capped percentage calculations, and documentation charges."""
    adapter = HdfcCarLoanAdapter()
    raw_items = await adapter.fetch()
    normalized = adapter.normalize(adapter.parse(raw_items[0]))

    fees = normalized["fees"]
    assert len(fees) >= 2
    proc_fee = [f for f in fees if f["fee_type"] == "PROCESSING_FEE"][0]
    assert proc_fee["calculation_method"] == "CAPPED_PERCENTAGE"
    assert proc_fee["percentage"] == Decimal("0.50")
    assert proc_fee["minimum_amount"] == Decimal("3500.00")
    assert proc_fee["maximum_amount"] == Decimal("8000.00")


@pytest.mark.asyncio
async def test_finance_validator_bounds_and_error_handling():
    """Validates FinanceDataValidator against erroneous inputs."""
    validator = FinanceDataValidator()

    # Valid payload
    valid_payload = {
        "bank_name": "ICICI Bank",
        "product_name": "ICICI Auto Loan",
        "product_category": "STANDARD",
        "vehicle_condition": "NEW",
        "min_loan_amount": Decimal("100000.00"),
        "max_loan_amount": Decimal("10000000.00"),
        "min_tenure_months": 12,
        "max_tenure_months": 84,
        "annual_interest_rate": Decimal("8.80"),
        "min_cibil_score": 750,
        "max_cibil_score": 900,
    }
    is_valid, errors = validator.validate(valid_payload)
    assert is_valid is True
    assert len(errors) == 0

    # Negative loan amounts
    invalid_loans = dict(valid_payload, min_loan_amount=Decimal("-5000"))
    is_valid, errors = validator.validate(invalid_loans)
    assert is_valid is False
    assert any("must be non-negative" in e for e in errors)

    # Inverted CIBIL bounds
    invalid_cibil = dict(valid_payload, min_cibil_score=800, max_cibil_score=700)
    is_valid, errors = validator.validate(invalid_cibil)
    assert is_valid is False
    assert any("min_cibil_score" in e for e in errors)

    # Out of bounds rate (e.g. 45% or -2%)
    invalid_rate = dict(valid_payload, annual_interest_rate=Decimal("45.0"))
    is_valid, errors = validator.validate(invalid_rate)
    assert is_valid is False
    assert any("outside realistic auto loan bounds" in e for e in errors)
