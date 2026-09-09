from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple
from app.core.config import settings
from app.core.exceptions import InvalidFinancialInputException
from app.schemas.finance import AmortizationScheduleItem, EmiCalculationResponse


def round_inr(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class FinanceService:
    """Pure domain finance calculations for car loans, EMIs, and banking eligibility."""

    @staticmethod
    def calculate_emi(
        principal: Decimal,
        annual_interest_rate: Decimal,
        tenure_months: int,
    ) -> Decimal:
        """Calculates monthly Equated Monthly Installment (EMI) using high-precision Decimal arithmetic.
        Formula: EMI = [P * r * (1 + r)^n] / [(1 + r)^n - 1]
        """
        if principal <= 0:
            raise InvalidFinancialInputException("Principal amount must be greater than zero.")
        if annual_interest_rate <= 0:
            # 0% interest edge case
            return round_inr(principal / Decimal(str(tenure_months)))
        if tenure_months <= 0:
            raise InvalidFinancialInputException("Tenure months must be greater than zero.")

        # Monthly interest rate = Annual / 12 / 100
        monthly_rate = annual_interest_rate / Decimal("1200.0")

        # (1 + r)^n using high precision
        one_plus_r = Decimal("1.0") + monthly_rate
        # Calculate power with floating conversion for exponentiation then back to Decimal with high precision
        power_factor = Decimal(str(float(one_plus_r) ** tenure_months))

        numerator = principal * monthly_rate * power_factor
        denominator = power_factor - Decimal("1.0")

        if denominator == 0:
            raise InvalidFinancialInputException("Invalid loan parameters resulting in zero denominator.")

        emi = numerator / denominator
        return round_inr(emi)

    @classmethod
    def calculate_full_loan_summary(
        cls,
        principal: Decimal,
        annual_interest_rate: Decimal,
        tenure_months: int,
        generate_amortization: bool = False,
    ) -> EmiCalculationResponse:
        """Computes EMI, total interest payable, total repayment amount, and optional monthly amortization schedule."""
        emi = cls.calculate_emi(principal, annual_interest_rate, tenure_months)
        total_payable = emi * Decimal(str(tenure_months))
        total_interest = total_payable - principal

        schedule: Optional[List[AmortizationScheduleItem]] = None
        if generate_amortization:
            schedule = []
            balance = principal
            monthly_rate = annual_interest_rate / Decimal("1200.0")

            for m in range(1, tenure_months + 1):
                interest_month = round_inr(balance * monthly_rate)
                principal_month = emi - interest_month
                if principal_month > balance or m == tenure_months:
                    principal_month = balance
                    emi_actual = principal_month + interest_month
                else:
                    emi_actual = emi

                end_balance = max(Decimal("0.00"), balance - principal_month)

                schedule.append(
                    AmortizationScheduleItem(
                        month=m,
                        beginning_balance=balance,
                        emi=emi_actual,
                        principal_paid=principal_month,
                        interest_paid=interest_month,
                        ending_balance=end_balance,
                    )
                )
                balance = end_balance

        return EmiCalculationResponse(
            principal_amount=round_inr(principal),
            annual_interest_rate=annual_interest_rate,
            tenure_months=tenure_months,
            monthly_emi=emi,
            total_interest_payable=round_inr(total_interest),
            total_amount_payable=round_inr(total_payable),
            amortization_schedule=schedule,
        )

    @staticmethod
    def calculate_max_loan_from_emi_budget(
        available_monthly_emi: Decimal,
        annual_interest_rate: Decimal,
        tenure_months: int,
    ) -> Decimal:
        """Inverse EMI calculation to compute maximum affordable loan principal from monthly EMI budget.
        Formula: P = [EMI * ((1 + r)^n - 1)] / [r * (1 + r)^n]
        """
        if available_monthly_emi <= 0:
            return Decimal("0.00")
        if annual_interest_rate <= 0:
            return round_inr(available_monthly_emi * Decimal(str(tenure_months)))
        if tenure_months <= 0:
            return Decimal("0.00")

        monthly_rate = annual_interest_rate / Decimal("1200.0")
        one_plus_r = Decimal("1.0") + monthly_rate
        power_factor = Decimal(str(float(one_plus_r) ** tenure_months))

        numerator = available_monthly_emi * (power_factor - Decimal("1.0"))
        denominator = monthly_rate * power_factor

        max_principal = numerator / denominator
        return round_inr(max_principal)

    @staticmethod
    def resolve_interest_rate_by_cibil(cibil_score: int) -> Decimal:
        """Resolves benchmark auto loan interest rate for Indian retail banks based on credit score bands."""
        if cibil_score >= 800:
            return Decimal("8.65")  # Super prime (SBI / HDFC top rate)
        elif cibil_score >= 750:
            return Decimal("8.75")  # Prime
        elif cibil_score >= 700:
            return Decimal("9.25")  # Standard
        elif cibil_score >= 650:
            return Decimal("10.50") # Sub-prime
        else:
            return Decimal("12.00") # High risk
