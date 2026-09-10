import re
from typing import Any, Dict, List, Tuple
from app.ingestion.base import DataValidator

# Standard recognized 2-letter Indian States and Union Territories (ISO 3166-2:IN / MoRTH)
RECOGNIZED_INDIAN_STATE_CODES = {
    "AN",
    "AP",
    "AR",
    "AS",
    "BR",
    "CH",
    "CG",
    "DD",
    "DH",
    "DL",
    "GA",
    "GJ",
    "HR",
    "HP",
    "JK",
    "JH",
    "KA",
    "KL",
    "LA",
    "LD",
    "MP",
    "MH",
    "MN",
    "ML",
    "MZ",
    "NL",
    "OD",
    "PB",
    "PY",
    "RJ",
    "SK",
    "TN",
    "TS",
    "TR",
    "UK",
    "UP",
    "WB",
}


class LocationDataValidator(DataValidator):
    """Validates state codes, city names, RTO codes, and hierarchical consistency."""

    STRICT_RTO_CODE_PATTERN = re.compile(r"^[A-Z]{2}-\d{2}$")
    FLEXIBLE_RTO_CODE_PATTERN = re.compile(r"^[A-Z]{2}[-\s]?[0-9]{1,2}[A-Z]{0,3}$", re.IGNORECASE)
    STATE_CODE_PATTERN = re.compile(r"^[A-Z]{2}$")

    def validate(self, item: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        # 1. State validation
        state_code = item.get("state_code")
        if state_code:
            clean_code = str(state_code).strip().upper()
            if not self.STATE_CODE_PATTERN.match(clean_code):
                errors.append(
                    f"Invalid state_code '{state_code}'. Must be 2 uppercase alphabetic characters (e.g. 'KA', 'DL')"
                )
            elif clean_code not in RECOGNIZED_INDIAN_STATE_CODES:
                errors.append(
                    f"Unrecognized state_code '{state_code}'. Must be a valid Indian State/UT code."
                )

        state_name = item.get("state_name")
        if state_name is not None and not str(state_name).strip():
            errors.append("State name cannot be empty when provided.")

        region_type = item.get("region_type")
        if region_type and str(region_type).upper() not in {"STATE", "UNION_TERRITORY"}:
            errors.append(
                f"Invalid region_type '{region_type}'. Must be 'STATE' or 'UNION_TERRITORY'."
            )

        # 2. City validation
        city_name = item.get("city_name")
        if city_name is not None and not str(city_name).strip():
            errors.append("City name cannot be empty when provided.")

        city_tier = item.get("tier")
        if city_tier and str(city_tier) not in {"Tier 1", "Tier 2", "Tier 3"}:
            errors.append(
                f"Invalid city tier '{city_tier}'. Expected 'Tier 1', 'Tier 2', or 'Tier 3'."
            )

        # 3. RTO validation
        rto_code = item.get("rto_code")
        if rto_code:
            clean_rto = str(rto_code).strip().upper()
            if not self.FLEXIBLE_RTO_CODE_PATTERN.match(clean_rto):
                errors.append(
                    f"Invalid rto_code '{rto_code}'. Must match standard Indian RTO pattern (e.g. 'KA-01', 'DL-04')"
                )

            # 4. Hierarchical consistency: RTO prefix matches parent state code
            if state_code:
                rto_prefix = clean_rto[:2]
                clean_state = str(state_code).strip().upper()
                if rto_prefix != clean_state:
                    errors.append(
                        f"Hierarchical mismatch: RTO code '{clean_rto}' prefix '{rto_prefix}' does not match state code '{clean_state}'."
                    )

        rto_name = item.get("rto_name")
        if rto_name is not None and not str(rto_name).strip():
            errors.append("RTO name cannot be empty when provided.")

        return len(errors) == 0, errors

    @classmethod
    def classify_status(cls, rto_code: str, is_authoritative: bool = False) -> str:
        """Classifies RTO code status as AUTHORITATIVE_MATCH, FORMAT_VALID, or UNVERIFIED."""
        clean = str(rto_code).strip().upper()
        if not cls.STRICT_RTO_CODE_PATTERN.match(clean):
            return "UNVERIFIED"
        return "AUTHORITATIVE_MATCH" if is_authoritative else "FORMAT_VALID"
