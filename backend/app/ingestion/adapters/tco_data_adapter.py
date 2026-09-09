from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.core.ingestion_constants import DataSourceType, IngestionEntityType, VerificationStatus
from app.ingestion.base import (
    CanonicalMapper,
    DataFetcher,
    DataNormalizer,
    DataParser,
    DataValidator,
    DataSourceAdapter,
)
from app.ingestion.validators.tco_validator import TCOValidator


# =============================================================================
# 1. FUEL PRICE DATA FIXTURES & ADAPTER (PPAC / IOCL / BPCL / HPCL)
# =============================================================================

PPAC_FUEL_PRICE_FIXTURES: List[Dict[str, Any]] = [
    # --- Bengaluru (KA) ---
    {
        "tco_category": "fuel_price",
        "fuel_type": "PETROL",
        "state_code": "KA",
        "city_name": "Bengaluru",
        "price_per_unit": "102.86",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "PPAC-BLR-PETROL-202603",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "fuel_price",
        "fuel_type": "PETROL",
        "state_code": "KA",
        "city_name": "Bengaluru",
        "price_per_unit": "101.94",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2025-06-01T00:00:00Z",
        "effective_from": "2025-06-01T00:00:00Z",
        "source_record_id": "PPAC-BLR-PETROL-202506",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "fuel_price",
        "fuel_type": "DIESEL",
        "state_code": "KA",
        "city_name": "Bengaluru",
        "price_per_unit": "88.94",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "PPAC-BLR-DIESEL-202603",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "fuel_price",
        "fuel_type": "CNG",
        "state_code": "KA",
        "city_name": "Bengaluru",
        "price_per_unit": "82.50",
        "unit": "kg",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "GAIL-BLR-CNG-202603",
        "verification_status": "VERIFIED",
    },

    # --- Delhi (DL) ---
    {
        "tco_category": "fuel_price",
        "fuel_type": "PETROL",
        "state_code": "DL",
        "city_name": "Delhi",
        "price_per_unit": "94.72",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "PPAC-DEL-PETROL-202603",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "fuel_price",
        "fuel_type": "DIESEL",
        "state_code": "DL",
        "city_name": "Delhi",
        "price_per_unit": "87.62",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "PPAC-DEL-DIESEL-202603",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "fuel_price",
        "fuel_type": "CNG",
        "state_code": "DL",
        "city_name": "Delhi",
        "price_per_unit": "75.09",
        "unit": "kg",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "IGL-DEL-CNG-202603",
        "verification_status": "VERIFIED",
    },

    # --- Mumbai (MH) ---
    {
        "tco_category": "fuel_price",
        "fuel_type": "PETROL",
        "state_code": "MH",
        "city_name": "Mumbai",
        "price_per_unit": "103.44",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "PPAC-MUM-PETROL-202603",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "fuel_price",
        "fuel_type": "DIESEL",
        "state_code": "MH",
        "city_name": "Mumbai",
        "price_per_unit": "89.97",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "PPAC-MUM-DIESEL-202603",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "fuel_price",
        "fuel_type": "CNG",
        "state_code": "MH",
        "city_name": "Mumbai",
        "price_per_unit": "79.00",
        "unit": "kg",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "MGL-MUM-CNG-202603",
        "verification_status": "VERIFIED",
    },

    # --- Chennai (TN) ---
    {
        "tco_category": "fuel_price",
        "fuel_type": "PETROL",
        "state_code": "TN",
        "city_name": "Chennai",
        "price_per_unit": "100.75",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "PPAC-CHE-PETROL-202603",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "fuel_price",
        "fuel_type": "DIESEL",
        "state_code": "TN",
        "city_name": "Chennai",
        "price_per_unit": "92.34",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "PPAC-CHE-DIESEL-202603",
        "verification_status": "VERIFIED",
    },

    # --- Hyderabad (TS) ---
    {
        "tco_category": "fuel_price",
        "fuel_type": "PETROL",
        "state_code": "TS",
        "city_name": "Hyderabad",
        "price_per_unit": "107.41",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "PPAC-HYD-PETROL-202603",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "fuel_price",
        "fuel_type": "DIESEL",
        "state_code": "TS",
        "city_name": "Hyderabad",
        "price_per_unit": "95.65",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "PPAC-HYD-DIESEL-202603",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "fuel_price",
        "fuel_type": "CNG",
        "state_code": "TS",
        "city_name": "Hyderabad",
        "price_per_unit": "89.00",
        "unit": "kg",
        "currency": "INR",
        "observed_date": "2026-03-01T00:00:00Z",
        "effective_from": "2026-03-01T00:00:00Z",
        "source_record_id": "BGL-HYD-CNG-202603",
        "verification_status": "VERIFIED",
    },

    # --- National Baseline Fallback ---
    {
        "tco_category": "fuel_price",
        "fuel_type": "PETROL",
        "state_code": None,
        "city_name": None,
        "price_per_unit": "102.50",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2026-01-01T00:00:00Z",
        "effective_from": "2026-01-01T00:00:00Z",
        "source_record_id": "PPAC-NATIONAL-PETROL-202601",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "fuel_price",
        "fuel_type": "DIESEL",
        "state_code": None,
        "city_name": None,
        "price_per_unit": "88.50",
        "unit": "Litre",
        "currency": "INR",
        "observed_date": "2026-01-01T00:00:00Z",
        "effective_from": "2026-01-01T00:00:00Z",
        "source_record_id": "PPAC-NATIONAL-DIESEL-202601",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "fuel_price",
        "fuel_type": "CNG",
        "state_code": None,
        "city_name": None,
        "price_per_unit": "85.00",
        "unit": "kg",
        "currency": "INR",
        "observed_date": "2026-01-01T00:00:00Z",
        "effective_from": "2026-01-01T00:00:00Z",
        "source_record_id": "PPAC-NATIONAL-CNG-202601",
        "verification_status": "VERIFIED",
    },
]


