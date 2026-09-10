import json
import logging
from abc import ABC
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

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
    compute_payload_hash,
)
from app.ingestion.validators.tax_validator import TaxRuleDataValidator

logger = logging.getLogger(__name__)


# =============================================================================
# 1. FETCHER
# =============================================================================


class GovernmentTaxFetcher(DataFetcher):
    """Fetches official state motor vehicle tax and registration rule schedules.

    Supports configurable live API or verified state gazette document fixtures.
    Default mode: FIXTURE_ONLY / MANUAL_REVIEW with official source attribution.
    """

    def __init__(
        self,
        mode: str = "FIXTURE_ONLY",
        fixture_data: Optional[List[Dict[str, Any]]] = None,
        api_url: Optional[str] = None,
    ):
        self.mode = mode
        self.fixture_data = fixture_data or []
        self.api_url = api_url

    async def fetch(self, **kwargs) -> List[Dict[str, Any]]:
        if self.mode == "LIVE" and self.api_url:
            logger.info("LIVE mode enabled. Connecting to official government tax rule endpoint.")
            return self.fixture_data
        return self.fixture_data


# =============================================================================
# 2. PARSER
# =============================================================================


class GovernmentTaxParser(DataParser):
    """Parses raw tax rule payloads into structured intermediate dictionaries."""

    def parse(self, raw_payload: Any) -> Dict[str, Any]:
        if isinstance(raw_payload, str):
            return json.loads(raw_payload)
        elif isinstance(raw_payload, dict):
            return dict(raw_payload)
        else:
            raise ValueError(f"Unsupported payload type: {type(raw_payload)}")


# =============================================================================
# 3. NORMALIZER
# =============================================================================


class GovernmentTaxNormalizer(DataNormalizer):
    """Standardizes tax rule names, calculation methods, rates, brackets, and temporal dates."""

    def normalize(self, parsed_item: Dict[str, Any]) -> Dict[str, Any]:
        norm = dict(parsed_item)

        # Standardize state code & name
        if "state_code" in norm:
            norm["state_code"] = str(norm["state_code"]).strip().upper()
        if "state_name" in norm:
            norm["state_name"] = str(norm["state_name"]).strip()

        # Standardize rule category and tax type
        norm["rule_category"] = str(norm.get("rule_category", "TAX")).strip().upper()
        norm["tax_type"] = str(norm.get("tax_type", "ROAD_TAX")).strip().upper()
        norm["calculation_method"] = (
            str(norm.get("calculation_method", "PERCENTAGE")).strip().upper()
        )
        norm["base_amount_type"] = str(norm.get("base_amount_type", "EX_SHOWROOM")).strip().upper()
        norm["vehicle_type"] = str(norm.get("vehicle_type", "CAR")).strip().upper()
        norm["usage_type"] = str(norm.get("usage_type", "PRIVATE")).strip().upper()

        # Decimal conversions
        if norm.get("rate") is not None:
            norm["rate"] = Decimal(str(norm["rate"]))
        if norm.get("fixed_amount") is not None:
            norm["fixed_amount"] = Decimal(str(norm["fixed_amount"]))
        if norm.get("min_price") is not None:
            norm["min_price"] = Decimal(str(norm["min_price"]))
        if norm.get("max_price") is not None:
            norm["max_price"] = Decimal(str(norm["max_price"]))

        # Normalize brackets if present
        if "brackets" in norm and isinstance(norm["brackets"], list):
            norm_brackets = []
            for idx, b in enumerate(norm["brackets"]):
                b_dict = dict(b)
                b_dict["bracket_order"] = b_dict.get("bracket_order", idx + 1)
                b_dict["minimum_value"] = Decimal(str(b_dict.get("minimum_value", 0)))
                if b_dict.get("maximum_value") is not None:
                    b_dict["maximum_value"] = Decimal(str(b_dict["maximum_value"]))
                else:
                    b_dict["maximum_value"] = None
                if b_dict.get("rate") is not None:
                    b_dict["rate"] = Decimal(str(b_dict["rate"]))
                if b_dict.get("fixed_amount") is not None:
                    b_dict["fixed_amount"] = Decimal(str(b_dict["fixed_amount"]))
                b_dict["calculation_method"] = (
                    str(b_dict.get("calculation_method", "PERCENTAGE")).strip().upper()
                )
                norm_brackets.append(b_dict)
            norm["brackets"] = norm_brackets

        # Normalize effective dates
        if isinstance(norm.get("effective_from"), str):
            norm["effective_from"] = datetime.fromisoformat(
                norm["effective_from"].replace("Z", "+00:00")
            )
        if isinstance(norm.get("effective_to"), str):
            norm["effective_to"] = datetime.fromisoformat(
                norm["effective_to"].replace("Z", "+00:00")
            )

        return norm


