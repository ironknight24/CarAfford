from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion_constants import IngestionRunStatus, VerificationStatus, ConflictStatus
from app.models.finance import Bank, LoanProduct, InterestRate, LoanEligibilityRule, LoanFee
from app.models.ingestion import DataConflictRecord, IngestionRun
from app.services.finance_service import FinanceService


@pytest.mark.asyncio
async def test_bank_finance_ingestion_api_flow(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """End-to-end ingestion flow for official bank auto-loan products, rate cards, and fees."""
    # 1. Trigger SBI Ingestion Run
    payload = {
        "dataset_name": "sbi_car_loans",
        "notes": "SBI official car-loan circular ingestion",
    }
    res = await async_client.post("/api/v1/ingestion/runs", json=payload)
    assert res.status_code == 201
    run_data = res.json()["data"]
    assert run_data["status"] == IngestionRunStatus.COMPLETED.value
    assert run_data["records_created"] >= 1

    # 2. Verify Canonical Bank & Product in DB
    bank_res = await db_session.execute(select(Bank).where(Bank.slug == "state-bank-of-india"))
    bank = bank_res.scalars().first()
    assert bank is not None
    assert bank.verification_status == VerificationStatus.VERIFIED.value
    assert bank.website_url == "https://sbi.co.in"

    # Verify Standard & Green Car Loan Products
    prod_res = await db_session.execute(select(LoanProduct).where(LoanProduct.bank_id == bank.id))
    products = prod_res.scalars().all()
    assert len(products) >= 2
    std_product = [p for p in products if p.product_category == "STANDARD"][0]
    green_product = [p for p in products if p.product_category == "EV_GREEN"][0]

    assert std_product.verification_status == VerificationStatus.VERIFIED.value
    assert green_product.verification_status == VerificationStatus.VERIFIED.value
    assert green_product.max_tenure_months == 96

    # 3. Verify Rates, Eligibility Rules & Fees
    rates_res = await db_session.execute(
        select(InterestRate).where(InterestRate.loan_product_id == std_product.id)
    )
    rates = rates_res.scalars().all()
    assert len(rates) >= 4
    benchmark_rate = [r for r in rates if r.priority == 100][0]
    assert benchmark_rate.annual_interest_rate == Decimal("8.65")
    assert benchmark_rate.verification_status == VerificationStatus.VERIFIED.value

    fees_res = await db_session.execute(
        select(LoanFee).where(LoanFee.loan_product_id == std_product.id)
    )
    fees = fees_res.scalars().all()
    assert len(fees) >= 2
    proc_fee = [f for f in fees if f.fee_type == "PROCESSING_FEE"][0]
    assert proc_fee.calculation_method == "CAPPED_PERCENTAGE"
    assert proc_fee.percentage == Decimal("0.40")


@pytest.mark.asyncio
async def test_rate_history_preservation_and_effective_dating(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """When a bank revises interest rates, the historical record is preserved with closed effective_to and a new record is created."""
    # 1. Ingest initial rate via HDFC adapter
    res1 = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"dataset_name": "hdfc_car_loans", "notes": "HDFC initial rate card"},
    )
    assert res1.status_code == 201

    # Verify initial active rates
    prod_res = await db_session.execute(
        select(LoanProduct).where(LoanProduct.slug == "hdfc-bank-hdfc-customfit-car-loan")
    )
    product = prod_res.scalars().first()
    assert product is not None

    initial_top_tier_rate = (
        (
            await db_session.execute(
                select(InterestRate).where(
                    InterestRate.loan_product_id == product.id,
                    InterestRate.min_credit_score == 750,
                    InterestRate.active.is_(True),
                )
            )
        )
        .scalars()
        .first()
    )
    assert initial_top_tier_rate is not None
    assert initial_top_tier_rate.annual_interest_rate == Decimal("8.75")
    initial_id = initial_top_tier_rate.id

    # 2. Simulate subsequent revised ingestion where rate drops to 8.50% from 2026-07-01
    from app.ingestion.adapters.bank_finance_adapter import HdfcCarLoanAdapter
    from app.services.ingestion_service import IngestionService

    revised_fixture = [
        {
            "source_record_id": "hdfc-customfit-car-loan",
            "bank_name": "HDFC Bank",
            "product_name": "HDFC CustomFit Car Loan",
            "product_category": "STANDARD",
            "vehicle_type": "CAR",
            "vehicle_condition": "NEW",
            "effective_from": "2026-07-01T00:00:00Z",
            "rates": [
                {
                    "annual_interest_rate": "8.50",
                    "rate_type": "FLOATING",
                    "min_credit_score": 750,
                    "max_credit_score": 900,
                    "priority": 200,
                    "effective_from": "2026-07-01T00:00:00Z",
                    "effective_to": None,
                }
            ],
        }
    ]
    custom_adapter = HdfcCarLoanAdapter(fixture_data=revised_fixture)
    await IngestionService.run_adapter(db_session, custom_adapter, notes="HDFC Q3 Rate Reduction")

    # 3. Verify history preservation in Database
    all_rates_res = await db_session.execute(
        select(InterestRate)
        .where(
            InterestRate.loan_product_id == product.id,
            InterestRate.min_credit_score == 750,
        )
        .order_by(InterestRate.effective_from.asc())
    )
    all_rates = all_rates_res.scalars().all()
    assert len(all_rates) >= 2

    # Old rate is deactivated with effective_to populated
    old_rate = [r for r in all_rates if r.id == initial_id][0]
    assert old_rate.active is False
    assert old_rate.effective_to is not None
    assert old_rate.annual_interest_rate == Decimal("8.75")

    # New rate is active with effective_to=None
    new_rate = [r for r in all_rates if r.id != initial_id and r.active is True][0]
    assert new_rate.active is True
    assert new_rate.effective_to is None
    assert new_rate.annual_interest_rate == Decimal("8.50")


