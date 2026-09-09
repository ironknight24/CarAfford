from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

from app.models.finance import LoanEligibilityRule, LoanProduct


class LoanEligibilityEvaluatorService:
    """Evaluates applicant financing parameters against bank pre-qualification criteria.
    
    IMPORTANT: This evaluates estimated pre-qualification parameters (income, credit score, LTV, tenure),
    and strictly labels results as 'ESTIMATED_ELIGIBLE' rather than official loan approval.
    """

    @classmethod
    def evaluate_product_eligibility(
        cls,
        loan_product: LoanProduct,
        loan_amount: Decimal,
        on_road_price: Decimal,
        tenure_months: int,
        credit_score: Optional[int] = None,
        monthly_income: Optional[Decimal] = None,
        applicant_age: Optional[int] = None,
        employment_type: Optional[str] = None,
        calculation_date: Optional[datetime] = None,
    ) -> Tuple[bool, str, List[str]]:
        """Evaluates eligibility for a loan product.
        
        Returns:
            Tuple of (is_eligible: bool, status: str, reasons: List[str])
            Status values: 'ESTIMATED_ELIGIBLE', 'MARGINAL', 'ESTIMATED_INELIGIBLE'
        """
        reasons: List[str] = []
        is_eligible = True
        calc_date = calculation_date or datetime.now(timezone.utc)
        if calc_date.tzinfo is None:
            calc_date = calc_date.replace(tzinfo=timezone.utc)

        user_cibil = credit_score if credit_score is not None else 750
        user_age = applicant_age if applicant_age is not None else 30
        user_emp = (employment_type or "SALARIED").upper()

        # 1. Product Loan Amount Bounds
        if loan_amount < loan_product.min_loan_amount:
            is_eligible = False
            reasons.append(
                f"Requested loan amount ₹{loan_amount:,.2f} is below minimum ₹{loan_product.min_loan_amount:,.2f}"
            )
        if loan_amount > loan_product.max_loan_amount:
            is_eligible = False
            reasons.append(
                f"Requested loan amount ₹{loan_amount:,.2f} exceeds maximum product cap ₹{loan_product.max_loan_amount:,.2f}"
            )

        # 2. Product Tenure Bounds
        if tenure_months < loan_product.min_tenure_months:
            is_eligible = False
            reasons.append(
                f"Tenure of {tenure_months} months is below minimum allowed {loan_product.min_tenure_months} months"
            )
        if tenure_months > loan_product.max_tenure_months:
            is_eligible = False
            reasons.append(
                f"Tenure of {tenure_months} months exceeds maximum allowed {loan_product.max_tenure_months} months"
            )

        # 3. Loan-to-Value (LTV) Check
        if on_road_price > 0:
            ltv = (loan_amount / on_road_price) * Decimal("100.0")
            if ltv > loan_product.max_ltv_percent:
                is_eligible = False
                reasons.append(
                    f"Required financing ({ltv:.1f}% LTV) exceeds bank maximum LTV cap ({loan_product.max_ltv_percent:.1f}%)"
                )

        # 4. Custom Eligibility Rules
        rules = loan_product.eligibility_rules or []
        for rule in rules:
            if not rule.active:
                continue
            eff_from = rule.effective_from.replace(tzinfo=timezone.utc) if rule.effective_from.tzinfo is None else rule.effective_from
            if eff_from > calc_date:
                continue
            if rule.effective_to is not None:
                eff_to = rule.effective_to.replace(tzinfo=timezone.utc) if rule.effective_to.tzinfo is None else rule.effective_to
                if eff_to < calc_date:
                    continue

            # Income Rule
            if rule.min_monthly_income is not None and monthly_income is not None:
                if monthly_income < rule.min_monthly_income:
                    is_eligible = False
                    reasons.append(
                        f"Monthly take-home income ₹{monthly_income:,.2f} is below required threshold ₹{rule.min_monthly_income:,.2f}"
                    )

            # Credit Score Rule
            if rule.min_credit_score is not None and user_cibil < rule.min_credit_score:
                is_eligible = False
                reasons.append(
                    f"Credit score {user_cibil} is below minimum threshold of {rule.min_credit_score}"
                )

            # Age Rule
            if rule.min_age_years is not None and user_age < rule.min_age_years:
                is_eligible = False
                reasons.append(f"Applicant age ({user_age}) is below minimum requirement ({rule.min_age_years} years)")
            if rule.max_age_years is not None and user_age > rule.max_age_years:
                is_eligible = False
                reasons.append(f"Applicant age ({user_age}) exceeds maximum maturity cap ({rule.max_age_years} years)")

            # Employment Type Rule
            if rule.allowed_employment_types:
                allowed = [t.strip().upper() for t in rule.allowed_employment_types.split(",")]
                if user_emp not in allowed and "ANY" not in allowed:
                    is_eligible = False
                    reasons.append(f"Employment type '{user_emp}' is not accepted for this scheme")

        status = "ESTIMATED_ELIGIBLE"
        if not is_eligible:
            status = "ESTIMATED_INELIGIBLE"
        elif user_cibil < 700:
            status = "MARGINAL"
            reasons.append("Credit score is in fair band (650-699); additional documentation or guarantor may be requested")

        return is_eligible, status, reasons