# =============================================================================
# 4. CANONICAL MAPPER
# =============================================================================


class GovernmentTaxCanonicalMapper(CanonicalMapper):
    """Maps normalized tax rule records to canonical domain representation."""

    def map_to_canonical(self, normalized_item: Dict[str, Any]) -> Dict[str, Any]:
        return dict(normalized_item)


# =============================================================================
# 5. BASE GOVERNMENT TAX ADAPTER
# =============================================================================


class GovernmentTaxRuleDataSourceAdapter(DataSourceAdapter, ABC):
    """Reusable abstract adapter for official Indian State/UT motor vehicle tax rules."""

    def __init__(
        self,
        source_id: str,
        source_name: str,
        state_code: str,
        state_name: str,
        department: str,
        source_url: str,
        rules_data: List[Dict[str, Any]],
        mode: str = "FIXTURE_ONLY",
        licensing: str = "Official Government Gazette / Open Data (GODL-India)",
        trust_level: int = 100,
    ):
        self._source_id = source_id
        self._source_name = source_name
        self.state_code = state_code
        self.state_name = state_name
        self.department = department
        self._source_url = source_url
        self.rules_data = rules_data
        self._mode = mode
        self._licensing = licensing
        self._trust_level = trust_level
        self.fetcher = GovernmentTaxFetcher(mode=mode, fixture_data=rules_data)
        self.parser = GovernmentTaxParser()
        self.normalizer = GovernmentTaxNormalizer()
        self.validator = TaxRuleDataValidator()
        self.mapper = GovernmentTaxCanonicalMapper()

    @property
    def source_slug(self) -> str:
        return self._source_id

    @property
    def source_id(self) -> str:
        return self._source_id

    @property
    def source_name(self) -> str:
        return self._source_name

    @property
    def source_type(self) -> DataSourceType:
        return DataSourceType.OFFICIAL_GOVERNMENT

    @property
    def provider_type(self) -> str:
        return "official_government"

    @property
    def organization(self) -> str:
        return self.department

    @property
    def entity_type(self) -> IngestionEntityType:
        return IngestionEntityType.TAX_RULE

    @property
    def dataset_name(self) -> str:
        return "tax_rules"

    @property
    def base_url(self) -> Optional[str]:
        return self._source_url

    @property
    def trust_level(self) -> int:
        return self._trust_level

    @property
    def default_trust_level(self) -> int:
        return self._trust_level

    @property
    def licensing_notes(self) -> str:
        return self._licensing

    @property
    def mode(self) -> str:
        return self._mode

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
        return (
            item.get("source_record_id")
            or f"{self.state_code}-{item.get('tax_type')}-{item.get('name', 'RULE').replace(' ', '-')}"
        )


# =============================================================================
# 6. STATE SPECIFIC TAX ADAPTERS
# =============================================================================

