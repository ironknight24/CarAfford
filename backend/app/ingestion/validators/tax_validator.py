from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple
from app.ingestion.base import DataValidator


class TaxRuleDataValidator(DataValidator):
    """Validates state RTO tax percentages, brackets, calculation types, and safe formula definitions."""

    VALID_TAX_TYPES = {"ROAD_TAX", "REGISTRATION_FEE", "GREEN_CESS", "FASTAG", "HYPOTHECATION", "OTHER"}
    VALID_CALCULATION_TYPES = {"PERCENTAGE", "FIXED_AMOUNT", "SLAB_TIERED", "FORMULA_AST"}

    def validate(self, item: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        if not item.get("state_code") and not item.get("state_id"):
            errors.append("Tax rule must specify either 'state_code' or 'state_id'")

        tax_type = item.get("tax_type")
        if not tax_type or tax_type not in self.VALID_TAX_TYPES:
            errors.append(f"Invalid tax_type '{tax_type}'. Must be one of {sorted(self.VALID_TAX_TYPES)}")

        calc_type = item.get("calculation_type")
        if not calc_type or calc_type not in self.VALID_CALCULATION_TYPES:
            errors.append(f"Invalid calculation_type '{calc_type}'. Must be one of {sorted(self.VALID_CALCULATION_TYPES)}")

        rate_val = item.get("base_rate_percent")
        if rate_val is not None:
            try:
                dec_rate = Decimal(str(rate_val))
                if dec_rate < Decimal("0.0") or dec_rate > Decimal("50.0"):
                    errors.append(f"Tax rate {dec_rate}% is outside plausible bounds (0% to 50%)")
            except Exception:
                errors.append(f"Invalid decimal format for base_rate_percent: {rate_val}")

        # Check for non-executable AST formulas
        formula = item.get("formula_ast")
        if formula and not isinstance(formula, dict):
            errors.append("formula_ast must be a valid JSON dictionary/AST representation, not arbitrary code")

        return len(errors) == 0, errors
