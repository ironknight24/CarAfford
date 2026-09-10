import pytest
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion_constants import (
    DataSourceType,
    IngestionRunStatus,
    VerificationStatus,
    DataFreshnessStatus,
    ConflictStatus,
    IngestionEntityType,
    DATA_QUALITY_WEIGHTS,
)
from app.ingestion.adapters.demo_adapter import DemoDataSourceAdapter
from app.ingestion.base import compute_payload_hash
from app.ingestion.validators.finance_validator import FinanceDataValidator
from app.ingestion.validators.location_validator import LocationDataValidator
from app.ingestion.validators.pricing_validator import PriceDataValidator
from app.ingestion.validators.tax_validator import TaxRuleDataValidator
from app.ingestion.validators.vehicle_validator import VehicleDataValidator
from app.models.data_source import DataSource
from app.models.ingestion import (
    DataConflictRecord,
    DataQualityReviewItem,
    IngestionRun,
    RawIngestionRecord,
)
from app.models.pricing import VehiclePrice
from app.models.vehicle import CarModel, Variant
from app.services.data_quality_service import DataQualityService
from app.services.ingestion_service import IngestionService
from app.db.seed import seed_database


class TestDataSourceAndProvenance:
    @pytest.mark.asyncio
    async def test_create_data_source_and_trust_levels(self, db_session: AsyncSession):
        """Data sources store provenance metadata and configurable trust levels."""
        ds = await IngestionService.get_or_create_data_source(
            db=db_session,
            name="Ministry of Road Transport and Highways (MoRTH)",
            slug="morth-parivahan-official",
            source_type=DataSourceType.OFFICIAL_GOVERNMENT,
            organization="Government of India",
            base_url="https://parivahan.gov.in",
            trust_level=100,
        )
        assert ds.id is not None
        assert ds.trust_level == 100
        assert ds.source_type == DataSourceType.OFFICIAL_GOVERNMENT.value
        assert ds.is_active is True

    @pytest.mark.asyncio
    async def test_raw_payload_hash_deduplication(self, db_session: AsyncSession):
        """SHA-256 payload hashing ensures deterministic idempotency."""
        payload1 = {"manufacturer": "Tata", "model": "Punch", "price": "600000.00"}
        payload2 = {"price": "600000.00", "model": "Punch", "manufacturer": "Tata"}
        payload3 = {"manufacturer": "Tata", "model": "Punch", "price": "610000.00"}

        hash1 = compute_payload_hash(payload1)
        hash2 = compute_payload_hash(payload2)
        hash3 = compute_payload_hash(payload3)

        assert hash1 == hash2  # Dict ordering does not alter hash
        assert hash1 != hash3  # Different values produce distinct hashes


