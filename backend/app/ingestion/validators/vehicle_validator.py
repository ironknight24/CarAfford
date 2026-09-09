from decimal import Decimal
from typing import Any, Dict, List, Tuple
from app.ingestion.base import DataValidator


class VehicleDataValidator(DataValidator):
    """Validates technical specs, fuel types, seating capacity, and safety attributes for vehicles."""

    VALID_FUEL_TYPES = {"Petrol", "Diesel", "CNG", "Electric", "Hybrid", "LPG"}
    VALID_TRANSMISSIONS = {"Manual", "Automatic", "AMT", "CVT", "DCT", "AT", "iMT"}
    VALID_BODY_TYPES = {"Hatchback", "Sedan", "SUV", "MUV", "Coupe", "Convertible", "Pickup", "Van"}

    def validate(self, item: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        # Required fields
        if not item.get("manufacturer_name"):
            errors.append("Missing required field 'manufacturer_name'")
        if not item.get("model_name"):
            errors.append("Missing required field 'model_name'")
        if not item.get("variant_name"):
            errors.append("Missing required field 'variant_name'")

        # Enums
        fuel = item.get("fuel_type")
        if fuel and fuel not in self.VALID_FUEL_TYPES:
            errors.append(f"Invalid fuel_type '{fuel}'. Must be one of {sorted(self.VALID_FUEL_TYPES)}")

        trans = item.get("transmission")
        if trans and trans not in self.VALID_TRANSMISSIONS:
            errors.append(f"Invalid transmission '{trans}'. Must be one of {sorted(self.VALID_TRANSMISSIONS)}")

        body = item.get("body_type")
        if body and body not in self.VALID_BODY_TYPES:
            errors.append(f"Invalid body_type '{body}'. Must be one of {sorted(self.VALID_BODY_TYPES)}")

        # Numeric ranges
        seating = item.get("seating_capacity")
        if seating is not None:
            if not isinstance(seating, int) or seating < 2 or seating > 12:
                errors.append(f"Invalid seating_capacity '{seating}'. Must be an integer between 2 and 12")

        mileage = item.get("arai_mileage_kmpl")
        if mileage is not None:
            try:
                dec_mileage = Decimal(str(mileage))
                if dec_mileage <= Decimal("0.0"):
                    errors.append(f"Fuel efficiency mileage must be positive: got {dec_mileage}")
            except Exception:
                errors.append(f"Invalid decimal format for arai_mileage_kmpl: {mileage}")

        safety = item.get("safety_rating_stars")
        if safety is not None:
            if not isinstance(safety, int) or safety < 0 or safety > 5:
                errors.append(f"Invalid safety_rating_stars '{safety}'. Must be between 0 and 5")

        airbags = item.get("airbags_count")
        if airbags is not None:
            if not isinstance(airbags, int) or airbags < 0 or airbags > 20:
                errors.append(f"Invalid airbags_count '{airbags}'. Must be non-negative")

        return len(errors) == 0, errors
