from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Tuple

from app.core.ingestion_constants import (
    DataSourceType,
    IngestionEntityType,
    VerificationStatus,
)
from app.ingestion.base import (
    CanonicalMapper,
    DataFetcher,
    DataNormalizer,
    DataParser,
    DataSourceAdapter,
    DataValidator,
)
from app.ingestion.validators.vehicle_validator import VehicleDataValidator
from app.ingestion.validators.pricing_validator import PriceDataValidator
from app.ingestion.validators.tax_validator import TaxRuleDataValidator
from app.ingestion.validators.finance_validator import FinanceDataValidator
from app.ingestion.validators.location_validator import LocationDataValidator

# =============================================================================
# DEMO VEHICLE ADAPTER
# =============================================================================


class DemoVehicleFetcher(DataFetcher):
    """Fetches seeded/demo vehicle entries for pipeline execution."""

    async def fetch(self, **kwargs) -> List[Dict[str, Any]]:
        # Structured demo payload simulating external OEM/Parivahan data feed
        return [
            {
                "source_record_id": "DEMO-PUNCH-PURE-01",
                "manufacturer": "Tata Motors",
                "model": "Punch",
                "variant": "Punch Pure 1.2 MT",
                "fuel": "PETROL",
                "transmission": "MANUAL",
                "body": "SUV",
                "seating": 5,
                "mileage": "20.09",
                "safety_stars": 5,
                "airbags": 2,
                "price": "612900.00",
                "effective_from": "2026-01-01T00:00:00Z",
            },
            {
                "source_record_id": "DEMO-NEXON-SMART-01",
                "manufacturer": "Tata Motors",
                "model": "Nexon",
                "variant": "Nexon Smart 1.2 Revotron 6MT",
                "fuel": "PETROL",
                "transmission": "MANUAL",
                "body": "SUV",
                "seating": 5,
                "mileage": "17.44",
                "safety_stars": 5,
                "airbags": 6,
                "price": "814990.00",
                "effective_from": "2026-01-01T00:00:00Z",
            },
            {
                "source_record_id": "DEMO-SWIFT-LXI-01",
                "manufacturer": "Maruti Suzuki",
                "model": "Swift",
                "variant": "Swift LXi 1.2 5MT",
                "fuel": "PETROL",
                "transmission": "MANUAL",
                "body": "HATCHBACK",
                "seating": 5,
                "mileage": "24.8",
                "safety_stars": 4,
                "airbags": 6,
                "price": "649000.00",
                "effective_from": "2026-01-01T00:00:00Z",
            },
            {
                "source_record_id": "DEMO-CRETA-E-01",
                "manufacturer": "Hyundai",
                "model": "Creta",
                "variant": "Creta E 1.5 Petrol 6MT",
                "fuel": "PETROL",
                "transmission": "MANUAL",
                "body": "SUV",
                "seating": 5,
                "mileage": "17.4",
                "safety_stars": 3,
                "airbags": 6,
                "price": "1099900.00",
                "effective_from": "2026-01-01T00:00:00Z",
            },
        ]


class DemoVehicleParser(DataParser):
    def parse(self, raw_payload: Any) -> Dict[str, Any]:
        return {
            "source_record_id": raw_payload.get("source_record_id"),
            "manufacturer_raw": raw_payload.get("manufacturer"),
            "model_raw": raw_payload.get("model"),
            "variant_raw": raw_payload.get("variant"),
            "fuel_raw": raw_payload.get("fuel"),
            "transmission_raw": raw_payload.get("transmission"),
            "body_raw": raw_payload.get("body"),
            "seating_raw": raw_payload.get("seating"),
            "mileage_raw": raw_payload.get("mileage"),
            "safety_raw": raw_payload.get("safety_stars"),
            "airbags_raw": raw_payload.get("airbags"),
            "price_raw": raw_payload.get("price"),
            "effective_from_raw": raw_payload.get("effective_from"),
        }


