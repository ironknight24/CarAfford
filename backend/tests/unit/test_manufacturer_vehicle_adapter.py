import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import select

from app.core.ingestion_constants import (
    ConflictStatus,
    DataSourceType,
    IngestionEntityType,
    IngestionRunStatus,
    VerificationStatus,
)
from app.ingestion.adapters.manufacturer_vehicle_adapter import (
    BaseManufacturerVehicleAdapter,
    HyundaiVehicleDataSourceAdapter,
    ManufacturerVehicleFetcher,
    ManufacturerVehicleNormalizer,
    ManufacturerVehicleParser,
    MarutiSuzukiVehicleDataSourceAdapter,
    TataMotorsVehicleDataSourceAdapter,
)
from app.ingestion.base import compute_payload_hash
from app.ingestion.validators.pricing_validator import PriceDataValidator
from app.ingestion.validators.vehicle_validator import VehicleDataValidator
from app.models.data_source import DataSource
from app.models.ingestion import DataConflictRecord, IngestionRun, RawIngestionRecord
from app.models.pricing import VehiclePrice
from app.models.vehicle import CarModel, Manufacturer, Variant, VariantSpecification
from app.services.ingestion_service import IngestionService


class TestManufacturerVehicleAdapterComponents:
    """Validates fetcher, parser, normalizer, and validator components for OEM adapters."""

    def test_adapter_metadata_and_trust_levels(self):
        tata = TataMotorsVehicleDataSourceAdapter()
        maruti = MarutiSuzukiVehicleDataSourceAdapter()
        hyundai = HyundaiVehicleDataSourceAdapter()

        assert tata.source_slug == "tata-motors-official"
        assert tata.source_type == DataSourceType.OFFICIAL_MANUFACTURER
        assert tata.trust_level == 95
        assert tata.dataset_name == "tata_vehicles"
        assert tata.entity_type == IngestionEntityType.VEHICLE

        assert maruti.source_slug == "maruti-suzuki-official"
        assert maruti.source_type == DataSourceType.OFFICIAL_MANUFACTURER
        assert maruti.trust_level == 95

        assert hyundai.source_slug == "hyundai-motor-india-official"
        assert hyundai.source_type == DataSourceType.OFFICIAL_MANUFACTURER
        assert hyundai.trust_level == 95

    @pytest.mark.asyncio
    async def test_fetcher_fixture_fallback_and_records(self):
        tata = TataMotorsVehicleDataSourceAdapter(mode="FIXTURE_ONLY")
        records = await tata.get_fetcher().fetch()
        assert len(records) >= 5
        punch = next((r for r in records if "Punch" in r["model_name"]), None)
        assert punch is not None
        assert punch["manufacturer_name"] == "Tata Motors"
        assert punch["fuel_type"] in {"Petrol", "Electric"}

    def test_parser_and_normalizer_specifications(self):
        parser = ManufacturerVehicleParser()
        normalizer = ManufacturerVehicleNormalizer()

        raw_item = {
            "source_record_id": "TEST-EV-01",
            "manufacturer_name": "tata motors passenger vehicles",
            "model_name": "Curvv.ev",
            "variant_name": "Curvv.ev Empowered Plus 55",
            "body_type": "compact suv",
            "fuel_type": "EV",
            "transmission": "Automatic",
            "battery_capacity_kwh": "55.0",
            "range_km": "502.0",
            "engine_power_bhp": "165.0",
            "torque_nm": "215.0",
            "seating_capacity": "5",
            "boot_space_l": "500",
            "airbags_count": "6",
            "safety_rating_stars": "5",
            "ex_showroom_price": "2199000.00",
            "effective_from": "2026-01-01T00:00:00Z",
        }

        parsed = parser.parse(raw_item)
        normalized = normalizer.normalize(parsed)

        assert normalized["manufacturer_name"] == "Tata Motors"
        assert normalized["model_name"] == "Curvv.ev"
        assert normalized["fuel_type"] == "Electric"
        assert normalized["body_type"] == "SUV"
        assert normalized["battery_capacity_kwh"] == Decimal("55.0")
        assert normalized["range_km"] == Decimal("502.0")
        assert normalized["engine_cc"] is None  # EV must have engine_cc = None
        assert normalized["ex_showroom_price"] == Decimal("2199000.00")

    def test_vehicle_validator_and_price_validator(self):
        v_validator = VehicleDataValidator()
        p_validator = PriceDataValidator()

        # Valid EV item
        valid_ev = {
            "manufacturer_name": "Tata Motors",
            "model_name": "Nexon.ev",
            "variant_name": "Nexon.ev Empowered Plus 45",
            "fuel_type": "Electric",
            "transmission": "Automatic",
            "body_type": "SUV",
            "battery_capacity_kwh": Decimal("45.0"),
            "range_km": Decimal("489.0"),
            "seating_capacity": 5,
            "airbags_count": 6,
            "safety_rating_stars": 5,
        }
        is_valid, errors = v_validator.validate(valid_ev)
        assert is_valid is True
        assert len(errors) == 0

        # Invalid: EV with engine displacement
        invalid_ev = dict(valid_ev, engine_cc=1200)
        is_valid_inv, errors_inv = v_validator.validate(invalid_ev)
        assert is_valid_inv is False
        assert any("electric vehicles cannot have engine_cc" in e for e in errors_inv)

        # Price validation
        valid_price = {
            "ex_showroom_price": Decimal("1699000.00"),
            "effective_from": "2026-01-01T00:00:00Z",
            "effective_to": "2026-12-31T23:59:59Z",
        }
        is_p_valid, p_errors = p_validator.validate(valid_price)
        assert is_p_valid is True

        # Invalid price: negative or out of automotive bounds
        invalid_price = {
            "ex_showroom_price": Decimal("-500.00"),
            "effective_from": "2026-01-01T00:00:00Z",
        }
        is_p_inv, p_inv_errors = p_validator.validate(invalid_price)
        assert is_p_inv is False
        assert any("positive" in e for e in p_inv_errors)


