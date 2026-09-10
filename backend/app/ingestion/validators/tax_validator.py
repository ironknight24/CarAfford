from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Tuple
from app.ingestion.base import DataValidator


class TaxRuleDataValidator(DataValidator):
    """Validates state/city/RTO statutory motor vehicle tax percentages, brackets, calculation types, and safe formula definitions."""

    VALID_TAX_TYPES = {
        "ROAD_TAX",
        "MOTOR_VEHICLE_TAX",
        "REGISTRATION_FEE",
        "SMART_CARD_FEE",
        "HSRP_FEE",
        "HYPOTHECATION_FEE",
        "CESS",
        "SURCHARGE",
        "GREEN_TAX",
        "FASTAG_FEE",
        "OTHER",
    }

    VALID_CALCULATION_METHODS = {
        "FIXED",
        "PERCENTAGE",
        "BRACKETED",
        "FORMULA",
    }

    VALID_RULE_CATEGORIES = {
        "TAX",
        "REGISTRATION",
        "FEE",
        "CESS",
    }

    VALID_VEHICLE_TYPES = {
        "CAR",
        "TWO_WHEELER",
        "COMMERCIAL",
        "ANY",
    }

    VALID_USAGE_TYPES = {
        "PRIVATE",
        "COMMERCIAL",
        "ANY",
    }

    VALID_FORMULA_TYPES = {
        "BH_SERIES",
    }

    def validate(self, item: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        # 1. State / Jurisdiction Identification
        state_code = item.get("state_code")
        state_id = item.get("state_id")
        state_name = item.get("state_name")
        if not state_code and not state_id and not state_name:
            errors.append("Tax rule must specify either 'state_code', 'state_id', or 'state_name'")

        # 2. Rule Name & Category
        name = item.get("name")
        if not name or not isinstance(name, str) or not name.strip():
            errors.append("Tax rule must have a non-empty 'name'")

        rule_cat = item.get("rule_category", "TAX")
        if rule_cat not in self.VALID_RULE_CATEGORIES:
            errors.append(
                f"Invalid rule_category '{rule_cat}'. Must be one of {sorted(self.VALID_RULE_CATEGORIES)}"
            )

        # 3. Tax Type Validation
        tax_type = item.get("tax_type")
        if not tax_type or tax_type not in self.VALID_TAX_TYPES:
            errors.append(
                f"Invalid tax_type '{tax_type}'. Must be one of {sorted(self.VALID_TAX_TYPES)}"
            )

        # 4. Calculation Method Validation
        calc_method = item.get("calculation_method", "PERCENTAGE")
        if not calc_method or calc_method not in self.VALID_CALCULATION_METHODS:
            errors.append(
                f"Invalid calculation_method '{calc_method}'. Must be one of {sorted(self.VALID_CALCULATION_METHODS)}"
            )

        # 5. Rate & Fixed Amount Validation
        rate_val = item.get("rate")
        if rate_val is not None:
            try:
                dec_rate = Decimal(str(rate_val))
                if dec_rate < Decimal("0.0"):
                    errors.append(f"Tax rate ({dec_rate}%) cannot be negative")
                elif dec_rate > Decimal("50.0"):
                    errors.append(
                        f"Tax rate ({dec_rate}%) exceeds maximum plausible threshold (50.0%)"
                    )
            except Exception:
                errors.append(f"Invalid decimal format for rate: {rate_val}")

        fixed_val = item.get("fixed_amount")
        if fixed_val is not None:
            try:
                dec_fixed = Decimal(str(fixed_val))
                if dec_fixed < Decimal("0.0"):
                    errors.append(f"Fixed amount (₹{dec_fixed}) cannot be negative")
            except Exception:
                errors.append(f"Invalid decimal format for fixed_amount: {fixed_val}")

        # 6. Bracket Validation (for BRACKETED calculation method)
        brackets = item.get("brackets")
        if calc_method == "BRACKETED":
            if not brackets or not isinstance(brackets, list) or len(brackets) == 0:
                errors.append("BRACKETED calculation_method requires a non-empty 'brackets' list")
            else:
                prev_max: Decimal = Decimal("-1.00")
                for i, b in enumerate(brackets):
                    b_order = b.get("bracket_order", i + 1)
                    if b_order < 1:
                        errors.append(f"Bracket order must be >= 1 at index {i}")

                    min_v_raw = b.get("minimum_value")
                    if min_v_raw is None:
                        errors.append(f"Bracket at index {i} missing 'minimum_value'")
                        continue
                    try:
                        min_v = Decimal(str(min_v_raw))
                        if min_v < Decimal("0.00"):
                            errors.append(
                                f"Bracket minimum_value (₹{min_v}) cannot be negative at index {i}"
                            )
                    except Exception:
                        errors.append(
                            f"Invalid decimal for minimum_value at index {i}: {min_v_raw}"
                        )
                        continue

                    max_v = None
                    max_v_raw = b.get("maximum_value")
                    if max_v_raw is not None:
                        try:
                            max_v = Decimal(str(max_v_raw))
                            if max_v <= min_v:
                                errors.append(
                                    f"Bracket maximum_value (₹{max_v}) must be greater than minimum_value (₹{min_v}) at index {i}"
                                )
                        except Exception:
                            errors.append(
                                f"Invalid decimal for maximum_value at index {i}: {max_v_raw}"
                            )
                            continue

                    # Rate / Fixed amount in bracket
                    b_rate = b.get("rate")
                    if b_rate is not None:
                        try:
                            dec_b_rate = Decimal(str(b_rate))
                            if dec_b_rate < Decimal("0.0") or dec_b_rate > Decimal("50.0"):
                                errors.append(
                                    f"Bracket rate ({dec_b_rate}%) out of bounds (0% - 50%) at index {i}"
                                )
                        except Exception:
                            errors.append(f"Invalid decimal rate in bracket at index {i}")

                    b_fixed = b.get("fixed_amount")
                    if b_fixed is not None:
                        try:
                            dec_b_fixed = Decimal(str(b_fixed))
                            if dec_b_fixed < Decimal("0.0"):
                                errors.append(
                                    f"Bracket fixed_amount cannot be negative at index {i}"
                                )
                        except Exception:
                            errors.append(f"Invalid decimal fixed_amount in bracket at index {i}")

                    # Overlapping / Gap validation
                    if i > 0:
                        if prev_max != Decimal("-1.00") and min_v < prev_max:
                            errors.append(
                                f"Overlapping bracket detected: bracket {i} min ({min_v}) < previous max ({prev_max})"
                            )

                    if max_v is not None:
                        prev_max = max_v
                    else:
                        # Open ended bracket must be the last bracket
                        if i != len(brackets) - 1:
                            errors.append(
                                f"Unbounded bracket (maximum_value=None) must be the final bracket, found at index {i}"
                            )
                        prev_max = Decimal("999999999999.00")

        # 7. Safe Formula AST Validation (for FORMULA calculation method)
        if calc_method == "FORMULA":
            formula = item.get("formula_definition")
            if not formula or not isinstance(formula, dict):
                errors.append(
                    "FORMULA calculation_method requires a safe structured JSON 'formula_definition' dictionary"
                )
            else:
                f_type = formula.get("type")
                if not f_type or f_type not in self.VALID_FORMULA_TYPES:
                    errors.append(
                        f"Formula type '{f_type}' is not supported. Must be one of {sorted(self.VALID_FORMULA_TYPES)}"
                    )

                # Validate parameters for BH_SERIES
                if f_type == "BH_SERIES":
                    factor = formula.get("factor", 1.25)
                    try:
                        dec_f = Decimal(str(factor))
                        if dec_f <= Decimal("0.0") or dec_f > Decimal("5.0"):
                            errors.append(
                                f"BH_SERIES factor ({dec_f}) outside valid range (0 to 5.0)"
                            )
                    except Exception:
                        errors.append(f"Invalid decimal for BH_SERIES factor: {factor}")

                    tenure = formula.get("payment_tenure_years", 2)
                    if not isinstance(tenure, int) or tenure < 1 or tenure > 15:
                        errors.append(
                            f"BH_SERIES payment_tenure_years ({tenure}) must be integer between 1 and 15"
                        )

        # 8. Effective Date Range Consistency
        eff_from = item.get("effective_from")
        if not eff_from:
            errors.append("Tax rule must have an 'effective_from' date")
        else:
            eff_from_dt = None
            if isinstance(eff_from, str):
                try:
                    eff_from_dt = datetime.fromisoformat(eff_from.replace("Z", "+00:00"))
                except Exception:
                    errors.append(f"Invalid ISO datetime string for effective_from: {eff_from}")
            elif isinstance(eff_from, datetime):
                eff_from_dt = eff_from

            eff_to = item.get("effective_to")
            if eff_to is not None:
                eff_to_dt = None
                if isinstance(eff_to, str):
                    try:
                        eff_to_dt = datetime.fromisoformat(eff_to.replace("Z", "+00:00"))
                    except Exception:
                        errors.append(f"Invalid ISO datetime string for effective_to: {eff_to}")
                elif isinstance(eff_to, datetime):
                    eff_to_dt = eff_to

                if eff_from_dt and eff_to_dt and eff_to_dt < eff_from_dt:
                    errors.append(
                        f"effective_to ({eff_to_dt}) cannot be earlier than effective_from ({eff_from_dt})"
                    )

        # 9. Vehicle Category & Usage Applicability
        veh_type = item.get("vehicle_type", "CAR")
        if veh_type not in self.VALID_VEHICLE_TYPES:
            errors.append(
                f"Invalid vehicle_type '{veh_type}'. Must be one of {sorted(self.VALID_VEHICLE_TYPES)}"
            )

        usage_type = item.get("usage_type", "PRIVATE")
        if usage_type not in self.VALID_USAGE_TYPES:
            errors.append(
                f"Invalid usage_type '{usage_type}'. Must be one of {sorted(self.VALID_USAGE_TYPES)}"
            )

        return len(errors) == 0, errors
