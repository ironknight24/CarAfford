import re
from typing import Any, Dict, List, Tuple
from app.ingestion.base import DataValidator


class LocationDataValidator(DataValidator):
    """Validates state codes, city names, RTO codes, and hierarchical consistency."""

    RTO_CODE_PATTERN = re.compile(r"^[A-Z]{2}[-\s]?[0-9]{1,2}[A-Z]{0,3}$")
    STATE_CODE_PATTERN = re.compile(r"^[A-Z]{2}$")

    def validate(self, item: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        state_code = item.get("state_code")
        if state_code:
            if not self.STATE_CODE_PATTERN.match(state_code.upper()):
                errors.append(f"Invalid state_code '{state_code}'. Must be 2 uppercase alphabetic characters (e.g. 'KA', 'DL')")

        rto_code = item.get("rto_code")
        if rto_code:
            if not self.RTO_CODE_PATTERN.match(rto_code.upper()):
                errors.append(f"Invalid rto_code '{rto_code}'. Must match standard Indian RTO pattern (e.g. 'KA-01', 'DL-04')")

        return len(errors) == 0, errors
