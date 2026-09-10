import pytest
from datetime import datetime, timezone
from decimal import Decimal

from app.core.ingestion_constants import DataSourceType, IngestionEntityType
from app.ingestion.adapters.government_tax_adapter import (
    KarnatakaTaxRuleAdapter,
    MaharashtraTaxRuleAdapter,
    DelhiTaxRuleAdapter,
    TamilNaduTaxRuleAdapter,
    TelanganaTaxRuleAdapter,
    GovernmentTaxNormalizer,
    GovernmentTaxParser,
)
from app.ingestion.validators.tax_validator import TaxRuleDataValidator


def test_government_tax_adapters_metadata():
    """Verifies metadata, trust levels, and source identifiers across all 5 state adapters."""
    adapters = [
        (KarnatakaTaxRuleAdapter(), "karnataka_tax_rules", "KA"),
        (MaharashtraTaxRuleAdapter(), "maharashtra_tax_rules", "MH"),
        (DelhiTaxRuleAdapter(), "delhi_tax_rules", "DL"),
        (TamilNaduTaxRuleAdapter(), "tamilnadu_tax_rules", "TN"),
        (TelanganaTaxRuleAdapter(), "telangana_tax_rules", "TS"),
    ]

    for adapter, expected_id, expected_code in adapters:
        assert adapter.source_id == expected_id
        assert adapter.state_code == expected_code
        assert adapter.source_type == DataSourceType.OFFICIAL_GOVERNMENT
        assert adapter.entity_type == IngestionEntityType.TAX_RULE
        assert adapter.dataset_name == "tax_rules"
        assert adapter.default_trust_level == 100
        assert len(adapter.rules_data) >= 3


def test_tax_validator_valid_bracketed_rule():
    """Verifies that a well-formed bracketed statutory tax rule passes validation."""
    validator = TaxRuleDataValidator()
    payload = {
        "name": "Karnataka Motor Vehicle Tax",
        "state_code": "KA",
        "state_name": "Karnataka",
        "rule_category": "TAX",
        "tax_type": "ROAD_TAX",
        "calculation_method": "BRACKETED",
        "vehicle_type": "CAR",
        "usage_type": "PRIVATE",
        "effective_from": "2024-01-01T00:00:00Z",
        "effective_to": None,
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
                "maximum_value": None,
                "rate": "17.0000",
                "fixed_amount": "0.00",
                "calculation_method": "PERCENTAGE",
            },
        ],
    }
    is_valid, errors = validator.validate(payload)
    assert is_valid is True
    assert len(errors) == 0


def test_tax_validator_rejects_negative_rate_and_overlapping_brackets():
    """Verifies that negative rates and overlapping brackets are strictly rejected."""
    validator = TaxRuleDataValidator()

    # 1. Negative rate
    payload_neg = {
        "name": "Invalid Negative Tax",
        "state_code": "KA",
        "tax_type": "ROAD_TAX",
        "calculation_method": "PERCENTAGE",
        "rate": "-5.00",
        "effective_from": "2024-01-01T00:00:00Z",
    }
    is_valid, errors = validator.validate(payload_neg)
    assert is_valid is False
    assert any("cannot be negative" in e for e in errors)

    # 2. Overlapping brackets
    payload_overlap = {
        "name": "Overlapping Slabs",
        "state_code": "KA",
        "tax_type": "ROAD_TAX",
        "calculation_method": "BRACKETED",
        "effective_from": "2024-01-01T00:00:00Z",
        "brackets": [
            {
                "bracket_order": 1,
                "minimum_value": "0.00",
                "maximum_value": "800000.00",
                "rate": "12.00",
            },
            {
                "bracket_order": 2,
                "minimum_value": "600000.00",
                "maximum_value": "1500000.00",
                "rate": "14.00",
            },  # Overlaps 6L < 8L
        ],
    }
    is_valid, errors = validator.validate(payload_overlap)
    assert is_valid is False
    assert any("Overlapping bracket detected" in e for e in errors)


def test_tax_validator_formula_ast_safety():
    """Verifies formula definition safety checks rejecting arbitrary or unsafe definitions."""
    validator = TaxRuleDataValidator()

    # Valid BH-Series formula AST
    valid_formula = {
        "name": "MoRTH BH-Series Tax",
        "state_code": "KA",
        "tax_type": "ROAD_TAX",
        "calculation_method": "FORMULA",
        "effective_from": "2021-09-15T00:00:00Z",
        "formula_definition": {
            "type": "BH_SERIES",
            "factor": 1.25,
            "payment_tenure_years": 2,
            "diesel_surcharge": 2.0,
            "ev_discount": 2.0,
        },
    }
    is_valid, errors = validator.validate(valid_formula)
    assert is_valid is True

    # Invalid formula type
    invalid_formula = {
        "name": "Unsafe Exec Formula",
        "state_code": "KA",
        "tax_type": "ROAD_TAX",
        "calculation_method": "FORMULA",
        "effective_from": "2021-09-15T00:00:00Z",
        "formula_definition": {
            "type": "ARBITRARY_EVAL",
            "code": "__import__('os').system('echo hack')",
        },
    }
    is_valid, errors = validator.validate(invalid_formula)
    assert is_valid is False
    assert any("not supported" in e for e in errors)


def test_tax_normalizer_decimal_and_dates():
    """Verifies that normalizer accurately converts floats/strings to Decimal and dates to UTC."""
    normalizer = GovernmentTaxNormalizer()
    raw = {
        "state_code": "ka ",
        "name": "  Karnataka Road Tax  ",
        "tax_type": "road_tax",
        "rate": "14.5",
        "fixed_amount": "600",
        "effective_from": "2024-01-01T00:00:00Z",
        "brackets": [
            {"bracket_order": 1, "minimum_value": "0", "maximum_value": "500000", "rate": "13.0"},
        ],
    }
    norm = normalizer.normalize(raw)
    assert norm["state_code"] == "KA"
    assert norm["tax_type"] == "ROAD_TAX"
    assert norm["rate"] == Decimal("14.5")
    assert norm["fixed_amount"] == Decimal("600")
    assert isinstance(norm["effective_from"], datetime)
    assert norm["brackets"][0]["minimum_value"] == Decimal("0")
    assert norm["brackets"][0]["maximum_value"] == Decimal("500000")
    assert norm["brackets"][0]["rate"] == Decimal("13.0")
