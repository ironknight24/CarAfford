import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion_constants import (
    DataSourceType,
    IngestionRunStatus,
    IngestionEntityType,
    ConflictStatus,
)
from app.ingestion.adapters.government_location_adapter import (
    GovernmentLocationDataSourceAdapter,
    GovernmentLocationFetcher,
    GovernmentLocationParser,
    GovernmentLocationNormalizer,
    GovernmentLocationMapper,
    CITY_NAME_CANONICAL_MAP,
)
from app.ingestion.validators.location_validator import (
    LocationDataValidator,
    RECOGNIZED_INDIAN_STATE_CODES,
)
from app.models.data_source import DataSource
from app.models.ingestion import (
    DataConflictRecord,
    IngestionRun,
    RawIngestionRecord,
)
from app.models.location import Country, State, City, RtoOffice
from app.services.ingestion_service import IngestionService
from app.db.seed import seed_database


class TestGovernmentLocationAdapterComponents:
    def test_adapter_metadata_and_trust_level(self):
        """Government location adapter exposes official MoRTH provenance and trust level 100."""
        adapter = GovernmentLocationDataSourceAdapter()
        assert adapter.source_type == DataSourceType.OFFICIAL_GOVERNMENT
        assert adapter.trust_level == 100
        assert "Ministry of Road Transport and Highways" in adapter.source_name
        assert adapter.source_slug == "morth-parivahan-rto-directory"
        assert adapter.provider_type == "government_portal"
        assert adapter.entity_type == IngestionEntityType.LOCATION
        assert adapter.base_url == "https://parivahan.gov.in"
        assert "godl" in adapter.terms_url.lower()

    @pytest.mark.asyncio
    async def test_fetcher_records_and_fallback(self):
        """Fetcher provides valid MoRTH records with source_record_id and handles network fallback."""
        fetcher = GovernmentLocationFetcher()
        records = await fetcher.fetch()
        assert len(records) >= 10
        assert all("source_record_id" in r for r in records)
        assert any(r["state_code"] == "KA" and r["rto_code"] == "KA-01" for r in records)
        assert any(r["state_code"] == "DL" and r["rto_code"] == "DL-01" for r in records)
        assert any(r["state_code"] == "MH" and r["rto_code"] == "MH-01" for r in records)

    def test_normalizer_city_alias_mapping(self):
        """Normalizer standardizes Indian city names and handles historical aliases."""
        normalizer = GovernmentLocationNormalizer()

        # Bangalore -> Bengaluru
        res_blr = normalizer.normalize({
            "state_code": "ka",
            "state_name": "Karnataka",
            "city_name": "Bangalore",
            "city_tier": "1",
            "rto_code": "ka01",
            "rto_name": "Koramangala",
        })
        assert res_blr["city_name"] == "Bengaluru"
        assert res_blr["city_slug"] == "bengaluru"
        assert res_blr["tier"] == "Tier 1"
        assert res_blr["state_code"] == "KA"
        assert res_blr["rto_code"] == "KA-01"

        # Bombay -> Mumbai
        res_mum = normalizer.normalize({
            "state_code": "MH",
            "city_name": "Bombay",
            "rto_code": "MH-1",
        })
        assert res_mum["city_name"] == "Mumbai"
        assert res_mum["rto_code"] == "MH-01"

        # Gurgaon -> Gurugram
        res_ggn = normalizer.normalize({
            "state_code": "HR",
            "city_name": "Gurgaon",
            "rto_code": "hr26",
        })
        assert res_ggn["city_name"] == "Gurugram"
        assert res_ggn["rto_code"] == "HR-26"

    def test_validator_rules_and_hierarchical_consistency(self):
        """Validator checks 2-letter state codes, RTO format, and parent state consistency."""
        validator = LocationDataValidator()

        # Valid payload
        valid_res, valid_errs = validator.validate({
            "state_code": "KA",
            "state_name": "Karnataka",
            "city_name": "Bengaluru",
            "tier": "Tier 1",
            "rto_code": "KA-01",
            "rto_name": "Bangalore Central",
        })
        assert valid_res is True
        assert len(valid_errs) == 0

        # Invalid state code length
        inv_st, errs_st = validator.validate({"state_code": "KAR"})
        assert inv_st is False
        assert any("2 uppercase" in e for e in errs_st)

        # Invalid state code unknown
        inv_unk, errs_unk = validator.validate({"state_code": "ZZ"})
        assert inv_unk is False
        assert any("Unrecognized" in e for e in errs_unk)

        # Hierarchical mismatch: RTO code DL-01 inside State KA
        inv_hier, errs_hier = validator.validate({
            "state_code": "KA",
            "rto_code": "DL-01",
        })
        assert inv_hier is False
        assert any("Hierarchical mismatch" in e for e in errs_hier)

    def test_validator_status_classification(self):
        """classify_status correctly distinguishes AUTHORITATIVE_MATCH, FORMAT_VALID, and UNVERIFIED."""
        assert LocationDataValidator.classify_status("KA-01", is_authoritative=True) == "AUTHORITATIVE_MATCH"
        assert LocationDataValidator.classify_status("KA-01", is_authoritative=False) == "FORMAT_VALID"
        assert LocationDataValidator.classify_status("INVALID-CODE", is_authoritative=True) == "UNVERIFIED"

    def test_mapper_hierarchical_structure(self):
        """Mapper converts normalized dictionaries into hierarchical Country->State->City->RTO structure."""
        mapper = GovernmentLocationMapper()
        mapped = mapper.map_to_canonical({
            "source_record_id": "MORTH-KA-01",
            "state_name": "Karnataka",
            "state_code": "KA",
            "region_type": "STATE",
            "city_name": "Bengaluru",
            "city_slug": "bengaluru",
            "tier": "Tier 1",
            "rto_code": "KA-01",
            "rto_name": "Bangalore Central",
            "jurisdiction": "Koramangala",
            "effective_date": None,
        })
        assert mapped["country"]["name"] == "India"
        assert mapped["state"]["code"] == "KA"
        assert mapped["city"]["slug"] == "bengaluru"
        assert mapped["rto"]["code"] == "KA-01"
        assert mapped["rto"]["source_record_id"] == "MORTH-KA-01"