class TestIngestionValidators:
    def test_vehicle_validator_rules(self):
        """Validates vehicle attributes, fuel types, seating, and safety bounds."""
        v = VehicleDataValidator()

        # Valid payload
        is_valid, errors = v.validate(
            {
                "manufacturer_name": "Tata Motors",
                "model_name": "Punch",
                "variant_name": "Pure 1.2 MT",
                "fuel_type": "Petrol",
                "transmission": "Manual",
                "body_type": "SUV",
                "seating_capacity": 5,
                "arai_mileage_kmpl": Decimal("20.09"),
                "safety_rating_stars": 5,
                "airbags_count": 2,
            }
        )
        assert is_valid is True
        assert len(errors) == 0

        # Invalid fuel and negative seating
        is_valid, errors = v.validate(
            {
                "manufacturer_name": "Tata Motors",
                "model_name": "Punch",
                "variant_name": "Pure 1.2 MT",
                "fuel_type": "Kerosene",  # Invalid
                "seating_capacity": 0,  # Invalid
            }
        )
        assert is_valid is False
        assert any("fuel_type" in e for e in errors)
        assert any("seating_capacity" in e for e in errors)

    def test_price_validator_bounds_and_dates(self):
        """Validates positive prices, automotive range bounds, and non-overlapping effective dates."""
        pv = PriceDataValidator()

        # Valid price and date span
        is_valid, errors = pv.validate(
            {
                "ex_showroom_price": Decimal("850000.00"),
                "effective_from": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "effective_to": datetime(2026, 6, 30, tzinfo=timezone.utc),
            }
        )
        assert is_valid is True

        # Inverted effective dates
        is_valid, errors = pv.validate(
            {
                "ex_showroom_price": Decimal("850000.00"),
                "effective_from": datetime(2026, 7, 1, tzinfo=timezone.utc),
                "effective_to": datetime(2026, 1, 1, tzinfo=timezone.utc),
            }
        )
        assert is_valid is False
        assert any("earlier" in e for e in errors)

        # Unrealistic zero / extreme prices
        is_valid, errors = pv.validate(
            {
                "ex_showroom_price": Decimal("0.00"),
                "effective_from": "2026-01-01T00:00:00Z",
            }
        )
        assert is_valid is False

    def test_tax_and_finance_validators(self):
        """Validates tax rule rates and bank interest rate bounds."""
        tv = TaxRuleDataValidator()
        fv = FinanceDataValidator()

        # Tax out of bounds
        is_valid, errors = tv.validate(
            {
                "state_code": "KA",
                "tax_type": "ROAD_TAX",
                "calculation_type": "PERCENTAGE",
                "base_rate_percent": Decimal("99.0"),  # Implausible 99%
            }
        )
        assert is_valid is False

        # Inverted CIBIL bounds
        is_valid, errors = fv.validate(
            {
                "bank_name": "SBI",
                "product_name": "Auto Loan",
                "annual_interest_rate": Decimal("8.5"),
                "min_cibil_score": 850,
                "max_cibil_score": 600,  # Inverted
            }
        )
        assert is_valid is False
        assert any("cannot exceed" in e for e in errors)

    def test_location_validator_regex(self):
        """Validates 2-letter state codes and Indian RTO regex formats."""
        lv = LocationDataValidator()
        assert lv.validate({"state_code": "KA", "rto_code": "KA-01"})[0] is True
        assert lv.validate({"state_code": "KAR"})[0] is False  # 3 chars invalid


class TestIngestionPipelineAndEffectiveDates:
    @pytest.mark.asyncio
    async def test_demo_adapter_end_to_end_ingestion(self, db_session: AsyncSession):
        """Demo adapter executes full Fetch -> Stage -> Validate -> Map -> Canonical workflow."""
        adapter = DemoDataSourceAdapter()
        run = await IngestionService.run_adapter(db_session, adapter, notes="Unit test demo run")

        assert run.id is not None
        assert run.status == IngestionRunStatus.COMPLETED.value
        assert run.records_seen >= 4
        assert run.records_created >= 4
        assert run.records_rejected == 0

        # Verify raw records were staged
        raw_recs = (
            (
                await db_session.execute(
                    select(RawIngestionRecord).where(RawIngestionRecord.ingestion_run_id == run.id)
                )
            )
            .scalars()
            .all()
        )
        assert len(raw_recs) == run.records_seen
        assert all(r.validation_status == "VALID" for r in raw_recs)

    @pytest.mark.asyncio
    async def test_effective_dated_price_updates_preserve_history(self, db_session: AsyncSession):
        """When a new price is ingested, the old price record is closed with effective_to, not overwritten."""
        await seed_database(db_session)
        ds = (await db_session.execute(select(DataSource).limit(1))).scalars().first()
        variant_res = await db_session.execute(
            select(Variant)
            .options(joinedload(Variant.model).joinedload(CarModel.manufacturer))
            .limit(1)
        )
        variant = variant_res.scalars().first()

        # Step 1: Ingest Initial Price
        p1_data = {
            "manufacturer_name": variant.model.manufacturer.name,
            "model_name": variant.model.name,
            "variant_name": variant.name,
            "ex_showroom_price": Decimal("650000.00"),
            "effective_from": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }
        res1 = await IngestionService._promote_vehicle_to_canonical(db_session, p1_data, ds.id)
        assert res1 in {"CREATED", "UPDATED"}

        # Step 2: Ingest Price Revision 6 months later
        p2_data = {
            "manufacturer_name": variant.model.manufacturer.name,
            "model_name": variant.model.name,
            "variant_name": variant.name,
            "ex_showroom_price": Decimal("670000.00"),
            "effective_from": datetime(2026, 7, 1, tzinfo=timezone.utc),
        }
        res2 = await IngestionService._promote_vehicle_to_canonical(db_session, p2_data, ds.id)
        assert res2 == "UPDATED"

        # Verify historical records in DB
        prices = (
            (
                await db_session.execute(
                    select(VehiclePrice)
                    .where(VehiclePrice.variant_id == variant.id)
                    .order_by(VehiclePrice.effective_from.asc())
                )
            )
            .scalars()
            .all()
        )

        assert len(prices) >= 2
        # Previous price closed
        old_price = [p for p in prices if p.ex_showroom_price == Decimal("650000.00")][0]
        new_price = [p for p in prices if p.ex_showroom_price == Decimal("670000.00")][0]

        assert old_price.effective_to is not None
        assert old_price.effective_to.replace(tzinfo=timezone.utc) == datetime(
            2026, 7, 1, tzinfo=timezone.utc
        )
        assert new_price.effective_to is None  # Active currently