class DemoVehicleNormalizer(DataNormalizer):
    def normalize(self, parsed_item: Dict[str, Any]) -> Dict[str, Any]:
        # Capitalize and clean string representations
        fuel_map = {
            "PETROL": "Petrol",
            "DIESEL": "Diesel",
            "CNG": "CNG",
            "ELECTRIC": "Electric",
            "EV": "Electric",
            "HYBRID": "Hybrid",
        }
        trans_map = {
            "MANUAL": "Manual",
            "AUTOMATIC": "Automatic",
            "AMT": "AMT",
            "CVT": "CVT",
            "DCT": "DCT",
        }
        body_map = {
            "SUV": "SUV",
            "SEDAN": "Sedan",
            "HATCHBACK": "Hatchback",
            "MUV": "MUV",
        }

        fuel = fuel_map.get(str(parsed_item.get("fuel_raw")).upper(), parsed_item.get("fuel_raw"))
        trans = trans_map.get(
            str(parsed_item.get("transmission_raw")).upper(), parsed_item.get("transmission_raw")
        )
        body = body_map.get(str(parsed_item.get("body_raw")).upper(), parsed_item.get("body_raw"))

        return {
            "source_record_id": parsed_item.get("source_record_id"),
            "manufacturer_name": str(parsed_item.get("manufacturer_raw", "")).strip(),
            "model_name": str(parsed_item.get("model_raw", "")).strip(),
            "variant_name": str(parsed_item.get("variant_raw", "")).strip(),
            "fuel_type": fuel,
            "transmission": trans,
            "body_type": body,
            "seating_capacity": int(parsed_item.get("seating_raw", 5)),
            "arai_mileage_kmpl": Decimal(str(parsed_item.get("mileage_raw", "18.0"))),
            "safety_rating_stars": (
                int(parsed_item.get("safety_raw", 0))
                if parsed_item.get("safety_raw") is not None
                else None
            ),
            "airbags_count": int(parsed_item.get("airbags_raw", 2)),
            "ex_showroom_price": Decimal(str(parsed_item.get("price_raw", "500000.00"))),
            "effective_from": parsed_item.get("effective_from_raw"),
            "verification_status": VerificationStatus.DEMO.value,
        }


class DemoVehicleMapper(CanonicalMapper):
    def map_to_canonical(self, validated_item: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "manufacturer_name": validated_item["manufacturer_name"],
            "model_name": validated_item["model_name"],
            "variant_name": validated_item["variant_name"],
            "fuel_type": validated_item["fuel_type"],
            "transmission": validated_item["transmission"],
            "body_type": validated_item["body_type"],
            "seating_capacity": validated_item["seating_capacity"],
            "arai_mileage_kmpl": validated_item["arai_mileage_kmpl"],
            "safety_rating_stars": validated_item["safety_rating_stars"],
            "airbags_count": validated_item["airbags_count"],
            "ex_showroom_price": validated_item["ex_showroom_price"],
            "effective_from": validated_item["effective_from"],
            "verification_status": VerificationStatus.DEMO.value,
        }


class DemoDataSourceAdapter(DataSourceAdapter):
    """Concrete demo adapter proving pipeline execution for demonstration datasets."""

    source_slug = "demo-seed-catalogue"
    source_name = "CarAfford Demonstration Seed Catalogue"
    source_type = DataSourceType.DEMO_SEED
    dataset_name = "vehicles_catalogue"
    entity_type = IngestionEntityType.VEHICLE

    def get_fetcher(self) -> DataFetcher:
        return DemoVehicleFetcher()

    def get_parser(self) -> DataParser:
        return DemoVehicleParser()

    def get_normalizer(self) -> DataNormalizer:
        return DemoVehicleNormalizer()

    def get_validator(self) -> DataValidator:
        return VehicleDataValidator()

    def get_mapper(self) -> CanonicalMapper:
        return DemoVehicleMapper()