class TCOFixtureFetcher(DataFetcher):
    def __init__(self, fixtures: List[Dict[str, Any]]):
        self._fixtures = fixtures

    async def fetch(self, **kwargs) -> List[Dict[str, Any]]:
        return self._fixtures


class TCODictParser(DataParser):
    def parse(self, raw_payload: Any) -> Dict[str, Any]:
        if isinstance(raw_payload, dict):
            return dict(raw_payload)
        return {"data": raw_payload}


class TCONormalizer(DataNormalizer):
    def normalize(self, parsed_item: Dict[str, Any]) -> Dict[str, Any]:
        norm = dict(parsed_item)
        if "observed_date" in norm and isinstance(norm["observed_date"], str):
            norm["observed_date"] = datetime.fromisoformat(norm["observed_date"].replace("Z", "+00:00"))
        if "effective_from" in norm and isinstance(norm["effective_from"], str):
            norm["effective_from"] = datetime.fromisoformat(norm["effective_from"].replace("Z", "+00:00"))
        if "effective_to" in norm and isinstance(norm["effective_to"], str):
            norm["effective_to"] = datetime.fromisoformat(norm["effective_to"].replace("Z", "+00:00"))

        for dec_field in ["price_per_unit", "rate_per_kwh", "fixed_charge_per_month", "annual_base_cost", "cost_per_km", "year_2_factor", "year_3_factor", "year_4_factor", "year_5_factor", "year_1_depreciation_pct", "year_2_depreciation_pct", "year_3_depreciation_pct", "year_4_depreciation_pct", "year_5_depreciation_pct"]:
            if dec_field in norm and norm[dec_field] is not None:
                norm[dec_field] = Decimal(str(norm[dec_field]))

        return norm


class TCOCanonicalMapper(CanonicalMapper):
    def map_to_canonical(self, validated_item: Dict[str, Any]) -> Dict[str, Any]:
        return dict(validated_item)


class PPACFuelPriceAdapter(DataSourceAdapter):
    """Adapter for official retail fuel price observations published by PPAC and Oil Marketing Companies."""

    def __init__(self):
        self.source_name = "Petroleum Planning & Analysis Cell (PPAC) / OMC Daily Published Rates"
        self.source_slug = "fuel_prices"
        self.source_type = DataSourceType.OFFICIAL_GOVERNMENT
        self.dataset_name = "fuel_prices"
        self.entity_type = IngestionEntityType.FUEL_PRICE
        self.trust_level = 98
        self.provider_type = "official_government"
        self.organization = "Ministry of Petroleum and Natural Gas, Government of India"
        self.base_url = "https://www.ppac.gov.in"

        self.fetcher = TCOFixtureFetcher(PPAC_FUEL_PRICE_FIXTURES)
        self.parser = TCODictParser()
        self.normalizer = TCONormalizer()
        self.validator = TCOValidator()
        self.mapper = TCOCanonicalMapper()

    def get_fetcher(self) -> DataFetcher:
        return self.fetcher

    def get_parser(self) -> DataParser:
        return self.parser

    def get_normalizer(self) -> DataNormalizer:
        return self.normalizer

    def get_validator(self) -> DataValidator:
        return self.validator

    def get_mapper(self) -> CanonicalMapper:
        return self.mapper

    def get_source_record_id(self, item: Dict[str, Any]) -> str:
        return item.get("source_record_id") or f"PPAC-{item.get('state_code', 'NAT')}-{item.get('fuel_type')}"


