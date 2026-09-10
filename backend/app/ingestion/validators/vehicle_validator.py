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
            errors.append(
                f"Invalid fuel_type '{fuel}'. Must be one of {sorted(self.VALID_FUEL_TYPES)}"
            )

        trans = item.get("transmission")
        if trans and trans not in self.VALID_TRANSMISSIONS:
            errors.append(
                f"Invalid transmission '{trans}'. Must be one of {sorted(self.VALID_TRANSMISSIONS)}"
            )

        body = item.get("body_type")
        if body and body not in self.VALID_BODY_TYPES:
            errors.append(
                f"Invalid body_type '{body}'. Must be one of {sorted(self.VALID_BODY_TYPES)}"
            )

        # Numeric ranges
        seating = item.get("seating_capacity")
        if seating is not None:
            if not isinstance(seating, int) or seating < 2 or seating > 12:
                errors.append(
                    f"Invalid seating_capacity '{seating}'. Must be an integer between 2 and 12"
                )

        mileage = item.get("arai_mileage_kmpl")
        if mileage is not None:
            try:
                dec_mileage = Decimal(str(mileage))
                if dec_mileage <= Decimal("0.0"):
                    errors.append(f"Fuel efficiency mileage must be positive: got {dec_mileage}")
            except Exception:
                errors.append(f"Invalid decimal format for arai_mileage_kmpl: {mileage}")

        # Engine & EV Battery checks
        fuel_val = fuel or ""
        engine_cc = item.get("engine_cc") or item.get("engine_displacement_cc")
        if engine_cc is not None:
            if not isinstance(engine_cc, int) or engine_cc < 500 or engine_cc > 8000:
                errors.append(
                    f"Invalid engine displacement '{engine_cc}'. Must be between 500cc and 8000cc"
                )
            if fuel_val == "Electric":
                errors.append("Pure electric vehicles cannot have engine_cc displacement")

        battery_kwh = item.get("battery_capacity_kwh")
        if battery_kwh is not None:
            try:
                dec_battery = Decimal(str(battery_kwh))
                if dec_battery <= Decimal("0.0") or dec_battery > Decimal("300.0"):
                    errors.append(
                        f"Invalid battery_capacity_kwh '{dec_battery}'. Must be between 0.1 and 300 kWh"
                    )
            except Exception:
                errors.append(f"Invalid decimal format for battery_capacity_kwh: {battery_kwh}")

        range_km = item.get("range_km")
        if range_km is not None:
            try:
                dec_range = Decimal(str(range_km))
                if dec_range <= Decimal("0.0") or dec_range > Decimal("1500.0"):
                    errors.append(f"Invalid range_km '{dec_range}'. Must be between 1 and 1500 km")
            except Exception:
                errors.append(f"Invalid decimal format for range_km: {range_km}")

        # Power & Torque
        power_bhp = item.get("engine_power_bhp") or item.get("max_power_bhp")
        if power_bhp is not None:
            try:
                dec_power = Decimal(str(power_bhp))
                if dec_power <= Decimal("0.0") or dec_power > Decimal("2000.0"):
                    errors.append(f"Invalid power '{dec_power}'. Must be between 1 and 2000 bhp")
            except Exception:
                errors.append(f"Invalid decimal format for power_bhp: {power_bhp}")

        torque_nm = item.get("torque_nm") or item.get("max_torque_nm")
        if torque_nm is not None:
            try:
                dec_torque = Decimal(str(torque_nm))
                if dec_torque <= Decimal("0.0") or dec_torque > Decimal("3000.0"):
                    errors.append(f"Invalid torque '{dec_torque}'. Must be between 1 and 3000 Nm")
            except Exception:
                errors.append(f"Invalid decimal format for torque_nm: {torque_nm}")

        boot_space = item.get("boot_space_l")
        if boot_space is not None:
            if not isinstance(boot_space, int) or boot_space < 0 or boot_space > 2500:
                errors.append(f"Invalid boot_space_l '{boot_space}'. Must be between 0 and 2500 L")

        return len(errors) == 0, errors

    def classify_status(self, is_valid: bool, has_official_source: bool = False) -> str:
        """Classifies verification status based on validation and source provenance."""
        if not is_valid:
            return "REJECTED"
        if has_official_source:
            return "VERIFIED"
        return "FORMAT_VALID"