class TestGovernmentLocationPipelineAndDeduplication:
    @pytest.mark.asyncio
    async def test_government_location_end_to_end_ingestion(self, db_session: AsyncSession):
        """Government location adapter executes full Fetch -> Stage -> Validate -> Map -> Canonical workflow."""
        adapter = GovernmentLocationDataSourceAdapter()
        run = await IngestionService.run_adapter(db_session, adapter, notes="Unit test gov location run")

        assert run.id is not None
        assert run.status == IngestionRunStatus.COMPLETED.value
        assert run.records_seen >= 10
        assert run.records_created >= 10
        assert run.records_rejected == 0
        assert run.error_count == 0

        # Verify Data Source was registered as OFFICIAL_GOVERNMENT
        ds = await db_session.get(DataSource, run.data_source_id)
        assert ds is not None
        assert ds.source_type == DataSourceType.OFFICIAL_GOVERNMENT.value
        assert ds.trust_level == 100

        # Verify raw records staged with SHA-256 payload hash
        raw_recs = (
            await db_session.execute(
                select(RawIngestionRecord).where(RawIngestionRecord.ingestion_run_id == run.id)
            )
        ).scalars().all()
        assert len(raw_recs) == run.records_seen
        assert all(len(r.payload_hash) == 64 for r in raw_recs)
        assert all(r.validation_status == "VALID" for r in raw_recs)

        # Verify canonical entities created
        ka_rto = (
            await db_session.execute(
                select(RtoOffice).where(RtoOffice.code == "KA-01")
            )
        ).scalars().first()
        assert ka_rto is not None
        assert ka_rto.source_id == ds.id
        assert ka_rto.source_record_id == "MORTH-KA-01-KORAMANGALA"

    @pytest.mark.asyncio
    async def test_idempotent_repeat_ingestion_produces_no_duplicates(self, db_session: AsyncSession):
        """Repeating the exact same government ingestion run is idempotent and creates 0 duplicate entities."""
        adapter = GovernmentLocationDataSourceAdapter()

        # Run 1
        run1 = await IngestionService.run_adapter(db_session, adapter, notes="Run 1")
        assert run1.status == IngestionRunStatus.COMPLETED.value
        rto_count_1 = (await db_session.execute(select(func.count(RtoOffice.id)))).scalar()

        # Run 2 (Same data)
        run2 = await IngestionService.run_adapter(db_session, adapter, notes="Run 2")
        assert run2.status == IngestionRunStatus.COMPLETED.value
        rto_count_2 = (await db_session.execute(select(func.count(RtoOffice.id)))).scalar()

        assert rto_count_1 == rto_count_2
        assert run2.records_created == 0

    @pytest.mark.asyncio
    async def test_authoritative_provenance_attaches_to_seeded_entities(self, db_session: AsyncSession):
        """When authoritative government data matches pre-existing DEMO entities, provenance updates without destroying records."""
        await seed_database(db_session)

        # Check initial state of KA-01 before government ingestion
        ka_rto_before = (
            await db_session.execute(
                select(RtoOffice).where(RtoOffice.code == "KA-01")
            )
        ).scalars().first()
        assert ka_rto_before is not None
        initial_id = ka_rto_before.id

        # Ingest authoritative MoRTH data
        adapter = GovernmentLocationDataSourceAdapter()
        run = await IngestionService.run_adapter(db_session, adapter, notes="Authoritative update run")
        assert run.status == IngestionRunStatus.COMPLETED.value

        # Check KA-01 after government ingestion
        ka_rto_after = (
            await db_session.execute(
                select(RtoOffice).where(RtoOffice.code == "KA-01")
            )
        ).scalars().first()
        assert ka_rto_after is not None
        assert ka_rto_after.id == initial_id  # Canonical ID preserved
        assert ka_rto_after.source_id == run.data_source_id  # Provenance updated to MoRTH
        assert ka_rto_after.source_record_id == "MORTH-KA-01-KORAMANGALA"
        assert ka_rto_after.retrieved_at is not None
