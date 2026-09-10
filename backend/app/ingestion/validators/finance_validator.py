from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple
from app.ingestion.base import DataValidator


class FinanceDataValidator(DataValidator):
    """Validates bank loan products, interest rate percentages, credit score slabs, eligibility criteria, and fee structures."""

    def validate(self, item: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not item.get("bank_name"):
            errors.append("Missing required field 'bank_name'")
        if not item.get("product_name"):
            errors.append("Missing required field 'product_name'")

        # Product category & vehicle condition
        category = item.get("product_category", "STANDARD")
        if category not in ("STANDARD", "EV_GREEN", "PRE_OWNED", "PROMOTIONAL"):
            errors.append(f"Invalid product_category '{category}'")

        condition = item.get("vehicle_condition", "NEW")
        if condition not in ("NEW", "USED", "ANY"):
            errors.append(f"Invalid vehicle_condition '{condition}'")

        # Loan amount range
        min_loan = item.get("min_loan_amount")
        max_loan = item.get("max_loan_amount")
        if min_loan is not None and max_loan is not None:
            try:
                min_l = Decimal(str(min_loan))
                max_l = Decimal(str(max_loan))
                if min_l < 0 or max_l < 0:
                    errors.append("Loan amounts must be non-negative")
                if min_l > max_l:
                    errors.append(
                        f"min_loan_amount ({min_l}) cannot exceed max_loan_amount ({max_l})"
                    )
            except Exception:
                errors.append("Invalid decimal for loan amounts")

        # Tenure range
        min_tenure = item.get("min_tenure_months")
        max_tenure = item.get("max_tenure_months")
        if min_tenure is not None and max_tenure is not None:
            if min_tenure <= 0 or max_tenure <= 0:
                errors.append("Tenure months must be positive")
            if min_tenure > max_tenure:
                errors.append(
                    f"min_tenure_months ({min_tenure}) cannot exceed max_tenure_months ({max_tenure})"
                )

        # Rates validation (either standalone or in rates list)
        rate = item.get("annual_interest_rate")
        if rate is not None:
            try:
                dec_rate = Decimal(str(rate))
                if dec_rate < Decimal("0.0") or dec_rate > Decimal("30.0"):
                    errors.append(
                        f"Interest rate {dec_rate}% is outside realistic auto loan bounds (0% to 30%)"
                    )
            except Exception:
                errors.append(f"Invalid decimal format for annual_interest_rate: {rate}")

        min_cibil = item.get("min_cibil_score")
        max_cibil = item.get("max_cibil_score")
        if min_cibil is not None:
            if not isinstance(min_cibil, int) or min_cibil < 300 or min_cibil > 900:
                errors.append(f"min_cibil_score '{min_cibil}' must be between 300 and 900")
        if max_cibil is not None:
            if not isinstance(max_cibil, int) or max_cibil < 300 or max_cibil > 900:
                errors.append(f"max_cibil_score '{max_cibil}' must be between 300 and 900")
        if min_cibil is not None and max_cibil is not None and min_cibil > max_cibil:
            errors.append(
                f"min_cibil_score ({min_cibil}) cannot exceed max_cibil_score ({max_cibil})"
            )

        # Validate rates array if present
        rates = item.get("rates")
        if isinstance(rates, list):
            for i, r in enumerate(rates):
                r_rate = r.get("annual_interest_rate")
                if r_rate is not None:
                    try:
                        dec = Decimal(str(r_rate))
                        if dec < Decimal("0.0") or dec > Decimal("30.0"):
                            errors.append(
                                f"Rate at index {i} ({dec}%) is outside valid bounds (0% to 30%)"
                            )
                    except Exception:
                        errors.append(f"Invalid rate decimal at index {i}: {r_rate}")
                r_min_c = r.get("min_credit_score")
                r_max_c = r.get("max_credit_score")
                if r_min_c is not None and r_max_c is not None and r_min_c > r_max_c:
                    errors.append(f"Rate at index {i} has min_credit_score > max_credit_score")

        # Validate eligibility rules if present
        eligibility = item.get("eligibility_rules")
        if isinstance(eligibility, list):
            for j, e in enumerate(eligibility):
                if not e.get("rule_name"):
                    errors.append(f"Eligibility rule at index {j} missing rule_name")
                min_age = e.get("min_age_years")
                max_age = e.get("max_age_years")
                if min_age is not None and max_age is not None and min_age > max_age:
                    errors.append(f"Eligibility rule at index {j} min_age_years > max_age_years")

        # Validate fees if present
        fees = item.get("fees")
        if isinstance(fees, list):
            for k, f in enumerate(fees):
                if not f.get("fee_name"):
                    errors.append(f"Fee at index {k} missing fee_name")
                calc_method = f.get("calculation_method", "PERCENTAGE")
                if calc_method not in ("FIXED", "PERCENTAGE", "CAPPED_PERCENTAGE", "WAIVED"):
                    errors.append(
                        f"Fee at index {k} has invalid calculation_method '{calc_method}'"
                    )

        # Validate effective dates
        eff_from = item.get("effective_from")
        eff_to = item.get("effective_to")
        if eff_from and eff_to:
            try:
                dt_from = (
                    eff_from
                    if isinstance(eff_from, datetime)
                    else datetime.fromisoformat(str(eff_from).replace("Z", "+00:00"))
                )
                dt_to = (
                    eff_to
                    if isinstance(eff_to, datetime)
                    else datetime.fromisoformat(str(eff_to).replace("Z", "+00:00"))
                )
                if dt_to < dt_from:
                    errors.append(
                        f"effective_to ({dt_to}) cannot precede effective_from ({dt_from})"
                    )
            except Exception:
                pass

        return len(errors) == 0, errors