@pytest.mark.asyncio
class TestManufacturerVehiclePipelineAndDeduplication:
    """Validates end-to-end ingestion, provenance attachment, deduplication, and effective-dated pricing."""

    async def test_end_to_end_oem_ingestion_and_provenance(self, db_session):
        # 1. Run Tata Motors adapter
        tata_adapter = TataMotorsVehicleDataSourceAdapter()
        run = await IngestionService.run_adapter(db=db_session, adapter=tata_adapter)

        assert run.status == IngestionRunStatus.COMPLETED.value
        assert run.records_seen >= 5
        assert run.records_created > 0
        assert run.error_count == 0

        # 2. Verify Data Source registration
        ds_res = await db_session.execute(
            select(DataSource).where(DataSource.slug == "tata-motors-official")
        )
        ds = ds_res.scalars().first()
        assert ds is not None
        assert ds.trust_level == 95
        assert ds.provider_type == "oem"

        # 3. Verify Manufacturer provenance
        mfg_res = await db_session.execute(
            select(Manufacturer).where(Manufacturer.name == "Tata Motors")
        )
        mfg = mfg_res.scalars().first()
        assert mfg is not None
        assert mfg.source_id == ds.id
        assert mfg.verification_status == VerificationStatus.VERIFIED.value

        # 4. Verify Variant and VariantSpecification
        var_res = await db_session.execute(
            select(Variant).where(Variant.name == "Punch Pure 1.2 MT")
        )
        var = var_res.scalars().first()
        assert var is not None
        assert var.source_id == ds.id
        assert var.verification_status == VerificationStatus.VERIFIED.value
        assert var.seating_capacity == 5
        assert var.engine_cc == 1199

        spec_res = await db_session.execute(
            select(VariantSpecification).where(VariantSpecification.variant_id == var.id)
        )
        spec = spec_res.scalars().first()
        assert spec is not None
        assert spec.boot_space_l == 366
        assert spec.safety_rating_stars == 5

        # 5. Verify Active VehiclePrice
        price_res = await db_session.execute(
            select(VehiclePrice).where(
                VehiclePrice.variant_id == var.id,
                VehiclePrice.effective_to.is_(None),
            )
        )
        price = price_res.scalars().first()
        assert price is not None
        assert price.ex_showroom_price == Decimal("612900.00")
        assert price.source_id == ds.id
        assert price.verification_status == VerificationStatus.VERIFIED.value

    async def test_idempotent_reingestion_skips_unchanged_records(self, db_session):
        maruti_adapter = MarutiSuzukiVehicleDataSourceAdapter()

        # First run
        run1 = await IngestionService.run_adapter(db=db_session, adapter=maruti_adapter)
        created_count = run1.records_created

        # Second run (exact same payload)
        run2 = await IngestionService.run_adapter(db=db_session, adapter=maruti_adapter)
        assert run2.records_created == 0
        assert run2.records_unchanged == run1.records_seen

    async def test_effective_dated_price_update_preserves_history(self, db_session):
        # 1. Ingest initial Hyundai records
        hyundai_adapter = HyundaiVehicleDataSourceAdapter()
        await IngestionService.run_adapter(db=db_session, adapter=hyundai_adapter)

        # 2. Locate Creta E variant
        var_res = await db_session.execute(
            select(Variant).where(Variant.name == "Creta E 1.5 Petrol 6MT")
        )
        var = var_res.scalars().first()
        assert var is not None

        # 3. Simulate new price revision payload with effective date progression
        new_price_val = Decimal("1125000.00")
        eff_from = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)

        updated_data = {
            "manufacturer_name": "Hyundai",
            "model_name": "Creta",
            "variant_name": "Creta E 1.5 Petrol 6MT",
            "fuel_type": "Petrol",
            "transmission": "Manual",
            "ex_showroom_price": new_price_val,
            "effective_from": eff_from,
            "verification_status": VerificationStatus.VERIFIED.value,
        }

        # Resolve DataSource
        ds = await IngestionService.get_or_create_data_source(
            db=db_session,
            name="Hyundai Motor India Official Catalogue & Pricing",
            slug="hyundai-motor-india-official",
            source_type=DataSourceType.OFFICIAL_MANUFACTURER,
        )

        status = await IngestionService._promote_vehicle_to_canonical(
            db=db_session,
            data=updated_data,
            source_id=ds.id,
            source_record_id="HMI-CRETA-E-MT-V2",
        )
        assert status == "UPDATED"

        # 4. Verify historical price was closed (effective_to = eff_from)
        all_prices = (
            await db_session.execute(
                select(VehiclePrice)
                .where(VehiclePrice.variant_id == var.id)
                .order_by(VehiclePrice.effective_from.asc())
            )
        ).scalars().all()

        assert len(all_prices) == 2
        old_price, current_price = all_prices[0], all_prices[1]

        assert old_price.ex_showroom_price == Decimal("1099900.00")
        assert (old_price.effective_to.replace(tzinfo=timezone.utc) if old_price.effective_to.tzinfo is None else old_price.effective_to) == eff_from

        assert current_price.ex_showroom_price == Decimal("1125000.00")
        assert (current_price.effective_from.replace(tzinfo=timezone.utc) if current_price.effective_from.tzinfo is None else current_price.effective_from) == eff_from
        assert current_price.effective_to is None
        assert current_price.source_record_id == "HMI-CRETA-E-MT-V2"
