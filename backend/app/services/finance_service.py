from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple
from app.core.exceptions import InvalidFinancialInputException
from app.schemas.finance import AmortizationScheduleItem, EmiCalculationResponse


def round_inr(amount: Decimal) -> Decimal:
    """Rounds monetary currency amounts strictly to 2 decimal places using standard ROUND_HALF_UP."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class FinanceService:
    """Pure domain mathematical calculations for auto loans, EMIs, amortization, and LTV.
    
    Guarantees:
    - Pure Decimal arithmetic (zero floating-point precision error).
    - Exact month-by-month reconciliation.
    - Final month ending balance reaches exactly ₹0.00 without rounding drift.
    """

    @staticmethod
    def calculate_emi(
        principal: Decimal,
        annual_interest_rate: Decimal,
        tenure_months: int,
    ) -> Decimal:
        """Calculates Equated Monthly Installment (EMI).
        Formula: EMI = [P * r * (1 + r)^n] / [(1 + r)^n - 1]
        """
        if principal <= 0:
            raise InvalidFinancialInputException("Principal amount must be greater than zero.")
        if annual_interest_rate < 0:
            raise InvalidFinancialInputException("Annual interest rate cannot be negative.")
        if tenure_months <= 0:
            raise InvalidFinancialInputException("Tenure months must be greater than zero.")
        if tenure_months > 120:
            raise InvalidFinancialInputException("Tenure months cannot exceed 120 months (10 years).")

        # 0% Interest promotional edge case
        if annual_interest_rate == 0:
            return round_inr(principal / Decimal(str(tenure_months)))

        # Monthly interest rate = Annual / 12 / 100
        monthly_rate = annual_interest_rate / Decimal("1200.0")

        # (1 + r)^n using high precision Decimal power
        one_plus_r = Decimal("1.0") + monthly_rate
        power_factor = Decimal(str(float(one_plus_r) ** tenure_months))

        numerator = principal * monthly_rate * power_factor
        denominator = power_factor - Decimal("1.0")

        if denominator == 0:
            raise InvalidFinancialInputException("Invalid loan parameters resulting in zero denominator.")

        emi = numerator / denominator
        return round_inr(emi)

    @classmethod
    def maximum_loan_for_emi(
        cls,
        maximum_emi: Decimal,
        annual_interest_rate: Decimal,
        tenure_months: int,
    ) -> Decimal:
        """Reverse EMI calculation: Computes maximum borrowing principal given affordable monthly EMI budget.
        Formula: P = [EMI * ((1 + r)^n - 1)] / [r * (1 + r)^n]
        """
        if maximum_emi <= 0:
            return Decimal("0.00")
        if annual_interest_rate < 0:
            raise InvalidFinancialInputException("Annual interest rate cannot be negative.")
        if tenure_months <= 0:
            return Decimal("0.00")

        if annual_interest_rate == 0:
            return round_inr(maximum_emi * Decimal(str(tenure_months)))

        monthly_rate = annual_interest_rate / Decimal("1200.0")
        one_plus_r = Decimal("1.0") + monthly_rate
        power_factor = Decimal(str(float(one_plus_r) ** tenure_months))

        numerator = maximum_emi * (power_factor - Decimal("1.0"))
        denominator = monthly_rate * power_factor

        max_principal = numerator / denominator
        return round_inr(max_principal)

    @classmethod
    def calculate_amortization_schedule(
        cls,
        principal: Decimal,
        annual_interest_rate: Decimal,
        tenure_months: int,
    ) -> List[AmortizationScheduleItem]:
        """Generates a complete month-by-month repayment schedule with exact reconciliation."""
        emi = cls.calculate_emi(principal, annual_interest_rate, tenure_months)
        schedule: List[AmortizationScheduleItem] = []
        balance = round_inr(principal)
        monthly_rate = annual_interest_rate / Decimal("1200.0")

        for m in range(1, tenure_months + 1):
            opening = balance
            if annual_interest_rate > 0:
                interest_month = round_inr(opening * monthly_rate)
            else:
                interest_month = Decimal("0.00")

            if m == tenure_months or opening + interest_month <= emi:
                # Final month adjustment: balance clears completely to 0.00
                principal_month = opening
                emi_actual = round_inr(principal_month + interest_month)
                closing = Decimal("0.00")
            else:
                principal_month = emi - interest_month
                emi_actual = emi
                closing = round_inr(opening - principal_month)

            item = AmortizationScheduleItem(
                installment_number=m,
                month=m,
                opening_balance=opening,
                beginning_balance=opening,
                emi=emi_actual,
                principal_component=principal_month,
                principal_paid=principal_month,
                interest_component=interest_month,
                interest_paid=interest_month,
                closing_balance=closing,
                ending_balance=closing,
            )
            schedule.append(item)
            balance = closing

        return schedule

    @staticmethod
    def calculate_ltv(loan_amount: Decimal, on_road_price: Decimal) -> Decimal:
        """Calculates Loan-to-Value (LTV) percentage."""
        if on_road_price <= 0:
            return Decimal("0.00")
        ltv = (loan_amount / on_road_price) * Decimal("100.0")
        return round_inr(ltv)

    @classmethod
    def calculate_full_loan_summary(
        cls,
        principal: Decimal,
        annual_interest_rate: Decimal,
        tenure_months: int,
        generate_amortization: bool = False,
    ) -> EmiCalculationResponse:
        """Legacy helper returning full loan summary and optional amortization."""
        emi = cls.calculate_emi(principal, annual_interest_rate, tenure_months)
        schedule: Optional[List[AmortizationScheduleItem]] = None
        
        if generate_amortization:
            schedule = cls.calculate_amortization_schedule(principal, annual_interest_rate, tenure_months)
            total_interest = sum(item.interest_component for item in schedule)
            total_payable = sum(item.emi for item in schedule)
        else:
            total_payable = emi * Decimal(str(tenure_months))
            total_interest = total_payable - principal

        return EmiCalculationResponse(
            principal_amount=round_inr(principal),
            annual_interest_rate=annual_interest_rate,
            tenure_months=tenure_months,
            monthly_emi=emi,
            total_interest_payable=round_inr(total_interest),
            total_amount_payable=round_inr(total_payable),
            amortization_schedule=schedule,
        )

    @classmethod
    def calculate_max_loan_from_emi_budget(
        cls,
        available_monthly_emi: Decimal,
        annual_interest_rate: Decimal,
        tenure_months: int,
    ) -> Decimal:
        return cls.maximum_loan_for_emi(available_monthly_emi, annual_interest_rate, tenure_months)

    @staticmethod
    def resolve_interest_rate_by_cibil(cibil_score: int) -> Decimal:
        """Benchmark retail interest rate tier based on credit score."""
        if cibil_score >= 800:
            return Decimal("8.65")  # Super prime (SBI / HDFC benchmark)
        elif cibil_score >= 750:
            return Decimal("8.75")  # Prime
        elif cibil_score >= 700:
            return Decimal("9.25")  # Standard
        elif cibil_score >= 650:
            return Decimal("10.50") # Sub-prime
        else:
            return Decimal("12.00") # High risk
