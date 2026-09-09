from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.finance import InterestRate, LoanProduct
from app.services.finance_service import FinanceService


class LoanRateResolverService:
    """Pure domain service for deterministic, location-independent, temporal interest rate resolution.
    
    Precedence Order:
    1. Highest Specificity Match:
       Exact Credit Score + Tenure + Loan Amount + Employment Tier
       > Exact Credit Score + Tenure
       > Exact Credit Score
       > General Product Benchmark Rate
    2. Rule Priority (higher integer value takes precedence)
    3. Lowest Annual Interest Rate (best consumer pricing)
    4. Most recently effective date
    5. Highest primary key ID
    """

    @classmethod
    def resolve_product_interest_rate(
        cls,
        loan_product: LoanProduct,
        loan_amount: Decimal,
        tenure_months: int,
        credit_score: Optional[int] = None,
        employment_type: Optional[str] = None,
        calculation_date: Optional[datetime] = None,
    ) -> Tuple[Decimal, str, Optional[InterestRate]]:
        """Resolves the best applicable interest rate for a given loan product.
        
        Returns:
            Tuple of (annual_interest_rate: Decimal, rate_type: str, matched_rate_record: Optional[InterestRate])
        """
        calc_date = calculation_date or datetime.now(timezone.utc)
        if calc_date.tzinfo is None:
            calc_date = calc_date.replace(tzinfo=timezone.utc)

        user_cibil = credit_score if credit_score is not None else 750
        candidates = loan_product.interest_rates or []

        # 1. Filter candidates by temporal validity and active status
        valid_rates: List[InterestRate] = []
        for r in candidates:
            if not r.active:
                continue
            eff_from = r.effective_from
            if eff_from.tzinfo is None:
                eff_from = eff_from.replace(tzinfo=timezone.utc)
            if eff_from > calc_date:
                continue
            if r.effective_to is not None:
                eff_to = r.effective_to
                if eff_to.tzinfo is None:
                    eff_to = eff_to.replace(tzinfo=timezone.utc)
                if eff_to < calc_date:
                    continue
            valid_rates.append(r)

        # 2. Score candidate matches
        scored_matches: List[Tuple[int, Decimal, datetime, int, InterestRate]] = []

        for r in valid_rates:
            match_score = 0

            # 2.1 Credit Score check
            has_cibil_condition = r.min_credit_score is not None or r.max_credit_score is not None
            if has_cibil_condition:
                if r.min_credit_score is not None and user_cibil < r.min_credit_score:
                    continue
                if r.max_credit_score is not None and user_cibil > r.max_credit_score:
                    continue
                match_score += 500  # High specificity weight

            # 2.2 Tenure check
            has_tenure_condition = r.min_tenure_months is not None or r.max_tenure_months is not None
            if has_tenure_condition:
                if r.min_tenure_months is not None and tenure_months < r.min_tenure_months:
                    continue
                if r.max_tenure_months is not None and tenure_months > r.max_tenure_months:
                    continue
                match_score += 300

            # 2.3 Loan Amount check
            has_amount_condition = r.min_loan_amount is not None or r.max_loan_amount is not None
            if has_amount_condition:
                if r.min_loan_amount is not None and loan_amount < r.min_loan_amount:
                    continue
                if r.max_loan_amount is not None and loan_amount > r.max_loan_amount:
                    continue
                match_score += 200

            # 2.4 Employment type check
            if r.employment_type and r.employment_type.upper() != "ANY":
                if employment_type and employment_type.upper() == r.employment_type.upper():
                    match_score += 100
                elif employment_type and employment_type.upper() != r.employment_type.upper():
                    continue

            # 2.5 Priority weighting
            match_score += ((r.priority if r.priority is not None else 100) * 10)

            eff_dt = r.effective_from if r.effective_from.tzinfo else r.effective_from.replace(tzinfo=timezone.utc)
            r_id = r.id if r.id is not None else 0
            scored_matches.append((match_score, r.annual_interest_rate, eff_dt, r_id, r))

        # 3. Sort by:
        # - match_score DESC (highest specificity & priority)
        # - annual_interest_rate ASC (lowest customer rate)
        # - effective_from DESC (latest date)
        # - id DESC (latest PK)
        if scored_matches:
            scored_matches.sort(
                key=lambda x: (
                    -x[0],
                    x[1],
                    -x[2].timestamp(),
                    -x[3],
                )
            )
            best = scored_matches[0][4]
            return best.annual_interest_rate, best.rate_type, best

        # 4. Fallback check: Legacy interest_rate_slabs
        if loan_product.interest_rate_slabs:
            for slab in loan_product.interest_rate_slabs:
                if slab.min_cibil_score <= user_cibil <= slab.max_cibil_score:
                    rate_type = "FIXED" if slab.is_fixed else "FLOATING"
                    return slab.default_interest_rate, rate_type, None

        # 5. Default benchmark rate based on CIBIL
        benchmark_rate = FinanceService.resolve_interest_rate_by_cibil(user_cibil)
        return benchmark_rate, "FLOATING", None
