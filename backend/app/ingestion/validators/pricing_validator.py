from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple
from app.ingestion.base import DataValidator


class PriceDataValidator(DataValidator):
    """Validates ex-showroom currency values, effective date spans, and uniqueness constraints."""

    MIN_PRICE = Decimal("100000.00")      # ₹1 Lakh min benchmark
    MAX_PRICE = Decimal("50000000.00")    # ₹5 Crore max benchmark

    def validate(self, item: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        price_val = item.get("ex_showroom_price")
        if price_val is None:
            errors.append("Missing required field 'ex_showroom_price'")
        else:
            try:
                dec_price = Decimal(str(price_val))
                if dec_price <= Decimal("0.00"):
                    errors.append(f"Price must be strictly positive: got ₹{dec_price}")
                elif dec_price < self.MIN_PRICE or dec_price > self.MAX_PRICE:
                    errors.append(f"Price ₹{dec_price:,.2f} is outside reasonable automotive bounds (₹1L - ₹5Cr)")
            except Exception:
                errors.append(f"Invalid currency format for ex_showroom_price: {price_val}")

        # Effective date validation
        eff_from = item.get("effective_from")
        eff_to = item.get("effective_to")

        if eff_from is None:
            errors.append("Missing required field 'effective_from'")
        elif isinstance(eff_from, str):
            try:
                datetime.fromisoformat(eff_from.replace("Z", "+00:00"))
            except Exception:
                errors.append(f"Invalid ISO format for effective_from: {eff_from}")

        if eff_to is not None:
            if isinstance(eff_to, str):
                try:
                    to_dt = datetime.fromisoformat(eff_to.replace("Z", "+00:00"))
                    if isinstance(eff_from, datetime) and eff_from >= to_dt:
                        errors.append(f"effective_from ({eff_from}) must be strictly earlier than effective_to ({to_dt})")
                except Exception:
                    errors.append(f"Invalid ISO format for effective_to: {eff_to}")
            elif isinstance(eff_from, datetime) and isinstance(eff_to, datetime):
                if eff_from >= eff_to:
                    errors.append(f"effective_from ({eff_from}) must be strictly earlier than effective_to ({eff_to})")

        return len(errors) == 0, errors