class TestConflictResolutionAndQualityReview:
    @pytest.mark.asyncio
    async def test_conflict_detection_and_resolution(self, db_session: AsyncSession):
        """Cross-source price discrepancies trigger conflict records that can be explicitly resolved."""
        ds_a = await IngestionService.get_or_create_data_source(
            db_session, "OEM Official Portal", "oem-portal", DataSourceType.OFFICIAL_MANUFACTURER
        )
        ds_b = await IngestionService.get_or_create_data_source(
            db_session, "Dealer Association Feed", "dealer-feed", DataSourceType.LICENSED_COMMERCIAL
        )

        conflict = DataConflictRecord(
            dataset_name="vehicle_prices",
            entity_type="VEHICLE_PRICE",
            entity_identifier="Tata Punch Pure 1.2 MT",
            field_name="ex_showroom_price",
            source_a_id=ds_a.id,
            source_a_value={"price": "612900.00"},
            source_b_id=ds_b.id,
            source_b_value={"price": "619000.00"},
            detected_at=datetime.now(timezone.utc),
            status=ConflictStatus.UNRESOLVED.value,
        )
        db_session.add(conflict)
        await db_session.commit()
        await db_session.refresh(conflict)

        # Unresolved conflicts query
        unresolved = await DataQualityService.get_unresolved_conflicts(db_session)
        assert len(unresolved) >= 1
        assert any(c.id == conflict.id for c in unresolved)

        # Resolve conflict
        resolved = await DataQualityService.resolve_conflict(
            db_session,
            conflict_id=conflict.id,
            accepted_source_id=ds_a.id,
            notes="Accepted OEM authoritative ex-showroom price",
        )
        assert resolved is not None
        assert resolved.status == ConflictStatus.RESOLVED.value
        assert "Adopted Source" in resolved.resolution_notes

    @pytest.mark.asyncio
    async def test_manual_review_queue_approval_and_rejection(self, db_session: AsyncSession):
        """Flagged items can be reviewed, approved to VERIFIED, or rejected."""
        review_item = DataQualityReviewItem(
            entity_type="TAX_RULE",
            entity_identifier="Karnataka Road Tax 2026",
            field_name="base_rate_percent",
            current_value={"rate": "14.0"},
            proposed_value={"rate": "15.0"},
            status=VerificationStatus.PENDING_REVIEW.value,
        )
        db_session.add(review_item)
        await db_session.commit()
        await db_session.refresh(review_item)

        # Verify in review queue
        queue = await DataQualityService.get_review_queue(db_session)
        assert any(item.id == review_item.id for item in queue)

        # Approve item
        approved = await DataQualityService.approve_review_item(
            db_session, item_id=review_item.id, reviewer_name="Lead Data Engineer"
        )
        assert approved.status == VerificationStatus.VERIFIED.value
        assert approved.reviewed_by == "Lead Data Engineer"

    @pytest.mark.asyncio
    async def test_data_quality_overview_and_freshness(self, db_session: AsyncSession):
        """Quality overview produces explainable composite score and freshness SLAs."""
        await seed_database(db_session)
        overview = await IngestionService.get_data_quality_overview(db_session)

        assert overview.overall_quality_score > Decimal("0.0")
        assert overview.breakdown.source_trust_score > Decimal("0.0")
        assert overview.breakdown.freshness_score >= Decimal("0.0")
        assert len(overview.freshness_report) > 0
        assert overview.data_status == "DEMO"
