import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion_constants import (
    DataSourceType,
    IngestionRunStatus,
    VerificationStatus,
    ConflictStatus,
)
from app.models.data_source import DataSource
from app.models.ingestion import DataConflictRecord, IngestionRun, RawIngestionRecord
from app.models.location import State
from app.models.tax_rule import TaxRule, TaxRuleBracket
from app.models.vehicle import Variant
from app.services.ingestion_service import IngestionService
from app.ingestion.adapters.government_tax_adapter import (
    KarnatakaTaxRuleAdapter,
    MaharashtraTaxRuleAdapter,
    DelhiTaxRuleAdapter,
    TamilNaduTaxRuleAdapter,
    TelanganaTaxRuleAdapter,
)
from app.ingestion.adapters.manufacturer_vehicle_adapter import TataMotorsVehicleDataSourceAdapter


@pytest.mark.asyncio
async def test_trigger_karnataka_tax_ingestion_api(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """Tests triggering Karnataka tax ingestion via REST API and verifies canonical tax rules."""
    response = await async_client.post(
        "/api/v1/ingestion/runs",
        json={
            "dataset_name": "karnataka_tax_rules",
            "notes": "API test run for KA tax rules",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["success"] is True
    run_data = data["data"]
    assert run_data["status"] == IngestionRunStatus.COMPLETED.value
    assert run_data["records_created"] > 0
    assert run_data["error_count"] == 0

    # Verify raw records stored with SHA-256 hash
    run_id = run_data["id"]
    raw_recs = (
        await db_session.execute(
            select(RawIngestionRecord).where(RawIngestionRecord.ingestion_run_id == run_id)
        )
    ).scalars().all()
    assert len(raw_recs) >= 3
    for r in raw_recs:
        assert len(r.payload_hash) == 64

    # Verify canonical TaxRule records
    ka_rules = (
        await db_session.execute(
            select(TaxRule).join(State).where(
                State.code == "KA",
                TaxRule.verification_status == VerificationStatus.VERIFIED.value,
            )
        )
    ).scalars().all()
    assert len(ka_rules) >= 3

    # Verify bracketed Road Tax rule
    road_tax = next((r for r in ka_rules if r.tax_type == "ROAD_TAX" and not r.is_ev), None)
    assert road_tax is not None
    assert road_tax.calculation_method == "BRACKETED"

    brackets = (
        await db_session.execute(
            select(TaxRuleBracket).where(TaxRuleBracket.tax_rule_id == road_tax.id)
        )
    ).scalars().all()
    assert len(brackets) == 4


@pytest.mark.asyncio
async def test_trigger_all_five_states_tax_ingestion(db_session: AsyncSession):
    """Tests ingestion runs for all 5 target states (KA, MH, DL, TN, TS)."""
    adapters = [
        KarnatakaTaxRuleAdapter(),
        MaharashtraTaxRuleAdapter(),
        DelhiTaxRuleAdapter(),
        TamilNaduTaxRuleAdapter(),
        TelanganaTaxRuleAdapter(),
    ]

    for adapter in adapters:
        run = await IngestionService.run_adapter(
            db=db_session, adapter=adapter, notes=f"Test run for {adapter.state_code}"
        )
        assert run.status == IngestionRunStatus.COMPLETED.value
        assert run.records_seen >= 3
        assert run.error_count == 0


@pytest.mark.asyncio
async def test_tax_ingestion_idempotency(db_session: AsyncSession):
    """Verifies that executing the same tax adapter multiple times is completely idempotent."""
    adapter = MaharashtraTaxRuleAdapter()

    # First run
    run1 = await IngestionService.run_adapter(db=db_session, adapter=adapter)
    assert run1.status == IngestionRunStatus.COMPLETED.value

    # Second run with unchanged data
    run2 = await IngestionService.run_adapter(db=db_session, adapter=adapter)
    assert run2.status == IngestionRunStatus.COMPLETED.value
    assert run2.records_created == 0
    assert run2.records_unchanged == run2.records_seen


@pytest.mark.asyncio
async def test_tax_temporal_effective_dating_preservation(db_session: AsyncSession):
    """Verifies that changing a tax rate closes the previous record and inserts a new active record without overwriting history."""
    adapter = DelhiTaxRuleAdapter()
    await IngestionService.run_adapter(db=db_session, adapter=adapter)

    # Ingest revised rate schedule
    revised_data = [
        {
            "source_record_id": "GOVT-DL-REG-FEE-600",
            "name": "Delhi Registration Fee",
            "description": "Revised registration fee",
            "state_code": "DL",
            "state_name": "Delhi",
            "rule_category": "REGISTRATION",
            "tax_type": "REGISTRATION_FEE",
            "calculation_method": "FIXED",
            "vehicle_type": "CAR",
            "fixed_amount": "800.00",  # Changed from 600 to 800
            "priority": 100,
            "effective_from": "2026-07-01T00:00:00Z",
            "effective_to": None,
            "verification_status": "VERIFIED",
        }
    ]

    custom_adapter = DelhiTaxRuleAdapter()
    custom_adapter.fetcher.fixture_data = revised_data

    run_revised = await IngestionService.run_adapter(db=db_session, adapter=custom_adapter)
    assert run_revised.status == IngestionRunStatus.COMPLETED.value
    assert run_revised.records_updated == 1

    # Verify both historical closed rule and new active rule exist in DB
    all_reg_rules = (
        await db_session.execute(
            select(TaxRule).join(State).where(
                State.code == "DL",
                TaxRule.tax_type == "REGISTRATION_FEE",
                TaxRule.name == "Delhi Registration Fee",
            )
        )
    ).scalars().all()

    assert len(all_reg_rules) == 2
    closed_rule = next(r for r in all_reg_rules if not r.active)
    active_rule = next(r for r in all_reg_rules if r.active)

    assert Decimal(str(closed_rule.fixed_amount)) == Decimal("600.00")
    assert closed_rule.effective_to is not None
    assert Decimal(str(active_rule.fixed_amount)) == Decimal("800.00")
    assert active_rule.effective_to is None


@pytest.mark.asyncio
async def test_tax_cross_source_conflict_detection(db_session: AsyncSession):
    """Verifies that conflicting tax rates from another data source trigger DataConflictRecord."""
    # 1. Primary official government ingestion
    ka_adapter = KarnatakaTaxRuleAdapter()
    await IngestionService.run_adapter(db=db_session, adapter=ka_adapter)

    # 2. Secondary source reporting conflicting fixed fee
    sec_data = [
        {
            "source_record_id": "SEC-KA-FASTAG",
            "name": "Karnataka FASTag Activation & Issuance Fee",
            "state_code": "KA",
            "state_name": "Karnataka",
            "tax_type": "FASTAG_FEE",
            "calculation_method": "FIXED",
            "rate": "15.0000",
            "fixed_amount": "800.00",
            "effective_from": "2024-01-01T00:00:00Z",
        }
    ]

    conflict_adapter = KarnatakaTaxRuleAdapter()
    conflict_adapter._source_id = "secondary_transport_source"
    conflict_adapter._source_name = "Secondary Transport Portal"
    conflict_adapter._trust_level = 75
    conflict_adapter.fetcher.fixture_data = sec_data

    await IngestionService.run_adapter(db=db_session, adapter=conflict_adapter)

    # Check for detected conflict
    conflicts = (
        await db_session.execute(
            select(DataConflictRecord).where(
                DataConflictRecord.dataset_name == "tax_rules",
            )
        )
    ).scalars().all()
    assert len(conflicts) >= 1


@pytest.mark.asyncio
async def test_on_road_pricing_integration_with_authoritative_tax_rules(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """Verifies that OnRoadPriceCalculationService accurately consumes ingested authoritative tax rules."""
    # Ensure vehicle and KA rules are ingested
    await IngestionService.run_adapter(db=db_session, adapter=TataMotorsVehicleDataSourceAdapter())
    await IngestionService.run_adapter(db=db_session, adapter=KarnatakaTaxRuleAdapter())

    ka_state = (await db_session.execute(select(State).where(State.code == "KA"))).scalars().first()
    assert ka_state is not None

    variant = (await db_session.execute(select(Variant).limit(1))).scalars().first()
    assert variant is not None

    res = await async_client.post(
        "/api/v1/pricing/on-road",
        json={
            "variant_id": variant.id,
            "state_id": ka_state.id,
            "is_financed": True,
        },
    )
    assert res.status_code == 200
    p_data = res.json()["data"]
    assert Decimal(str(p_data["totals"]["on_road_price"])) > Decimal(str(p_data["totals"]["ex_showroom_price"]))
    assert Decimal(str(p_data["totals"]["total_statutory_taxes"])) > Decimal("0.00")

    # Verify breakdown contains road tax and registration fee
    components = [item["component"] for item in p_data["breakdown"]]
    assert "EX_SHOWROOM" in components
    assert "ROAD_TAX" in components
    assert "REGISTRATION_FEE" in components


@pytest.mark.asyncio
async def test_tax_rules_rest_api_compatibility(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """Verifies that GET /api/v1/tax-rules returns rules with provenance and verification_status."""
    await IngestionService.run_adapter(db=db_session, adapter=KarnatakaTaxRuleAdapter())

    res = await async_client.get("/api/v1/tax-rules")
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert len(data["items"]) > 0
    rule_item = data["items"][0]
    assert "verification_status" in rule_item
    assert "effective_from" in rule_item