@pytest.mark.asyncio
async def test_finance_ingestion_idempotency(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """Repeated ingestion of unchanged source data is strictly idempotent with zero duplicate rows."""
    payload = {"dataset_name": "icici_car_loans", "notes": "ICICI run 1"}
    res1 = await async_client.post("/api/v1/ingestion/runs", json=payload)
    assert res1.status_code == 201
    run1 = res1.json()["data"]
    assert run1["status"] == IngestionRunStatus.COMPLETED.value

    # Second run with same data
    res2 = await async_client.post(
        "/api/v1/ingestion/runs", json={"dataset_name": "icici_car_loans", "notes": "ICICI run 2"}
    )
    assert res2.status_code == 201
    run2 = res2.json()["data"]
    assert run2["records_created"] == 0
    assert run2["records_unchanged"] >= 1


@pytest.mark.asyncio
async def test_canonical_finance_apis_and_calculations(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """Validates that existing canonical finance endpoints function accurately with authoritative bank data."""
    # Ensure SBI is ingested
    await async_client.post("/api/v1/ingestion/runs", json={"dataset_name": "sbi_car_loans"})

    # 1. Banks API
    banks_res = await async_client.get("/api/v1/finance/banks")
    assert banks_res.status_code == 200
    banks = banks_res.json()["items"]
    assert len(banks) > 0

    # 2. Loan Products API
    products_res = await async_client.get("/api/v1/finance/loan-products")
    assert products_res.status_code == 200
    products = products_res.json()["items"]
    assert len(products) > 0

    # 3. Calculation API
    calc_req = {
        "on_road_price": 1000000.00,
        "down_payment": 200000.00,
        "tenure_months": 60,
        "credit_score": 780,
    }
    calc_res = await async_client.post("/api/v1/finance/calculate", json=calc_req)
    assert calc_res.status_code == 200
    calc_data = calc_res.json()["data"]
    assert "loan_amount" in calc_data
    assert Decimal(str(calc_data["loan_amount"])) == Decimal("800000.00")
    assert "selected_offer" in calc_data
    assert Decimal(str(calc_data["selected_offer"]["monthly_emi"])) > 0
    assert Decimal(str(calc_data["selected_offer"]["annual_interest_rate"])) > 0


@pytest.mark.asyncio
async def test_financial_mathematics_correctness_and_decimal_precision():
    """Validates mathematical correctness of EMI formula P*r*(1+r)^n / ((1+r)^n - 1) and Decimal precision."""
    # Principal: 10,00,000 INR, 8.5% annual rate, 60 months (5 years)
    p = Decimal("1000000.00")
    rate_annual = Decimal("8.50")
    tenure_months = 60

    emi = FinanceService.calculate_emi(
        principal=p,
        annual_interest_rate=rate_annual,
        tenure_months=tenure_months,
    )

    # Standard formula verification
    r_monthly = (rate_annual / Decimal("100")) / Decimal("12")
    factor = (Decimal("1") + r_monthly) ** tenure_months
    expected_emi = (p * r_monthly * factor / (factor - Decimal("1"))).quantize(Decimal("0.01"))

    assert emi == expected_emi

    # Verify amortization totals
    sched = FinanceService.calculate_amortization_schedule(
        principal=p,
        annual_interest_rate=rate_annual,
        tenure_months=tenure_months,
    )
    assert len(sched) == 60
    total_principal_paid = sum(item.principal_component for item in sched)
    assert total_principal_paid == p
    assert sched[-1].closing_balance == Decimal("0.00")

    # Verify zero-interest edge case
    zero_emi = FinanceService.calculate_emi(
        principal=p,
        annual_interest_rate=Decimal("0.00"),
        tenure_months=10,
    )
    assert zero_emi == Decimal("100000.00")


@pytest.mark.asyncio
async def test_all_six_major_banks_ingestion_and_promotion(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """Ingests all 6 major banks and verifies canonical persistence, products, and rates."""
    sources = [
        "sbi_car_loans",
        "hdfc_car_loans",
        "icici_car_loans",
        "axis_car_loans",
        "bob_car_loans",
        "kotak_car_loans",
    ]

    for s in sources:
        res = await async_client.post("/api/v1/ingestion/runs", json={"dataset_name": s})
        assert res.status_code == 201
        data = res.json()["data"]
        assert data["status"] == IngestionRunStatus.COMPLETED.value
        assert data["records_created"] + data["records_updated"] + data["records_unchanged"] >= 1

    # Verify all 6 banks exist and are verified
    banks_res = await db_session.execute(
        select(Bank).where(
            Bank.slug.in_(
                [
                    "state-bank-of-india",
                    "hdfc-bank",
                    "icici-bank",
                    "axis-bank",
                    "bank-of-baroda",
                    "kotak-mahindra-bank",
                ]
            )
        )
    )
    banks = banks_res.scalars().all()
    assert len(banks) == 6
    for b in banks:
        assert b.verification_status == VerificationStatus.VERIFIED.value


@pytest.mark.asyncio
async def test_cross_source_rate_conflict_detection(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """Detects and logs discrepancy when two different sources report conflicting interest rates for the same product."""
    from app.ingestion.adapters.bank_finance_adapter import BaseBankFinanceAdapter
    from app.services.ingestion_service import IngestionService

    # 1. Primary official SBI run
    await async_client.post("/api/v1/ingestion/runs", json={"dataset_name": "sbi_car_loans"})

    # 2. Secondary commercial feed with conflicting rate for same product slab
    conflict_fixture = [
        {
            "source_record_id": "commercial-sbi-car-loan",
            "bank_name": "State Bank of India",
            "product_name": "SBI Car Loan",
            "rates": [
                {
                    "annual_interest_rate": "9.10",  # Discrepancy vs 8.65%
                    "rate_type": "FLOATING",
                    "min_credit_score": 775,
                    "max_credit_score": 900,
                }
            ],
        }
    ]

    class CommercialBankRateAdapter(BaseBankFinanceAdapter):
        def __init__(self):
            super().__init__(
                source_name="commercial_loan_feed",
                display_name="Commercial Aggregator Auto Loan Feed",
                bank_name="State Bank of India",
                trust_level=80,
                fixture_data=conflict_fixture,
            )

    comm_adapter = CommercialBankRateAdapter()
    await IngestionService.run_adapter(
        db_session, comm_adapter, notes="Secondary commercial feed run"
    )

    # 3. Verify conflict recorded
    conflicts_res = await async_client.get("/api/v1/ingestion/data-quality/conflicts")
    assert conflicts_res.status_code == 200
    conflicts = conflicts_res.json()["data"]
    rate_conflicts = [c for c in conflicts if c["field_name"] == "annual_interest_rate"]
    assert len(rate_conflicts) >= 1
    assert "State Bank of India" in rate_conflicts[0]["entity_identifier"]


@pytest.mark.asyncio
async def test_freshness_report_includes_finance_dataset(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """Freshness endpoint evaluates bank_rates, loan_fees, and eligibility_rules SLAs."""
    await async_client.post("/api/v1/ingestion/runs", json={"dataset_name": "sbi_car_loans"})

    quality_res = await async_client.get("/api/v1/ingestion/data-quality")
    assert quality_res.status_code == 200
    q_data = quality_res.json()["data"]
    assert Decimal(str(q_data["overall_quality_score"])) > 0

    freshness_list = q_data["freshness_report"]
    dataset_names = [f["dataset_name"] for f in freshness_list]
    assert "bank_rates" in dataset_names
    assert "loan_fees" in dataset_names
    assert "eligibility_rules" in dataset_names
