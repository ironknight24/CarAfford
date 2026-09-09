from decimal import Decimal
from typing import Any, Dict, List, Tuple
from app.ingestion.base import DataValidator


class FinanceDataValidator(DataValidator):
    """Validates bank loan products, interest rate percentages, credit score slabs, and fee structures."""

    def validate(self, item: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not item.get("bank_name"):
            errors.append("Missing required field 'bank_name'")
        if not item.get("product_name"):
            errors.append("Missing required field 'product_name'")

        rate = item.get("annual_interest_rate")
        if rate is not None:
            try:
                dec_rate = Decimal(str(rate))
                if dec_rate < Decimal("0.0") or dec_rate > Decimal("30.0"):
                    errors.append(f"Interest rate {dec_rate}% is outside realistic auto loan bounds (0% to 30%)")
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
            errors.append(f"min_cibil_score ({min_cibil}) cannot exceed max_cibil_score ({max_cibil})")

        return len(errors) == 0, errors
