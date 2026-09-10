from decimal import Decimal
import pytest
from app.core.exceptions import InvalidFinancialInputException
from app.services.finance_service import FinanceService


def test_emi_calculation_standard_sbi():
    # Principal: ₹10,00,000 (10 Lakhs), Rate: 8.75% p.a., Tenure: 60 months (5 years)
    principal = Decimal("1000000.00")
    rate = Decimal("8.75")
    tenure = 60

    emi = FinanceService.calculate_emi(principal, rate, tenure)
    # Exact mathematical EMI: ₹20,637.23
    assert isinstance(emi, Decimal)
    assert emi == Decimal("20637.23")


def test_emi_calculation_short_tenure():
    # Principal: ₹5,00,000, Rate: 9.00%, Tenure: 36 months
    principal = Decimal("500000.00")
    rate = Decimal("9.00")
    tenure = 36

    emi = FinanceService.calculate_emi(principal, rate, tenure)
    assert emi == Decimal("15899.87")


def test_emi_calculation_zero_interest():
    principal = Decimal("120000.00")
    rate = Decimal("0.0")
    tenure = 12

    emi = FinanceService.calculate_emi(principal, rate, tenure)
    assert emi == Decimal("10000.00")


def test_emi_calculation_invalid_inputs():
    with pytest.raises(InvalidFinancialInputException):
        FinanceService.calculate_emi(Decimal("-1000"), Decimal("8.5"), 60)

    with pytest.raises(InvalidFinancialInputException):
        FinanceService.calculate_emi(Decimal("100000"), Decimal("8.5"), 0)


def test_max_loan_from_emi_budget():
    # If a user can afford ₹20,637.23 monthly at 8.75% for 60 months, max loan should equal ₹10,00,000
    emi_budget = Decimal("20637.23")
    rate = Decimal("8.75")
    tenure = 60

    max_loan = FinanceService.calculate_max_loan_from_emi_budget(emi_budget, rate, tenure)
    # Rounding difference should be within ₹1
    assert abs(max_loan - Decimal("1000000.00")) <= Decimal("1.00")


def test_loan_summary_and_amortization():
    principal = Decimal("500000.00")
    rate = Decimal("9.00")
    tenure = 12

    res = FinanceService.calculate_full_loan_summary(
        principal, rate, tenure, generate_amortization=True
    )
    assert res.monthly_emi > Decimal("0")
    assert res.total_amount_payable > principal
    assert res.total_interest_payable == res.total_amount_payable - principal
    assert len(res.amortization_schedule) == 12
    # Last month balance should be 0.00
    assert res.amortization_schedule[-1].ending_balance == Decimal("0.00")


def test_cibil_interest_rate_resolution():
    assert FinanceService.resolve_interest_rate_by_cibil(820) == Decimal("8.65")
    assert FinanceService.resolve_interest_rate_by_cibil(760) == Decimal("8.75")
    assert FinanceService.resolve_interest_rate_by_cibil(720) == Decimal("9.25")
    assert FinanceService.resolve_interest_rate_by_cibil(660) == Decimal("10.50")
    assert FinanceService.resolve_interest_rate_by_cibil(550) == Decimal("12.00")
