from decimal import Decimal
from typing import Any, Dict, List, Tuple
from app.ingestion.base import DataValidator


class TCOValidator(DataValidator):
    """Ingestion validator for TCO input datasets including fuel prices, electricity tariffs, maintenance benchmarks, insurance renewal factors, and depreciation curves."""

    @classmethod
    def validate_fuel_price(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        fuel_type = data.get("fuel_type", "").upper()
        if fuel_type not in ["PETROL", "DIESEL", "CNG"]:
            errors.append(f"Invalid fuel_type '{fuel_type}'. Must be PETROL, DIESEL, or CNG.")

        raw_price = data.get("price_per_unit")
        if raw_price is None:
            errors.append("price_per_unit is required.")
        else:
            try:
                price = Decimal(str(raw_price))
                if price < Decimal("20.00") or price > Decimal("250.00"):
                    errors.append(
                        f"price_per_unit {price} out of realistic bounds [20.00, 250.00]."
                    )
            except Exception:
                errors.append(f"Invalid price_per_unit '{raw_price}'.")

        unit = data.get("unit", "")
        if unit not in ["Litre", "kg", "litre", "KG"]:
            errors.append(f"Invalid fuel unit '{unit}'. Must be 'Litre' or 'kg'.")

        if not data.get("observed_date"):
            errors.append("observed_date is required for fuel price observations.")

        return len(errors) == 0, errors

    @classmethod
    def validate_electricity_tariff(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        tariff_type = data.get("tariff_type", "")
        if tariff_type not in ["DOMESTIC_SLAB", "EV_SPECIAL_TARIFF", "COMMERCIAL"]:
            errors.append(f"Invalid tariff_type '{tariff_type}'.")

        raw_rate = data.get("rate_per_kwh")
        if raw_rate is None:
            errors.append("rate_per_kwh is required.")
        else:
            try:
                rate = Decimal(str(raw_rate))
                if rate < Decimal("1.00") or rate > Decimal("30.00"):
                    errors.append(f"rate_per_kwh {rate} out of bounds [1.00, 30.00].")
            except Exception:
                errors.append(f"Invalid rate_per_kwh '{raw_rate}'.")

        return len(errors) == 0, errors

    @classmethod
    def validate_maintenance_benchmark(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        powertrain = data.get("powertrain", "").upper()
        if powertrain not in ["PETROL", "DIESEL", "CNG", "ELECTRIC", "HYBRID"]:
            errors.append(f"Invalid powertrain '{powertrain}'.")

        raw_base = data.get("annual_base_cost")
        if raw_base is None:
            errors.append("annual_base_cost is required.")
        else:
            try:
                base = Decimal(str(raw_base))
                if base < Decimal("500.00") or base > Decimal("50000.00"):
                    errors.append(
                        f"annual_base_cost {base} out of realistic bounds [500.00, 50000.00]."
                    )
            except Exception:
                errors.append(f"Invalid annual_base_cost '{raw_base}'.")

        raw_km = data.get("cost_per_km")
        if raw_km is None:
            errors.append("cost_per_km is required.")
        else:
            try:
                km = Decimal(str(raw_km))
                if km < Decimal("0.05") or km > Decimal("5.00"):
                    errors.append(f"cost_per_km {km} out of bounds [0.05, 5.00].")
            except Exception:
                errors.append(f"Invalid cost_per_km '{raw_km}'.")

        return len(errors) == 0, errors

    @classmethod
    def validate_insurance_renewal(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        for year in [2, 3, 4, 5]:
            key = f"year_{year}_factor"
            raw_factor = data.get(key)
            if raw_factor is None:
                errors.append(f"{key} is required.")
            else:
                try:
                    factor = Decimal(str(raw_factor))
                    if factor < Decimal("0.10") or factor > Decimal("1.50"):
                        errors.append(f"{key} {factor} out of realistic bounds [0.10, 1.50].")
                except Exception:
                    errors.append(f"Invalid {key} '{raw_factor}'.")

        return len(errors) == 0, errors

    @classmethod
    def validate_depreciation(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []
        prev_pct = Decimal("0.00")
        for year in [1, 2, 3, 4, 5]:
            key = f"year_{year}_depreciation_pct"
            raw_pct = data.get(key)
            if raw_pct is None:
                errors.append(f"{key} is required.")
            else:
                try:
                    pct = Decimal(str(raw_pct))
                    if pct < Decimal("1.00") or pct > Decimal("95.00"):
                        errors.append(f"{key} {pct} out of realistic bounds [1.00, 95.00].")
                    if pct <= prev_pct:
                        errors.append(
                            f"{key} ({pct}%) must be greater than previous year ({prev_pct}%)."
                        )
                    prev_pct = pct
                except Exception:
                    errors.append(f"Invalid {key} '{raw_pct}'.")

        return len(errors) == 0, errors

    def validate(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        category = record.get("tco_category", "")
        if category == "fuel_price":
            return self.validate_fuel_price(record)
        elif category == "electricity_tariff":
            return self.validate_electricity_tariff(record)
        elif category == "maintenance":
            return self.validate_maintenance_benchmark(record)
        elif category == "insurance_renewal":
            return self.validate_insurance_renewal(record)
        elif category == "depreciation":
            return self.validate_depreciation(record)
        else:
            return False, [f"Unknown TCO category: '{category}'"]
