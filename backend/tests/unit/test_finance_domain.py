from datetime import datetime, timezone
from decimal import Decimal
import pytest
from app.core.exceptions import InvalidFinancialInputException
from app.models.finance import (
    Bank,
    InterestRate,
    LoanEligibilityRule,
    LoanFee,
    LoanProduct,
)
from app.services.finance_service import FinanceService
from app.services.loan_eligibility_service import (
    LoanEligibilityEvaluatorService,
)
from app.services.loan_fee_service import LoanFeeCalculatorService
from app.services.loan_rate_resolver import LoanRateResolverService


class TestFinanceServiceMath:
    def test_emi_calculation_standard(self):
        # Loan: 1,000,000, 8.5% interest, 60 months (5 years)
        # Standard EMI: ~20,516.53
        emi = FinanceService.calculate_emi(
            principal=Decimal("1000000.00"),
            annual_interest_rate=Decimal("8.50"),
            tenure_months=60,
        )
        assert emi == Decimal("20516.53")

    def test_emi_calculation_zero_interest(self):
        # 0% interest loan: 120,000 over 12 months = 10,000/month
        emi = FinanceService.calculate_emi(
            principal=Decimal("120000.00"),
            annual_interest_rate=Decimal("0.00"),
            tenure_months=12,
        )
        assert emi == Decimal("10000.00")

    def test_emi_calculation_invalid_inputs(self):
        with pytest.raises(InvalidFinancialInputException):
            FinanceService.calculate_emi(
                principal=Decimal("-100"),
                annual_interest_rate=Decimal("8.0"),
                tenure_months=12,
            )
        with pytest.raises(InvalidFinancialInputException):
            FinanceService.calculate_emi(
                principal=Decimal("100000"),
                annual_interest_rate=Decimal("8.0"),
                tenure_months=0,
            )

    def test_reverse_emi_max_loan(self):
        # Desired EMI: 20,516.53, 8.5%, 60 months -> Principal ~ 1,000,000
        max_loan = FinanceService.maximum_loan_for_emi(
            maximum_emi=Decimal("20516.53"),
            annual_interest_rate=Decimal("8.50"),
            tenure_months=60,
        )
        # Should be extremely close to 1,000,000
        assert abs(max_loan - Decimal("1000000.00")) <= Decimal("1.00")

    def test_reverse_emi_zero_interest(self):
        max_loan = FinanceService.maximum_loan_for_emi(
            maximum_emi=Decimal("10000.00"),
            annual_interest_rate=Decimal("0.00"),
            tenure_months=12,
        )
        assert max_loan == Decimal("120000.00")

    def test_amortization_schedule_zero_drift_reconciliation(self):
        principal = Decimal("500000.00")
        rate = Decimal("9.00")
        tenure = 36

        schedule = FinanceService.calculate_amortization_schedule(
            principal=principal,
            annual_interest_rate=rate,
            tenure_months=tenure,
        )

        assert len(schedule) == 36

        # Check first month
        first = schedule[0]
        assert first.installment_number == 1
        assert first.opening_balance == principal
        assert first.principal_component + first.interest_component == first.emi

        # Check last month
        last = schedule[-1]
        assert last.installment_number == 36
        assert last.closing_balance == Decimal("0.00")

        # Sum of principal components MUST equal original principal exactly
        total_principal_paid = sum(item.principal_component for item in schedule)
        assert total_principal_paid == principal

    def test_ltv_calculation(self):
        ltv = FinanceService.calculate_ltv(
            loan_amount=Decimal("800000.00"),
            on_road_price=Decimal("1000000.00"),
        )
        assert ltv == Decimal("80.00")

        ltv_zero = FinanceService.calculate_ltv(
            loan_amount=Decimal("800000.00"),
            on_road_price=Decimal("0.00"),
        )
        assert ltv_zero == Decimal("0.00")