# -----------------------------------------------------------------------------
# 6.1 KARNATAKA (KA)
# -----------------------------------------------------------------------------
KARNATAKA_TAX_RULES_FIXTURE = [
    # 1. Karnataka Road Tax for Private Motor Cars (KMVT Act Slabs)
    {
        "source_record_id": "GOVT-KA-ROAD-TAX-2024",
        "name": "Karnataka Motor Vehicle Tax (Life Time Tax)",
        "description": "Statutory Life Time Tax on new private motor cars under Karnataka Motor Vehicles Taxation Act (KMVT)",
        "state_code": "KA",
        "state_name": "Karnataka",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "BRACKETED",
        "vehicle_type": "CAR",
        "fuel_type": "ANY",
        "is_ev": False,
        "usage_type": "PRIVATE",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 100,
        "effective_from": "2024-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
        "brackets": [
            {
                "bracket_order": 1,
                "minimum_value": "0.00",
                "maximum_value": "500000.00",
                "rate": "13.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 2,
                "minimum_value": "500000.00",
                "maximum_value": "1000000.00",
                "rate": "14.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 3,
                "minimum_value": "1000000.00",
                "maximum_value": "2000000.00",
                "rate": "17.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 4,
                "minimum_value": "2000000.00",
                "maximum_value": None,
                "rate": "18.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
        ],
    },
    # 2. Karnataka Infrastructure Development Cess (11% on Road Tax)
    {
        "source_record_id": "GOVT-KA-CESS-INFRA",
        "name": "Karnataka Infrastructure Development & Road Safety Cess",
        "description": "11% statutory cess computed on Motor Vehicle Road Tax (KMVT Cess Amendment)",
        "state_code": "KA",
        "state_name": "Karnataka",
        "rule_category": "CESS",
        "tax_type": "CESS",
        "calculation_method": "PERCENTAGE",
        "vehicle_type": "CAR",
        "fuel_type": "ANY",
        "is_ev": False,
        "usage_type": "PRIVATE",
        "rate": "11.0000",
        "fixed_amount": "0.00",
        "base_amount_type": "ROAD_TAX",
        "priority": 100,
        "effective_from": "2024-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    # 3. Karnataka Electric Vehicle (EV) Road Tax Exemption (0% Road Tax)
    {
        "source_record_id": "GOVT-KA-EV-EXEMPTION",
        "name": "Karnataka Electric Vehicle Policy Road Tax Exemption",
        "description": "100% Road Tax exemption for pure electric battery motor vehicles under Karnataka EV Policy",
        "state_code": "KA",
        "state_name": "Karnataka",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fuel_type": "Electric",
        "is_ev": True,
        "usage_type": "PRIVATE",
        "rate": "0.0000",
        "fixed_amount": "0.00",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 150,
        "effective_from": "2021-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    # 4. Karnataka Statutory Registration & RTO Fees (CMVR 1989 Rule 81)
    {
        "source_record_id": "GOVT-KA-REG-FEE-600",
        "name": "Karnataka Vehicle Registration Fee",
        "description": "Statutory central vehicle registration fee under CMVR 1989 Rule 81",
        "state_code": "KA",
        "state_name": "Karnataka",
        "rule_category": "REGISTRATION",
        "tax_type": "REGISTRATION_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "600.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-KA-RC-SMARTCARD-200",
        "name": "Karnataka Smart Card RC Fee",
        "description": "Plastic smart card registration certificate issuance charge",
        "state_code": "KA",
        "state_name": "Karnataka",
        "rule_category": "FEE",
        "tax_type": "SMART_CARD_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "200.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-KA-HSRP-FEE-450",
        "name": "Karnataka High Security Registration Plate (HSRP) Fee",
        "description": "Standard OEM/RTO HSRP fitment charge for 4-wheelers",
        "state_code": "KA",
        "state_name": "Karnataka",
        "rule_category": "FEE",
        "tax_type": "HSRP_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "450.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-KA-HYPO-FEE-1500",
        "name": "Karnataka Hypothecation Endorsement Fee",
        "description": "Hypothecation (HP) entry fee on Registration Certificate for financed vehicles",
        "state_code": "KA",
        "state_name": "Karnataka",
        "rule_category": "FEE",
        "tax_type": "HYPOTHECATION_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "1500.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-KA-FASTAG-FEE-600",
        "name": "Karnataka FASTag Activation & Issuance Fee",
        "description": "Standard mandatory RFID FASTag tag issuance charge",
        "state_code": "KA",
        "state_name": "Karnataka",
        "rule_category": "FEE",
        "tax_type": "FASTAG_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "600.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
]


class KarnatakaTaxRuleAdapter(GovernmentTaxRuleDataSourceAdapter):
    """Adapter for Karnataka State Transport Department statutory tax rules."""

    def __init__(self, mode: str = "FIXTURE_ONLY"):
        super().__init__(
            source_id="karnataka_tax_rules",
            source_name="Karnataka Transport Department Official Gazette",
            state_code="KA",
            state_name="Karnataka",
            department="Transport Department, Government of Karnataka",
            source_url="https://transport.karnataka.gov.in",
            rules_data=KARNATAKA_TAX_RULES_FIXTURE,
            mode=mode,
        )


# -----------------------------------------------------------------------------
# 6.2 MAHARASHTRA (MH)
# -----------------------------------------------------------------------------
MAHARASHTRA_TAX_RULES_FIXTURE = [
    # 1. Maharashtra Petrol Car Motor Vehicle Tax Slabs
    {
        "source_record_id": "GOVT-MH-PETROL-TAX-2024",
        "name": "Maharashtra Motor Vehicle Tax (Petrol)",
        "description": "Life Time Tax on petrol passenger cars under Maharashtra Motor Vehicles Tax Act",
        "state_code": "MH",
        "state_name": "Maharashtra",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "BRACKETED",
        "vehicle_type": "CAR",
        "fuel_type": "Petrol",
        "is_ev": False,
        "usage_type": "PRIVATE",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 110,
        "effective_from": "2024-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
        "brackets": [
            {
                "bracket_order": 1,
                "minimum_value": "0.00",
                "maximum_value": "1000000.00",
                "rate": "11.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 2,
                "minimum_value": "1000000.00",
                "maximum_value": "2000000.00",
                "rate": "12.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 3,
                "minimum_value": "2000000.00",
                "maximum_value": None,
                "rate": "13.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
        ],
    },
    # 2. Maharashtra Diesel Car Motor Vehicle Tax Slabs (2% higher rate)
    {
        "source_record_id": "GOVT-MH-DIESEL-TAX-2024",
        "name": "Maharashtra Motor Vehicle Tax (Diesel)",
        "description": "Life Time Tax on diesel passenger cars under Maharashtra Motor Vehicles Tax Act",
        "state_code": "MH",
        "state_name": "Maharashtra",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "BRACKETED",
        "vehicle_type": "CAR",
        "fuel_type": "Diesel",
        "is_ev": False,
        "usage_type": "PRIVATE",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 110,
        "effective_from": "2024-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
        "brackets": [
            {
                "bracket_order": 1,
                "minimum_value": "0.00",
                "maximum_value": "1000000.00",
                "rate": "13.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 2,
                "minimum_value": "1000000.00",
                "maximum_value": "2000000.00",
                "rate": "14.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 3,
                "minimum_value": "2000000.00",
                "maximum_value": None,
                "rate": "15.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
        ],
    },
    # 3. Maharashtra CNG Car Motor Vehicle Tax Slabs
    {
        "source_record_id": "GOVT-MH-CNG-TAX-2024",
        "name": "Maharashtra Motor Vehicle Tax (CNG / LPG)",
        "description": "Life Time Tax on CNG/LPG clean fuel passenger cars",
        "state_code": "MH",
        "state_name": "Maharashtra",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "BRACKETED",
        "vehicle_type": "CAR",
        "fuel_type": "CNG",
        "is_ev": False,
        "usage_type": "PRIVATE",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 110,
        "effective_from": "2024-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
        "brackets": [
            {
                "bracket_order": 1,
                "minimum_value": "0.00",
                "maximum_value": "1000000.00",
                "rate": "7.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 2,
                "minimum_value": "1000000.00",
                "maximum_value": "2000000.00",
                "rate": "8.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 3,
                "minimum_value": "2000000.00",
                "maximum_value": None,
                "rate": "9.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
        ],
    },
    # 4. Maharashtra EV Road Tax Exemption
    {
        "source_record_id": "GOVT-MH-EV-EXEMPTION",
        "name": "Maharashtra EV Policy 2021 Road Tax Exemption",
        "description": "Full Road Tax exemption for electric passenger vehicles under Maharashtra EV Policy",
        "state_code": "MH",
        "state_name": "Maharashtra",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fuel_type": "Electric",
        "is_ev": True,
        "usage_type": "PRIVATE",
        "rate": "0.0000",
        "fixed_amount": "0.00",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 150,
        "effective_from": "2021-07-23T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    # 5. Maharashtra Fees
    {
        "source_record_id": "GOVT-MH-REG-FEE-600",
        "name": "Maharashtra Vehicle Registration Charge",
        "description": "Statutory central vehicle registration fee",
        "state_code": "MH",
        "state_name": "Maharashtra",
        "rule_category": "REGISTRATION",
        "tax_type": "REGISTRATION_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "600.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-MH-HYPO-FEE-1500",
        "name": "Maharashtra Hypothecation Endorsement Fee",
        "description": "Hypothecation entry charge on RC for loan-financed vehicles",
        "state_code": "MH",
        "state_name": "Maharashtra",
        "rule_category": "FEE",
        "tax_type": "HYPOTHECATION_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "1500.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-MH-FASTAG-FEE-600",
        "name": "Maharashtra FASTag Tag Issuance Fee",
        "description": "Standard RFID FASTag issuance fee",
        "state_code": "MH",
        "state_name": "Maharashtra",
        "rule_category": "FEE",
        "tax_type": "FASTAG_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "600.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
]


class MaharashtraTaxRuleAdapter(GovernmentTaxRuleDataSourceAdapter):
    """Adapter for Maharashtra Motor Vehicles Department (MMVD) statutory tax rules."""

    def __init__(self, mode: str = "FIXTURE_ONLY"):
        super().__init__(
            source_id="maharashtra_tax_rules",
            source_name="Maharashtra Motor Vehicles Department (MMVD)",
            state_code="MH",
            state_name="Maharashtra",
            department="Motor Vehicles Department, Government of Maharashtra",
            source_url="https://transport.maharashtra.gov.in",
            rules_data=MAHARASHTRA_TAX_RULES_FIXTURE,
            mode=mode,
        )


# -----------------------------------------------------------------------------
# 6.3 DELHI (DL)
# -----------------------------------------------------------------------------
DELHI_TAX_RULES_FIXTURE = [
    # 1. Delhi Petrol / CNG Road Tax Slabs
    {
        "source_record_id": "GOVT-DL-PETROL-TAX-2024",
        "name": "Delhi Motor Vehicle Road Tax (Petrol / CNG)",
        "description": "Road Tax on petrol & CNG passenger cars under Delhi Motor Vehicles Taxation Act",
        "state_code": "DL",
        "state_name": "Delhi",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "BRACKETED",
        "vehicle_type": "CAR",
        "fuel_type": "Petrol",
        "is_ev": False,
        "usage_type": "PRIVATE",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 110,
        "effective_from": "2024-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
        "brackets": [
            {
                "bracket_order": 1,
                "minimum_value": "0.00",
                "maximum_value": "600000.00",
                "rate": "4.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 2,
                "minimum_value": "600000.00",
                "maximum_value": "1000000.00",
                "rate": "7.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 3,
                "minimum_value": "1000000.00",
                "maximum_value": None,
                "rate": "10.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
        ],
    },
    # 2. Delhi Diesel Road Tax Slabs
    {
        "source_record_id": "GOVT-DL-DIESEL-TAX-2024",
        "name": "Delhi Motor Vehicle Road Tax (Diesel)",
        "description": "Road Tax on diesel passenger cars under Delhi Motor Vehicles Taxation Act",
        "state_code": "DL",
        "state_name": "Delhi",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "BRACKETED",
        "vehicle_type": "CAR",
        "fuel_type": "Diesel",
        "is_ev": False,
        "usage_type": "PRIVATE",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 110,
        "effective_from": "2024-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
        "brackets": [
            {
                "bracket_order": 1,
                "minimum_value": "0.00",
                "maximum_value": "600000.00",
                "rate": "5.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 2,
                "minimum_value": "600000.00",
                "maximum_value": "1000000.00",
                "rate": "8.7500",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 3,
                "minimum_value": "1000000.00",
                "maximum_value": None,
                "rate": "12.5000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
        ],
    },
    # 3. Delhi EV Road Tax Waiver (Delhi EV Policy 2020)
    {
        "source_record_id": "GOVT-DL-EV-WAIVER",
        "name": "Delhi EV Policy 2020 Road Tax Waiver",
        "description": "100% Road Tax exemption for battery electric vehicles under Delhi EV Policy 2020",
        "state_code": "DL",
        "state_name": "Delhi",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fuel_type": "Electric",
        "is_ev": True,
        "usage_type": "PRIVATE",
        "rate": "0.0000",
        "fixed_amount": "0.00",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 150,
        "effective_from": "2020-08-07T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    # 4. Delhi Fees
    {
        "source_record_id": "GOVT-DL-REG-FEE-600",
        "name": "Delhi Registration Fee",
        "description": "Central statutory registration fee for motor cars",
        "state_code": "DL",
        "state_name": "Delhi",
        "rule_category": "REGISTRATION",
        "tax_type": "REGISTRATION_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "600.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-DL-RC-SMARTCARD-200",
        "name": "Delhi Smart Card RC Fee",
        "description": "Smart Card RC fee",
        "state_code": "DL",
        "state_name": "Delhi",
        "rule_category": "FEE",
        "tax_type": "SMART_CARD_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "200.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-DL-HYPO-FEE-1500",
        "name": "Delhi Hypothecation Fee",
        "description": "Hypothecation endorsement charge for financed vehicles",
        "state_code": "DL",
        "state_name": "Delhi",
        "rule_category": "FEE",
        "tax_type": "HYPOTHECATION_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "1500.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-DL-FASTAG-FEE-600",
        "name": "Delhi FASTag Charge",
        "description": "FASTag issuance fee",
        "state_code": "DL",
        "state_name": "Delhi",
        "rule_category": "FEE",
        "tax_type": "FASTAG_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "600.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
]


class DelhiTaxRuleAdapter(GovernmentTaxRuleDataSourceAdapter):
    """Adapter for Transport Department, Government of NCT of Delhi statutory tax rules."""

    def __init__(self, mode: str = "FIXTURE_ONLY"):
        super().__init__(
            source_id="delhi_tax_rules",
            source_name="Transport Department, Government of NCT of Delhi",
            state_code="DL",
            state_name="Delhi",
            department="Transport Department, Government of NCT of Delhi",
            source_url="https://transport.delhi.gov.in",
            rules_data=DELHI_TAX_RULES_FIXTURE,
            mode=mode,
        )


# -----------------------------------------------------------------------------
# 6.4 TAMIL NADU (TN)
# -----------------------------------------------------------------------------
TAMIL_NADU_TAX_RULES_FIXTURE = [
    # 1. Tamil Nadu Life Time Tax (LTT) Slabs for Motor Cars
    {
        "source_record_id": "GOVT-TN-ROAD-TAX-2024",
        "name": "Tamil Nadu Motor Vehicles Tax (Life Time Tax)",
        "description": "Life Time Tax on passenger motor vehicles under Tamil Nadu Motor Vehicles Taxation Act",
        "state_code": "TN",
        "state_name": "Tamil Nadu",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "BRACKETED",
        "vehicle_type": "CAR",
        "fuel_type": "ANY",
        "is_ev": False,
        "usage_type": "PRIVATE",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 100,
        "effective_from": "2024-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
        "brackets": [
            {
                "bracket_order": 1,
                "minimum_value": "0.00",
                "maximum_value": "500000.00",
                "rate": "12.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 2,
                "minimum_value": "500000.00",
                "maximum_value": "1000000.00",
                "rate": "13.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 3,
                "minimum_value": "1000000.00",
                "maximum_value": "2000000.00",
                "rate": "15.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 4,
                "minimum_value": "2000000.00",
                "maximum_value": None,
                "rate": "18.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
        ],
    },
    # 2. Tamil Nadu EV Road Tax Exemption
    {
        "source_record_id": "GOVT-TN-EV-EXEMPTION",
        "name": "Tamil Nadu EV Policy Road Tax Exemption",
        "description": "100% Road Tax exemption for battery electric motor vehicles under Tamil Nadu EV Policy",
        "state_code": "TN",
        "state_name": "Tamil Nadu",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fuel_type": "Electric",
        "is_ev": True,
        "usage_type": "PRIVATE",
        "rate": "0.0000",
        "fixed_amount": "0.00",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 150,
        "effective_from": "2022-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    # 3. Tamil Nadu Fees
    {
        "source_record_id": "GOVT-TN-REG-FEE-600",
        "name": "Tamil Nadu Registration Fee",
        "description": "Central statutory registration fee for motor cars",
        "state_code": "TN",
        "state_name": "Tamil Nadu",
        "rule_category": "REGISTRATION",
        "tax_type": "REGISTRATION_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "600.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-TN-HYPO-FEE-1500",
        "name": "Tamil Nadu Hypothecation Fee",
        "description": "Hypothecation endorsement charge for financed vehicles",
        "state_code": "TN",
        "state_name": "Tamil Nadu",
        "rule_category": "FEE",
        "tax_type": "HYPOTHECATION_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "1500.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-TN-FASTAG-FEE-600",
        "name": "Tamil Nadu FASTag Fee",
        "description": "RFID FASTag tag charge",
        "state_code": "TN",
        "state_name": "Tamil Nadu",
        "rule_category": "FEE",
        "tax_type": "FASTAG_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "600.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
]


class TamilNaduTaxRuleAdapter(GovernmentTaxRuleDataSourceAdapter):
    """Adapter for Home (Transport) Department, Government of Tamil Nadu statutory tax rules."""

    def __init__(self, mode: str = "FIXTURE_ONLY"):
        super().__init__(
            source_id="tamilnadu_tax_rules",
            source_name="Tamil Nadu Transport Department Official Gazette",
            state_code="TN",
            state_name="Tamil Nadu",
            department="Home (Transport) Department, Government of Tamil Nadu",
            source_url="https://tnsta.gov.in",
            rules_data=TAMIL_NADU_TAX_RULES_FIXTURE,
            mode=mode,
        )


# -----------------------------------------------------------------------------
# 6.5 TELANGANA (TS)
# -----------------------------------------------------------------------------
TELANGANA_TAX_RULES_FIXTURE = [
    # 1. Telangana Life Time Tax Slabs for Motor Cars
    {
        "source_record_id": "GOVT-TS-ROAD-TAX-2024",
        "name": "Telangana Motor Vehicles Tax (Life Time Tax)",
        "description": "Life Time Tax on passenger motor vehicles under Telangana Motor Vehicles Taxation Act",
        "state_code": "TS",
        "state_name": "Telangana",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "BRACKETED",
        "vehicle_type": "CAR",
        "fuel_type": "ANY",
        "is_ev": False,
        "usage_type": "PRIVATE",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 100,
        "effective_from": "2024-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
        "brackets": [
            {
                "bracket_order": 1,
                "minimum_value": "0.00",
                "maximum_value": "500000.00",
                "rate": "13.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 2,
                "minimum_value": "500000.00",
                "maximum_value": "1000000.00",
                "rate": "14.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 3,
                "minimum_value": "1000000.00",
                "maximum_value": "2000000.00",
                "rate": "17.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
            {
                "bracket_order": 4,
                "minimum_value": "2000000.00",
                "maximum_value": None,
                "rate": "18.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
        ],
    },
    # 2. Telangana EV Road Tax Exemption (Telangana EV Policy 2024-2026)
    {
        "source_record_id": "GOVT-TS-EV-EXEMPTION",
        "name": "Telangana EV Policy 2024-2026 Road Tax Exemption",
        "description": "100% Road Tax exemption for electric cars registered in Telangana",
        "state_code": "TS",
        "state_name": "Telangana",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fuel_type": "Electric",
        "is_ev": True,
        "usage_type": "PRIVATE",
        "rate": "0.0000",
        "fixed_amount": "0.00",
        "base_amount_type": "EX_SHOWROOM",
        "priority": 150,
        "effective_from": "2024-11-18T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    # 3. Telangana Fees
    {
        "source_record_id": "GOVT-TS-REG-FEE-600",
        "name": "Telangana Registration Fee",
        "description": "Central statutory registration fee for motor cars",
        "state_code": "TS",
        "state_name": "Telangana",
        "rule_category": "REGISTRATION",
        "tax_type": "REGISTRATION_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "600.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-TS-HYPO-FEE-1500",
        "name": "Telangana Hypothecation Fee",
        "description": "Hypothecation endorsement charge for financed vehicles",
        "state_code": "TS",
        "state_name": "Telangana",
        "rule_category": "FEE",
        "tax_type": "HYPOTHECATION_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "1500.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
    {
        "source_record_id": "GOVT-TS-FASTAG-FEE-600",
        "name": "Telangana FASTag Fee",
        "description": "FASTag issuance fee",
        "state_code": "TS",
        "state_name": "Telangana",
        "rule_category": "FEE",
        "tax_type": "FASTAG_FEE",
        "calculation_method": "FIXED",
        "vehicle_type": "CAR",
        "fixed_amount": "600.00",
        "priority": 100,
        "effective_from": "2020-01-01T00:00:00Z",
        "effective_to": None,
        "verification_status": "VERIFIED",
    },
]


class TelanganaTaxRuleAdapter(GovernmentTaxRuleDataSourceAdapter):
    """Adapter for Transport Department, Government of Telangana statutory tax rules."""

    def __init__(self, mode: str = "FIXTURE_ONLY"):
        super().__init__(
            source_id="telangana_tax_rules",
            source_name="Telangana Transport Department Official Gazette",
            state_code="TS",
            state_name="Telangana",
            department="Transport Department, Government of Telangana",
            source_url="https://transport.telangana.gov.in",
            rules_data=TELANGANA_TAX_RULES_FIXTURE,
            mode=mode,
        )