# =============================================================================
# 2. STATE ELECTRICITY TARIFF FIXTURES & ADAPTER (SERCs / DISCOMs)
# =============================================================================

SERC_ELECTRICITY_TARIFF_FIXTURES: List[Dict[str, Any]] = [
    {
        "tco_category": "electricity_tariff",
        "tariff_type": "DOMESTIC_SLAB",
        "state_code": "KA",
        "discom_name": "BESCOM (Bangalore Electricity Supply Company)",
        "rate_per_kwh": "7.00",
        "fixed_charge_per_month": "110.00",
        "currency": "INR",
        "effective_from": "2025-04-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "electricity_tariff",
        "tariff_type": "EV_SPECIAL_TARIFF",
        "state_code": "KA",
        "discom_name": "BESCOM LT-6 EV Charging Tariff",
        "rate_per_kwh": "5.50",
        "fixed_charge_per_month": "70.00",
        "currency": "INR",
        "effective_from": "2025-04-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "electricity_tariff",
        "tariff_type": "DOMESTIC_SLAB",
        "state_code": "DL",
        "discom_name": "Delhi Electricity Regulatory Commission (DERC / TPDDL / BRPL)",
        "rate_per_kwh": "6.50",
        "fixed_charge_per_month": "150.00",
        "currency": "INR",
        "effective_from": "2025-04-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "electricity_tariff",
        "tariff_type": "EV_SPECIAL_TARIFF",
        "state_code": "DL",
        "discom_name": "DERC EV Public & Dedicated Home Tariff",
        "rate_per_kwh": "4.50",
        "fixed_charge_per_month": "0.00",
        "currency": "INR",
        "effective_from": "2025-04-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "electricity_tariff",
        "tariff_type": "DOMESTIC_SLAB",
        "state_code": "MH",
        "discom_name": "MSEDCL (Maharashtra State Electricity Distribution Co)",
        "rate_per_kwh": "8.90",
        "fixed_charge_per_month": "128.00",
        "currency": "INR",
        "effective_from": "2025-04-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "electricity_tariff",
        "tariff_type": "EV_SPECIAL_TARIFF",
        "state_code": "MH",
        "discom_name": "MERC EV Special Charging Tariff",
        "rate_per_kwh": "6.00",
        "fixed_charge_per_month": "0.00",
        "currency": "INR",
        "effective_from": "2025-04-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "electricity_tariff",
        "tariff_type": "DOMESTIC_SLAB",
        "state_code": "TN",
        "discom_name": "TANGEDCO (Tamil Nadu Generation and Distribution Corp)",
        "rate_per_kwh": "6.50",
        "fixed_charge_per_month": "0.00",
        "currency": "INR",
        "effective_from": "2025-04-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "electricity_tariff",
        "tariff_type": "DOMESTIC_SLAB",
        "state_code": "TS",
        "discom_name": "TSSPDCL (Southern Power Distribution Co of Telangana)",
        "rate_per_kwh": "7.50",
        "fixed_charge_per_month": "100.00",
        "currency": "INR",
        "effective_from": "2025-04-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
]


class StateDiscomTariffAdapter(DataSourceAdapter):
    """Adapter for state electricity regulatory commission published consumer & EV tariffs."""

    def __init__(self):
        self.source_name = "State Electricity Regulatory Commissions (SERC) Tariff Orders"
        self.source_slug = "electricity_tariffs"
        self.source_type = DataSourceType.OFFICIAL_GOVERNMENT
        self.dataset_name = "electricity_tariffs"
        self.entity_type = IngestionEntityType.ELECTRICITY_TARIFF
        self.trust_level = 95
        self.provider_type = "official_government"
        self.organization = "Forum of Regulators & State Electricity Regulatory Commissions"
        self.base_url = "https://cercind.gov.in"

        self.fetcher = TCOFixtureFetcher(SERC_ELECTRICITY_TARIFF_FIXTURES)
        self.parser = TCODictParser()
        self.normalizer = TCONormalizer()
        self.validator = TCOValidator()
        self.mapper = TCOCanonicalMapper()

    def get_fetcher(self) -> DataFetcher:
        return self.fetcher

    def get_parser(self) -> DataParser:
        return self.parser

    def get_normalizer(self) -> DataNormalizer:
        return self.normalizer

    def get_validator(self) -> DataValidator:
        return self.validator

    def get_mapper(self) -> CanonicalMapper:
        return self.mapper

    def get_source_record_id(self, item: Dict[str, Any]) -> str:
        return item.get("source_record_id") or f"SERC-{item.get('state_code')}-{item.get('tariff_type')}"


# =============================================================================
# 3. MAINTENANCE BENCHMARKS FIXTURES & ADAPTER (ARAI / INDUSTRY BENCHMARKS)
# =============================================================================

MAINTENANCE_COST_FIXTURES: List[Dict[str, Any]] = [
    {
        "tco_category": "maintenance",
        "powertrain": "PETROL",
        "segment": "HATCHBACK",
        "annual_base_cost": "5500.00",
        "cost_per_km": "0.3500",
        "service_interval_km": 10000,
        "service_interval_months": 12,
        "effective_from": "2025-01-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "maintenance",
        "powertrain": "PETROL",
        "segment": "SUV",
        "annual_base_cost": "7500.00",
        "cost_per_km": "0.4500",
        "service_interval_km": 10000,
        "service_interval_months": 12,
        "effective_from": "2025-01-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "maintenance",
        "powertrain": "PETROL",
        "segment": None,  # Default fallback
        "annual_base_cost": "6000.00",
        "cost_per_km": "0.4000",
        "service_interval_km": 10000,
        "service_interval_months": 12,
        "effective_from": "2025-01-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "maintenance",
        "powertrain": "DIESEL",
        "segment": None,
        "annual_base_cost": "8000.00",
        "cost_per_km": "0.5000",
        "service_interval_km": 10000,
        "service_interval_months": 12,
        "effective_from": "2025-01-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "maintenance",
        "powertrain": "CNG",
        "segment": None,
        "annual_base_cost": "6500.00",
        "cost_per_km": "0.4500",
        "service_interval_km": 10000,
        "service_interval_months": 12,
        "effective_from": "2025-01-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "maintenance",
        "powertrain": "ELECTRIC",
        "segment": None,
        "annual_base_cost": "3500.00",  # EV ~45% lower routine maintenance
        "cost_per_km": "0.2500",
        "service_interval_km": 15000,
        "service_interval_months": 12,
        "effective_from": "2025-01-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
    {
        "tco_category": "maintenance",
        "powertrain": "HYBRID",
        "segment": None,
        "annual_base_cost": "7000.00",
        "cost_per_km": "0.4000",
        "service_interval_km": 10000,
        "service_interval_months": 12,
        "effective_from": "2025-01-01T00:00:00Z",
        "verification_status": "VERIFIED",
    },
]


class IndustryMaintenanceBenchmarkAdapter(DataSourceAdapter):
    """Adapter for automotive routine & scheduled maintenance benchmark schedules."""

    def __init__(self):
        self.source_name = "Industry Standard Service Cost Benchmark (ARAI & OEM Manuals)"
        self.source_slug = "maintenance_costs"
        self.source_type = DataSourceType.MANUAL_REVIEW
        self.dataset_name = "maintenance_costs"
        self.entity_type = IngestionEntityType.MAINTENANCE_COST
        self.trust_level = 90
        self.provider_type = "industry_benchmark"
        self.organization = "Automotive Research Association of India (ARAI)"
        self.base_url = "https://www.araiindia.com"

        self.fetcher = TCOFixtureFetcher(MAINTENANCE_COST_FIXTURES)
        self.parser = TCODictParser()
        self.normalizer = TCONormalizer()
        self.validator = TCOValidator()
        self.mapper = TCOCanonicalMapper()

    def get_fetcher(self) -> DataFetcher:
        return self.fetcher

    def get_parser(self) -> DataParser:
        return self.parser

    def get_normalizer(self) -> DataNormalizer:
        return self.normalizer

    def get_validator(self) -> DataValidator:
        return self.validator

    def get_mapper(self) -> CanonicalMapper:
        return self.mapper

    def get_source_record_id(self, item: Dict[str, Any]) -> str:
        return item.get("source_record_id") or f"MAINT-{item.get('powertrain')}-{item.get('segment', 'ALL')}"


# =============================================================================
# 4. INSURANCE RENEWAL BENCHMARKS FIXTURES & ADAPTER (IRDAI / GIC)
# =============================================================================

INSURANCE_RENEWAL_FIXTURES: List[Dict[str, Any]] = [
    {
        "tco_category": "insurance_renewal",
        "fuel_type": None,
        "segment": None,
        "year_2_factor": "0.6500",  # Own Damage only (3-Yr TP already bundled in Year 1)
        "year_3_factor": "0.6000",  # Own Damage only
        "year_4_factor": "0.7500",  # Own Damage + 1-Yr TP Renewal
        "year_5_factor": "0.7000",  # Own Damage + 1-Yr TP Renewal
        "effective_from": "2025-01-01T00:00:00Z",
        "verification_status": "VERIFIED",
    }
]


class IRDAIInsuranceRenewalAdapter(DataSourceAdapter):
    """Adapter for IRDAI Motor Tariff Guidelines & General Insurance Council renewal schedules."""

    def __init__(self):
        self.source_name = "IRDAI Motor Tariff Guidelines & General Insurance Council"
        self.source_slug = "insurance_data"
        self.source_type = DataSourceType.OFFICIAL_GOVERNMENT
        self.dataset_name = "insurance_data"
        self.entity_type = IngestionEntityType.INSURANCE_BENCHMARK
        self.trust_level = 95
        self.provider_type = "official_regulator"
        self.organization = "Insurance Regulatory and Development Authority of India (IRDAI)"
        self.base_url = "https://irdai.gov.in"

        self.fetcher = TCOFixtureFetcher(INSURANCE_RENEWAL_FIXTURES)
        self.parser = TCODictParser()
        self.normalizer = TCONormalizer()
        self.validator = TCOValidator()
        self.mapper = TCOCanonicalMapper()

    def get_fetcher(self) -> DataFetcher:
        return self.fetcher

    def get_parser(self) -> DataParser:
        return self.parser

    def get_normalizer(self) -> DataNormalizer:
        return self.normalizer

    def get_validator(self) -> DataValidator:
        return self.validator

    def get_mapper(self) -> CanonicalMapper:
        return self.mapper

    def get_source_record_id(self, item: Dict[str, Any]) -> str:
        return item.get("source_record_id") or "IRDAI-MOTOR-RENEWAL-BENCHMARK"


# =============================================================================
# 5. DEPRECIATION CURVES FIXTURES & ADAPTER (FADA / INDUSTRY VALUATION)
# =============================================================================

DEPRECIATION_FIXTURES: List[Dict[str, Any]] = [
    {
        "tco_category": "depreciation",
        "powertrain": None,
        "segment": None,
        "year_1_depreciation_pct": "15.00",
        "year_2_depreciation_pct": "25.00",
        "year_3_depreciation_pct": "35.00",
        "year_4_depreciation_pct": "43.00",
        "year_5_depreciation_pct": "50.00",
        "methodology": "EMPIRICAL_MARKET_RESALE",
        "effective_from": "2025-01-01T00:00:00Z",
        "verification_status": "VERIFIED",
    }
]


class FADADepreciationBenchmarkAdapter(DataSourceAdapter):
    """Adapter for Federation of Automobile Dealers Associations (FADA) used vehicle valuation curves."""

    def __init__(self):
        self.source_name = "Federation of Automobile Dealers Associations (FADA) Used Vehicle Valuation Index"
        self.source_slug = "depreciation_data"
        self.source_type = DataSourceType.MANUAL_REVIEW
        self.dataset_name = "depreciation_data"
        self.entity_type = IngestionEntityType.DEPRECIATION_BENCHMARK
        self.trust_level = 90
        self.provider_type = "industry_association"
        self.organization = "Federation of Automobile Dealers Associations (FADA)"
        self.base_url = "https://fada.in"

        self.fetcher = TCOFixtureFetcher(DEPRECIATION_FIXTURES)
        self.parser = TCODictParser()
        self.normalizer = TCONormalizer()
        self.validator = TCOValidator()
        self.mapper = TCOCanonicalMapper()

    def get_fetcher(self) -> DataFetcher:
        return self.fetcher

    def get_parser(self) -> DataParser:
        return self.parser

    def get_normalizer(self) -> DataNormalizer:
        return self.normalizer

    def get_validator(self) -> DataValidator:
        return self.validator

    def get_mapper(self) -> CanonicalMapper:
        return self.mapper

    def get_source_record_id(self, item: Dict[str, Any]) -> str:
        return item.get("source_record_id") or "FADA-USED-CAR-DEPRECIATION-BENCHMARK"