class TestLoanRateResolverService:
    def test_rate_resolution_specificity_and_credit_score(self):
        bank = Bank(name="Test Bank", slug="test-bank", active=True)
        product = LoanProduct(
            bank=bank,
            name="Test Auto Loan",
            slug="test-auto-loan",
            active=True,
        )

        # Base rate
        r_base = InterestRate(
            id=1,
            loan_product=product,
            rate_type="FLOATING",
            annual_interest_rate=Decimal("9.00"),
            effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            active=True,
            priority=0,
        )

        # High credit score tier
        r_tier_high = InterestRate(
            id=2,
            loan_product=product,
            rate_type="FLOATING",
            annual_interest_rate=Decimal("8.50"),
            min_credit_score=750,
            max_credit_score=900,
            effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            active=True,
            priority=10,
        )

        # Mid credit score tier
        r_tier_mid = InterestRate(
            id=3,
            loan_product=product,
            rate_type="FLOATING",
            annual_interest_rate=Decimal("8.80"),
            min_credit_score=700,
            max_credit_score=749,
            effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            active=True,
            priority=10,
        )

        product.interest_rates = [r_base, r_tier_high, r_tier_mid]

        # Scenario 1: User has 780 CIBIL -> Should match high tier
        rate_high, rate_type_high, matched_high = (
            LoanRateResolverService.resolve_product_interest_rate(
                loan_product=product,
                credit_score=780,
                tenure_months=60,
                loan_amount=Decimal("800000"),
                calculation_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
            )
        )
        assert rate_high == Decimal("8.50")
        assert matched_high.id == 2

        # Scenario 2: User has 720 CIBIL -> Should match mid tier
        rate_mid, rate_type_mid, matched_mid = (
            LoanRateResolverService.resolve_product_interest_rate(
                loan_product=product,
                credit_score=720,
                tenure_months=60,
                loan_amount=Decimal("800000"),
                calculation_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
            )
        )
        assert rate_mid == Decimal("8.80")
        assert matched_mid.id == 3

    def test_historical_date_filtering(self):
        product = LoanProduct(
            name="P",
            slug="p",
            active=True,
        )

        old_rate = InterestRate(
            id=10,
            loan_product=product,
            rate_type="FIXED",
            annual_interest_rate=Decimal("7.50"),
            effective_from=datetime(2023, 1, 1, tzinfo=timezone.utc),
            effective_to=datetime(2023, 12, 31, tzinfo=timezone.utc),
            active=True,
        )

        current_rate = InterestRate(
            id=11,
            loan_product=product,
            rate_type="FIXED",
            annual_interest_rate=Decimal("8.75"),
            effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            effective_to=None,
            active=True,
        )

        product.interest_rates = [old_rate, current_rate]

        # Query in 2023
        rate_2023, _, matched_2023 = LoanRateResolverService.resolve_product_interest_rate(
            loan_product=product,
            loan_amount=Decimal("500000"),
            tenure_months=36,
            calculation_date=datetime(2023, 6, 1, tzinfo=timezone.utc),
        )
        assert rate_2023 == Decimal("7.50")
        assert matched_2023.id == 10

        # Query in 2025
        rate_2025, _, matched_2025 = LoanRateResolverService.resolve_product_interest_rate(
            loan_product=product,
            loan_amount=Decimal("500000"),
            tenure_months=36,
            calculation_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        )
        assert rate_2025 == Decimal("8.75")
        assert matched_2025.id == 11


class TestLoanFeeCalculatorService:
    def test_fee_calculations(self):
        product = LoanProduct(name="P", slug="p", active=True)

        fee_fixed = LoanFee(
            fee_name="Documentation Fee",
            fee_type="DOCUMENTATION_FEE",
            calculation_method="FIXED",
            fixed_amount=Decimal("1500.00"),
            effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            active=True,
        )

        fee_pct = LoanFee(
            fee_name="Processing Fee",
            fee_type="PROCESSING_FEE",
            calculation_method="CAPPED_PERCENTAGE",
            percentage=Decimal("0.50"),
            minimum_amount=Decimal("2000.00"),
            maximum_amount=Decimal("5000.00"),
            effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            active=True,
        )

        product.fees = [fee_fixed, fee_pct]

        # Loan amount: 200,000 -> 0.5% = 1,000 -> capped at min 2,000 + 1,500 = 3,500
        total_fee_small, items_small = LoanFeeCalculatorService.calculate_product_fees(
            loan_product=product,
            loan_amount=Decimal("200000.00"),
            calculation_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        assert total_fee_small == Decimal("3500.00")

        # Loan amount: 2,000,000 -> 0.5% = 10,000 -> capped at max 5,000 + 1,500 = 6,500
        total_fee_large, items_large = LoanFeeCalculatorService.calculate_product_fees(
            loan_product=product,
            loan_amount=Decimal("2000000.00"),
            calculation_date=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        assert total_fee_large == Decimal("6500.00")


class TestLoanEligibilityEvaluatorService:
    def test_eligibility_evaluation_eligible_and_ineligible(self):
        product = LoanProduct(
            name="Standard Auto Loan",
            slug="standard-auto-loan",
            min_loan_amount=Decimal("100000.00"),
            max_loan_amount=Decimal("5000000.00"),
            min_tenure_months=12,
            max_tenure_months=84,
            max_ltv_percent=Decimal("90.00"),
            active=True,
        )

        rule = LoanEligibilityRule(
            rule_name="Salaried Standard",
            min_monthly_income=Decimal("30000.00"),
            min_credit_score=700,
            max_ltv_percent=Decimal("85.00"),
            min_age_years=21,
            max_age_years=65,
            effective_from=datetime(2025, 1, 1, tzinfo=timezone.utc),
            active=True,
        )
        product.eligibility_rules = [rule]

        # 1. Fully eligible
        is_el_1, status_1, reasons_1 = LoanEligibilityEvaluatorService.evaluate_product_eligibility(
            loan_product=product,
            loan_amount=Decimal("800000.00"),
            on_road_price=Decimal("1000000.00"),  # LTV = 80%
            tenure_months=60,
            credit_score=750,
            monthly_income=Decimal("50000.00"),
            applicant_age=30,
        )
        assert is_el_1 is True
        assert status_1 == "ESTIMATED_ELIGIBLE"
        assert len(reasons_1) == 0

        # 2. Ineligible due to credit score below rule requirement
        is_el_2, status_2, reasons_2 = LoanEligibilityEvaluatorService.evaluate_product_eligibility(
            loan_product=product,
            loan_amount=Decimal("800000.00"),
            on_road_price=Decimal("1000000.00"),
            tenure_months=60,
            credit_score=600,
            monthly_income=Decimal("50000.00"),
            applicant_age=30,
        )
        assert is_el_2 is False
        assert status_2 == "ESTIMATED_INELIGIBLE"
        assert len(reasons_2) > 0
