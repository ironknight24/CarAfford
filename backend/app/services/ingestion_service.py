from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import func, select, update, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion_constants import (
    DataSourceType,
    IngestionRunStatus,
    VerificationStatus,
    DataFreshnessStatus,
    ConflictStatus,
    IngestionEntityType,
    DATASET_FRESHNESS_SLA_DAYS,
    DATA_SOURCE_DEFAULT_TRUST_LEVELS,
    DATA_QUALITY_WEIGHTS,
    INGESTION_DISCLAIMER,
)
from app.ingestion.base import DataSourceAdapter, compute_payload_hash
from app.models.data_source import DataSource
from app.models.ingestion import (
    DataConflictRecord,
    DataQualityReviewItem,
    IngestionRun,
    RawIngestionRecord,
)
from app.models.vehicle import Manufacturer, CarModel, Variant, VariantSpecification
from app.models.pricing import VehiclePrice
from app.models.location import Country, State, City, RtoOffice
from app.models.finance import (
    Bank,
    LoanProduct,
    InterestRate,
    LoanEligibilityRule,
    LoanFee,
)
from app.models.tax_rule import TaxRule, TaxRuleBracket
from app.models.tco import (
    FuelPrice,
    ElectricityTariff,
    MaintenanceCostBenchmark,
    InsuranceRenewalBenchmark,
    DepreciationBenchmark,
)
from app.schemas.ingestion import (
    DataQualityOverviewResponse,
    DataQualityScoreBreakdown,
    FreshnessReportItem,
    IngestionRunRead,
)


def _ensure_tz_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class IngestionService:
    """Core orchestration service for data ingestion, raw staging, deduplication, conflict tracking, and quality evaluation."""

    @classmethod
    async def get_or_create_data_source(
        cls,
        db: AsyncSession,
        name: str,
        slug: str,
        source_type: DataSourceType = DataSourceType.DEMO_SEED,
        provider_type: str = "aggregator",
        organization: Optional[str] = None,
        base_url: Optional[str] = None,
        trust_level: Optional[int] = None,
    ) -> DataSource:
        """Retrieves an existing data source or creates a new catalog entry."""
        res = await db.execute(select(DataSource).where(DataSource.slug == slug))
        ds = res.scalars().first()
        if ds:
            return ds

        assigned_trust = trust_level if trust_level is not None else DATA_SOURCE_DEFAULT_TRUST_LEVELS.get(source_type, 70)
        new_ds = DataSource(
            name=name,
            slug=slug,
            source_type=source_type.value,
            provider_type=provider_type,
            organization=organization or name,
            base_url=base_url,
            trust_level=assigned_trust,
            is_active=True,
        )
        db.add(new_ds)
        await db.flush()
        await db.refresh(new_ds)
        return new_ds

    @classmethod
    async def run_adapter(
        cls,
        db: AsyncSession,
        adapter: DataSourceAdapter,
        notes: Optional[str] = None,
    ) -> IngestionRun:
        """Executes the full Fetch -> Stage -> Parse -> Normalize -> Validate -> Map pipeline for an adapter."""
        # 1. Resolve Data Source
        ds = await cls.get_or_create_data_source(
            db=db,
            name=adapter.source_name,
            slug=adapter.source_slug,
            source_type=adapter.source_type,
            provider_type=getattr(adapter, "provider_type", "aggregator"),
            organization=getattr(adapter, "organization", None),
            base_url=getattr(adapter, "base_url", None),
            trust_level=getattr(adapter, "trust_level", None),
        )

        # 2. Create Ingestion Run
        run = IngestionRun(
            data_source_id=ds.id,
            dataset_name=adapter.dataset_name,
            started_at=datetime.now(timezone.utc),
            status=IngestionRunStatus.RUNNING.value,
            notes=notes or f"Automated ingestion for dataset {adapter.dataset_name}",
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        run_id = run.id

        fetcher = adapter.get_fetcher()
        parser = adapter.get_parser()
        normalizer = adapter.get_normalizer()
        validator = adapter.get_validator()
        mapper = adapter.get_mapper()

        try:
            # 3. Fetch Raw Data
            raw_items = await fetcher.fetch()
            run.records_seen = len(raw_items)

            for raw_payload in raw_items:
                payload_hash = compute_payload_hash(raw_payload)
                source_record_id = raw_payload.get("source_record_id")

                # Check deduplication on raw payload hash
                existing_raw = (
                    await db.execute(
                        select(RawIngestionRecord).where(
                            RawIngestionRecord.payload_hash == payload_hash,
                            RawIngestionRecord.ingestion_run_id == run_id,
                        )
                    )
                ).scalars().first()

                if existing_raw:
                    run.records_unchanged += 1
                    continue

                # Stage Raw Record
                raw_rec = RawIngestionRecord(
                    ingestion_run_id=run_id,
                    source_record_id=source_record_id,
                    entity_type=adapter.entity_type.value,
                    raw_payload=raw_payload,
                    payload_hash=payload_hash,
                    retrieved_at=datetime.now(timezone.utc),
                    parsing_status="PARSED",
                    validation_status="PENDING",
                )
                db.add(raw_rec)
                await db.flush()

                # Parse & Normalize
                try:
                    parsed = parser.parse(raw_payload)
                    normalized = normalizer.normalize(parsed)
                except Exception as ex:
                    raw_rec.parsing_status = "ERROR"
                    raw_rec.validation_status = "INVALID"
                    raw_rec.validation_errors = [{"error": f"Parsing exception: {str(ex)}"}]
                    run.error_count += 1
                    run.records_rejected += 1
                    continue

                # Validate
                is_valid, validation_errors = validator.validate(normalized)
                if not is_valid:
                    raw_rec.validation_status = "INVALID"
                    raw_rec.validation_errors = [{"error": err} for err in validation_errors]
                    run.validation_error_count += 1
                    run.records_rejected += 1
                    continue

                raw_rec.validation_status = "VALID"

                # Check for multi-source conflicts if entity identifier exists
                if adapter.entity_type == IngestionEntityType.LOCATION:
                    entity_ident = f"{normalized.get('state_code', '')} {normalized.get('rto_code', '')} {normalized.get('city_name', '')}".strip()
                elif adapter.entity_type == IngestionEntityType.FINANCE:
                    entity_ident = f"{normalized.get('bank_name', '')} {normalized.get('product_name', '')}".strip()
                elif adapter.entity_type == IngestionEntityType.TAX_RULE:
                    entity_ident = f"{normalized.get('state_code', '')} {normalized.get('tax_type', '')} {normalized.get('name', '')}".strip()
                elif adapter.entity_type == IngestionEntityType.FUEL_PRICE or normalized.get("tco_category") == "fuel_price":
                    entity_ident = f"{normalized.get('state_code', 'NATIONAL')} {normalized.get('city_name', 'ALL')} {normalized.get('fuel_type', '')}".strip()
                elif adapter.entity_type == IngestionEntityType.ELECTRICITY_TARIFF or normalized.get("tco_category") == "electricity_tariff":
                    entity_ident = f"{normalized.get('state_code', '')} {normalized.get('tariff_type', '')} {normalized.get('discom_name', '')}".strip()
                elif adapter.entity_type == IngestionEntityType.MAINTENANCE_COST or normalized.get("tco_category") == "maintenance":
                    entity_ident = f"{normalized.get('powertrain', '')} {normalized.get('segment', 'ALL')}".strip()
                elif adapter.entity_type == IngestionEntityType.INSURANCE_BENCHMARK or normalized.get("tco_category") == "insurance_renewal":
                    entity_ident = f"{normalized.get('fuel_type', 'ALL')} {normalized.get('segment', 'ALL')} INSURANCE".strip()
                elif adapter.entity_type == IngestionEntityType.DEPRECIATION_BENCHMARK or normalized.get("tco_category") == "depreciation":
                    entity_ident = f"{normalized.get('powertrain', 'ALL')} {normalized.get('segment', 'ALL')} DEPRECIATION".strip()
                else:
                    entity_ident = f"{normalized.get('manufacturer_name', '')} {normalized.get('model_name', '')} {normalized.get('variant_name', '')}".strip()

                if entity_ident:
                    await cls._check_conflicts(
                        db=db,
                        dataset_name=adapter.dataset_name,
                        entity_type=adapter.entity_type.value,
                        entity_identifier=entity_ident,
                        current_source_id=ds.id,
                        normalized_payload=normalized,
                    )

                # Map & Promote to Canonical if appropriate
                mapped_data = mapper.map_to_canonical(normalized)
                tco_cat = mapped_data.get("tco_category")
                if adapter.entity_type == IngestionEntityType.LOCATION:
                    promoted = await cls._promote_location_to_canonical(
                        db=db,
                        data=mapped_data,
                        source_id=ds.id,
                        source_record_id=source_record_id,
                    )
                elif adapter.entity_type == IngestionEntityType.FINANCE:
                    promoted = await cls._promote_finance_to_canonical(
                        db=db,
                        data=mapped_data,
                        source_id=ds.id,
                        source_record_id=source_record_id,
                    )
                elif adapter.entity_type == IngestionEntityType.TAX_RULE:
                    promoted = await cls._promote_tax_to_canonical(
                        db=db,
                        data=mapped_data,
                        source_id=ds.id,
                        source_record_id=source_record_id,
                    )
                elif adapter.entity_type == IngestionEntityType.FUEL_PRICE or tco_cat == "fuel_price":
                    promoted = await cls._promote_fuel_price_to_canonical(
                        db=db,
                        data=mapped_data,
                        source_id=ds.id,
                        source_record_id=source_record_id,
                    )
                elif adapter.entity_type == IngestionEntityType.ELECTRICITY_TARIFF or tco_cat == "electricity_tariff":
                    promoted = await cls._promote_electricity_tariff_to_canonical(
                        db=db,
                        data=mapped_data,
                        source_id=ds.id,
                        source_record_id=source_record_id,
                    )
                elif adapter.entity_type == IngestionEntityType.MAINTENANCE_COST or tco_cat == "maintenance":
                    promoted = await cls._promote_maintenance_to_canonical(
                        db=db,
                        data=mapped_data,
                        source_id=ds.id,
                        source_record_id=source_record_id,
                    )
                elif adapter.entity_type == IngestionEntityType.INSURANCE_BENCHMARK or tco_cat == "insurance_renewal":
                    promoted = await cls._promote_insurance_renewal_to_canonical(
                        db=db,
                        data=mapped_data,
                        source_id=ds.id,
                        source_record_id=source_record_id,
                    )
                elif adapter.entity_type == IngestionEntityType.DEPRECIATION_BENCHMARK or tco_cat == "depreciation":
                    promoted = await cls._promote_depreciation_to_canonical(
                        db=db,
                        data=mapped_data,
                        source_id=ds.id,
                        source_record_id=source_record_id,
                    )
                else:
                    promoted = await cls._promote_vehicle_to_canonical(
                        db=db,
                        data=mapped_data,
                        source_id=ds.id,
                        source_record_id=source_record_id,
                    )

                if promoted == "CREATED":
                    run.records_created += 1
                elif promoted == "UPDATED":
                    run.records_updated += 1
                else:
                    run.records_unchanged += 1

            # 4. Finalize Ingestion Run
            run.completed_at = datetime.now(timezone.utc)
            if run.error_count > 0 or run.validation_error_count > 0:
                run.status = IngestionRunStatus.PARTIAL.value if (run.records_created + run.records_updated) > 0 else IngestionRunStatus.FAILED.value
            else:
                run.status = IngestionRunStatus.COMPLETED.value

            ds.last_synced_at = datetime.now(timezone.utc)
            await db.commit()
            await db.refresh(run)
            return run

        except Exception as ex:
            await db.rollback()
            persisted_run = await db.get(IngestionRun, run_id)
            if persisted_run:
                persisted_run.status = IngestionRunStatus.FAILED.value
                persisted_run.completed_at = datetime.now(timezone.utc)
                persisted_run.error_count += 1
                persisted_run.notes = f"Ingestion run aborted: {str(ex)}"
                db.add(persisted_run)
                await db.commit()
                return persisted_run
            raise ex

    @classmethod
    async def _promote_vehicle_to_canonical(
        cls,
        db: AsyncSession,
        data: Dict[str, Any],
        source_id: int,
        source_record_id: Optional[str] = None,
    ) -> str:
        """Promotes validated vehicle & price data into canonical tables with deterministic matching and effective dating."""
        mfg_name = data.get("manufacturer_name")
        model_name = data.get("model_name")
        variant_name = data.get("variant_name")

        if not mfg_name or not model_name or not variant_name:
            return "UNCHANGED"

        now = datetime.now(timezone.utc)
        ver_status = data.get("verification_status", VerificationStatus.VERIFIED.value)

        # 1. Resolve Manufacturer
        mfg_slug = mfg_name.lower().replace(" ", "-")
        mfg_res = await db.execute(
            select(Manufacturer).where(
                (Manufacturer.slug == mfg_slug) | (Manufacturer.name.ilike(mfg_name))
            )
        )
        mfg = mfg_res.scalars().first()
        if not mfg:
            mfg = Manufacturer(
                name=mfg_name,
                slug=mfg_slug,
                country="India",
                is_active=True,
                source_id=source_id,
                source_record_id=source_record_id,
                retrieved_at=now,
                verification_status=ver_status,
            )
            db.add(mfg)
            await db.flush()
        else:
            mfg.source_id = source_id
            mfg.source_record_id = source_record_id
            mfg.retrieved_at = now
            mfg.verification_status = ver_status

        # 2. Resolve Car Model
        model_slug = f"{mfg.slug}-{model_name.lower().replace(' ', '-')}"
        model_res = await db.execute(
            select(CarModel).where(
                ((CarModel.manufacturer_id == mfg.id) & (CarModel.name.ilike(model_name)))
                | (CarModel.slug == model_slug)
            )
        )
        car_model = model_res.scalars().first()
        if not car_model:
            car_model = CarModel(
                manufacturer_id=mfg.id,
                name=model_name,
                slug=model_slug,
                body_type=data.get("body_type", "SUV"),
                segment=data.get("segment", "Compact SUV"),
                launch_year=data.get("launch_year", 2024),
                image_url=data.get("image_url"),
                is_active=not data.get("is_discontinued", False),
                source_id=source_id,
                source_record_id=source_record_id,
                retrieved_at=now,
                verification_status=ver_status,
            )
            db.add(car_model)
            await db.flush()
        else:
            if data.get("body_type"):
                car_model.body_type = data["body_type"]
            if data.get("segment"):
                car_model.segment = data["segment"]
            car_model.source_id = source_id
            car_model.source_record_id = source_record_id
            car_model.retrieved_at = now
            car_model.verification_status = ver_status

        # 3. Resolve Variant
        variant_slug = f"{car_model.slug}-{variant_name.lower().replace(' ', '-')}"
        fuel = data.get("fuel_type", "Petrol")
        trans = data.get("transmission", "Manual")
        
        var_res = await db.execute(
            select(Variant).where(
                ((Variant.model_id == car_model.id) & (Variant.name.ilike(variant_name)))
                | (Variant.slug == variant_slug)
            )
        )
        variant = var_res.scalars().first()
        is_created = False
        if not variant:
            variant = Variant(
                model_id=car_model.id,
                name=variant_name,
                slug=variant_slug,
                trim_level=data.get("trim_level", "Base"),
                fuel_type=fuel,
                transmission=trans,
                drivetrain=data.get("drivetrain", "FWD"),
                engine_cc=data.get("engine_cc"),
                engine_power_bhp=data.get("engine_power_bhp"),
                torque_nm=data.get("torque_nm"),
                seating_capacity=data.get("seating_capacity", 5),
                mileage_claimed=data.get("arai_mileage_kmpl"),
                battery_capacity_kwh=data.get("battery_capacity_kwh"),
                range_km=data.get("range_km"),
                active=not data.get("is_discontinued", False),
                source_id=source_id,
                source_record_id=source_record_id,
                retrieved_at=now,
                verification_status=ver_status,
            )
            db.add(variant)
            await db.flush()
            is_created = True
        else:
            variant.trim_level = data.get("trim_level", variant.trim_level)
            variant.fuel_type = fuel
            variant.transmission = trans
            if data.get("engine_cc") is not None:
                variant.engine_cc = data["engine_cc"]
            if data.get("engine_power_bhp") is not None:
                variant.engine_power_bhp = data["engine_power_bhp"]
            if data.get("torque_nm") is not None:
                variant.torque_nm = data["torque_nm"]
            if data.get("battery_capacity_kwh") is not None:
                variant.battery_capacity_kwh = data["battery_capacity_kwh"]
            if data.get("range_km") is not None:
                variant.range_km = data["range_km"]
            if data.get("arai_mileage_kmpl") is not None:
                variant.mileage_claimed = data["arai_mileage_kmpl"]
            if data.get("seating_capacity") is not None:
                variant.seating_capacity = data["seating_capacity"]
            variant.source_id = source_id
            variant.source_record_id = source_record_id
            variant.retrieved_at = now
            variant.verification_status = ver_status

        # 4. Sync VariantSpecification
        spec_res = await db.execute(
            select(VariantSpecification).where(VariantSpecification.variant_id == variant.id)
        )
        spec = spec_res.scalars().first()
        if not spec:
            spec = VariantSpecification(
                variant_id=variant.id,
                engine_displacement_cc=data.get("engine_cc"),
                battery_capacity_kwh=data.get("battery_capacity_kwh"),
                max_power_bhp=data.get("engine_power_bhp"),
                max_torque_nm=data.get("torque_nm"),
                arai_mileage_kmpl=data.get("arai_mileage_kmpl") or Decimal("18.00"),
                boot_space_l=data.get("boot_space_l"),
                airbags_count=data.get("airbags_count", 6),
                safety_rating_stars=data.get("safety_rating_stars"),
                ground_clearance_mm=data.get("ground_clearance_mm"),
                fuel_tank_capacity_l=data.get("fuel_tank_capacity_l"),
            )
            db.add(spec)
            await db.flush()
        else:
            if data.get("engine_cc") is not None:
                spec.engine_displacement_cc = data["engine_cc"]
            if data.get("battery_capacity_kwh") is not None:
                spec.battery_capacity_kwh = data["battery_capacity_kwh"]
            if data.get("engine_power_bhp") is not None:
                spec.max_power_bhp = data["engine_power_bhp"]
            if data.get("torque_nm") is not None:
                spec.max_torque_nm = data["torque_nm"]
            if data.get("arai_mileage_kmpl") is not None:
                spec.arai_mileage_kmpl = data["arai_mileage_kmpl"]
            if data.get("boot_space_l") is not None:
                spec.boot_space_l = data["boot_space_l"]
            if data.get("airbags_count") is not None:
                spec.airbags_count = data["airbags_count"]
            if data.get("safety_rating_stars") is not None:
                spec.safety_rating_stars = data["safety_rating_stars"]
            if data.get("ground_clearance_mm") is not None:
                spec.ground_clearance_mm = data["ground_clearance_mm"]

        # 5. Manage Effective-Dated Ex-Showroom Price
        ex_price = data.get("ex_showroom_price")
        if ex_price:
            eff_from = data.get("effective_from")
            if isinstance(eff_from, str):
                eff_from_dt = datetime.fromisoformat(eff_from.replace("Z", "+00:00"))
            elif isinstance(eff_from, datetime):
                eff_from_dt = eff_from
            else:
                eff_from_dt = now

            # Query currently active price (effective_to is NULL)
            active_price = (
                await db.execute(
                    select(VehiclePrice).where(
                        VehiclePrice.variant_id == variant.id,
                        VehiclePrice.effective_to.is_(None),
                    )
                )
            ).scalars().first()

            if active_price:
                if Decimal(str(active_price.ex_showroom_price)) != Decimal(str(ex_price)):
                    # Close the previous record
                    active_price.effective_to = eff_from_dt
                    new_price = VehiclePrice(
                        variant_id=variant.id,
                        ex_showroom_price=Decimal(str(ex_price)),
                        price_type=data.get("price_type", "EX_SHOWROOM"),
                        effective_from=eff_from_dt,
                        effective_to=None,
                        source_id=source_id,
                        source_record_id=source_record_id,
                        retrieved_at=now,
                        verification_status=ver_status,
                    )
                    db.add(new_price)
                    await db.flush()
                    return "UPDATED"
                else:
                    # Update provenance on unchanged price
                    active_price.source_id = source_id
                    active_price.source_record_id = source_record_id
                    active_price.retrieved_at = now
                    active_price.verification_status = ver_status
                    return "CREATED" if is_created else "UNCHANGED"
            else:
                new_price = VehiclePrice(
                    variant_id=variant.id,
                    ex_showroom_price=Decimal(str(ex_price)),
                    price_type=data.get("price_type", "EX_SHOWROOM"),
                    effective_from=eff_from_dt,
                    effective_to=None,
                    source_id=source_id,
                    source_record_id=source_record_id,
                    retrieved_at=now,
                    verification_status=ver_status,
                )
                db.add(new_price)
                await db.flush()
                return "CREATED"

        return "CREATED" if is_created else "UNCHANGED"

    @classmethod
    async def _promote_location_to_canonical(
        cls,
        db: AsyncSession,
        data: Dict[str, Any],
        source_id: int,
        source_record_id: Optional[str] = None,
    ) -> str:
        """Promotes validated location data (Country -> State -> City -> RTO) into canonical tables with deterministic matching."""
        state_data = data.get("state", {})
        city_data = data.get("city", {})
        rto_data = data.get("rto", {})

        state_name = state_data.get("name")
        state_code = state_data.get("code")
        region_type = state_data.get("region_type", "STATE")

        if not state_code:
            return "UNCHANGED"

        now = datetime.now(timezone.utc)

        # 1. Resolve Country (Default India, id=1)
        country = (await db.execute(select(Country).where(Country.iso_code == "IN"))).scalars().first()
        if not country:
            country = Country(
                name="India",
                iso_code="IN",
                iso3_code="IND",
                active=True,
            )
            db.add(country)
            await db.flush()
        country_id = country.id

        # 2. Resolve State
        state_res = await db.execute(
            select(State).where(
                (State.code == state_code) | (State.name.ilike(state_name))
            )
        )
        state = state_res.scalars().first()
        state_created = False
        if not state:
            state = State(
                country_id=country_id,
                name=state_name or state_code,
                code=state_code,
                region_type=region_type,
                active=True,
                source_id=source_id,
                source_record_id=source_record_id,
                retrieved_at=now,
            )
            db.add(state)
            await db.flush()
            state_created = True
        else:
            state.source_id = source_id
            state.source_record_id = source_record_id
            state.retrieved_at = now

        # 3. Resolve City
        city_name = city_data.get("name")
        city_slug = city_data.get("slug")
        city_tier = city_data.get("tier", "Tier 1")
        city = None
        city_created = False

        if city_name:
            city_res = await db.execute(
                select(City).where(
                    (City.state_id == state.id) &
                    ((City.slug == city_slug) | (City.name.ilike(city_name)))
                )
            )
            city = city_res.scalars().first()
            if not city:
                city = City(
                    state_id=state.id,
                    name=city_name,
                    slug=city_slug or city_name.lower().replace(" ", "-"),
                    tier=city_tier,
                    active=True,
                    source_id=source_id,
                    source_record_id=source_record_id,
                    retrieved_at=now,
                )
                db.add(city)
                await db.flush()
                city_created = True
            else:
                city.source_id = source_id
                city.source_record_id = source_record_id
                city.retrieved_at = now

        # 4. Resolve RTO Office
        rto_code = rto_data.get("code")
        rto_name = rto_data.get("name")
        jurisdiction = rto_data.get("jurisdiction")
        rto_record_id = rto_data.get("source_record_id") or source_record_id

        if not rto_code:
            return "CREATED" if (state_created or city_created) else "UNCHANGED"

        rto_res = await db.execute(
            select(RtoOffice).where(
                (RtoOffice.state_id == state.id) &
                ((RtoOffice.code == rto_code) | (RtoOffice.source_record_id == rto_record_id))
            )
        )
        rto = rto_res.scalars().first()
        if not rto:
            rto = RtoOffice(
                state_id=state.id,
                city_id=city.id if city else None,
                code=rto_code,
                name=rto_name or f"RTO {rto_code}",
                jurisdiction=jurisdiction,
                active=True,
                source_id=source_id,
                source_record_id=rto_record_id,
                retrieved_at=now,
            )
            db.add(rto)
            await db.flush()
            return "CREATED"
        else:
            # Update existing RTO with authoritative provenance and linked city if missing
            rto.source_id = source_id
            rto.source_record_id = rto_record_id
            rto.retrieved_at = now
            if city and not rto.city_id:
                rto.city_id = city.id
            if jurisdiction and not rto.jurisdiction:
                rto.jurisdiction = jurisdiction
            await db.flush()
            return "UPDATED"

    @classmethod
    async def _promote_finance_to_canonical(
        cls,
        db: AsyncSession,
        data: Dict[str, Any],
        source_id: int,
        source_record_id: Optional[str] = None,
    ) -> str:
        """Promotes validated bank loan products, interest rate tiers, eligibility rules, and fee structures into canonical tables."""
        bank_name = data.get("bank_name")
        product_name = data.get("product_name")

        if not bank_name or not product_name:
            return "UNCHANGED"

        now = datetime.now(timezone.utc)
        ver_status = data.get("verification_status", VerificationStatus.VERIFIED.value)
        is_created = False
        is_updated = False

        # 1. Resolve Bank
        bank_slug = bank_name.lower().replace(" ", "-")
        bank_res = await db.execute(
            select(Bank).where(
                (Bank.slug == bank_slug) | (Bank.name.ilike(bank_name))
            )
        )
        bank = bank_res.scalars().first()
        if not bank:
            bank = Bank(
                name=bank_name,
                slug=bank_slug,
                bank_type=data.get("bank_type", "Public"),
                website_url=data.get("website_url"),
                active=True,
                source_id=source_id,
                source_record_id=source_record_id,
                retrieved_at=now,
                verification_status=ver_status,
            )
            db.add(bank)
            await db.flush()
            is_created = True
        else:
            if data.get("website_url") and not bank.website_url:
                bank.website_url = data["website_url"]
            bank.source_id = source_id
            bank.source_record_id = source_record_id
            bank.retrieved_at = now
            bank.verification_status = ver_status

        # 2. Resolve Loan Product
        product_slug = f"{bank.slug}-{product_name.lower().replace(' ', '-')}"
        prod_res = await db.execute(
            select(LoanProduct).where(
                (LoanProduct.bank_id == bank.id) &
                ((LoanProduct.slug == product_slug) | (LoanProduct.name.ilike(product_name)))
            )
        )
        loan_product = prod_res.scalars().first()
        if not loan_product:
            loan_product = LoanProduct(
                bank_id=bank.id,
                name=product_name,
                slug=product_slug,
                vehicle_type=data.get("vehicle_type", "CAR"),
                vehicle_condition=data.get("vehicle_condition", "NEW"),
                product_category=data.get("product_category", "STANDARD"),
                min_loan_amount=data.get("min_loan_amount", Decimal("100000.00")),
                max_loan_amount=data.get("max_loan_amount", Decimal("100000000.00")),
                min_tenure_months=data.get("min_tenure_months", 12),
                max_tenure_months=data.get("max_tenure_months", 84),
                max_ltv_percent=data.get("max_ltv_percent", Decimal("90.00")),
                processing_fee_percent=data.get("processing_fee_percent", Decimal("0.50")),
                min_processing_fee=data.get("min_processing_fee", Decimal("1500.00")),
                max_processing_fee=data.get("max_processing_fee", Decimal("10000.00")),
                description=data.get("description"),
                active=True,
                source_id=source_id,
                source_record_id=source_record_id,
                retrieved_at=now,
                verification_status=ver_status,
            )
            db.add(loan_product)
            await db.flush()
            is_created = True
        else:
            if data.get("vehicle_type"):
                loan_product.vehicle_type = data["vehicle_type"]
            if data.get("vehicle_condition"):
                loan_product.vehicle_condition = data["vehicle_condition"]
            if data.get("product_category"):
                loan_product.product_category = data["product_category"]
            if data.get("min_loan_amount") is not None:
                loan_product.min_loan_amount = data["min_loan_amount"]
            if data.get("max_loan_amount") is not None:
                loan_product.max_loan_amount = data["max_loan_amount"]
            if data.get("min_tenure_months") is not None:
                loan_product.min_tenure_months = data["min_tenure_months"]
            if data.get("max_tenure_months") is not None:
                loan_product.max_tenure_months = data["max_tenure_months"]
            if data.get("max_ltv_percent") is not None:
                loan_product.max_ltv_percent = data["max_ltv_percent"]
            if data.get("processing_fee_percent") is not None:
                loan_product.processing_fee_percent = data["processing_fee_percent"]
            if data.get("min_processing_fee") is not None:
                loan_product.min_processing_fee = data["min_processing_fee"]
            if data.get("max_processing_fee") is not None:
                loan_product.max_processing_fee = data["max_processing_fee"]
            if data.get("description"):
                loan_product.description = data["description"]
            loan_product.source_id = source_id
            loan_product.source_record_id = source_record_id
            loan_product.retrieved_at = now
            loan_product.verification_status = ver_status

        # 3. Resolve & Promote Interest Rates with Temporal Effective Dating (History Preservation)
        rates_data = data.get("rates", [])
        for r_item in rates_data:
            ann_rate = r_item.get("annual_interest_rate")
            if ann_rate is None:
                continue

            r_type = r_item.get("rate_type", "FLOATING")
            min_c = r_item.get("min_credit_score")
            max_c = r_item.get("max_credit_score")
            min_t = r_item.get("min_tenure_months")
            max_t = r_item.get("max_tenure_months")
            min_a = r_item.get("min_loan_amount")
            max_a = r_item.get("max_loan_amount")
            priority = r_item.get("priority", 100)

            r_eff_from = r_item.get("effective_from") or data.get("effective_from")
            if isinstance(r_eff_from, str):
                eff_from_dt = datetime.fromisoformat(r_eff_from.replace("Z", "+00:00"))
            elif isinstance(r_eff_from, datetime):
                eff_from_dt = r_eff_from
            else:
                eff_from_dt = now

            # Query existing active matching rate
            conds = [
                InterestRate.loan_product_id == loan_product.id,
                InterestRate.rate_type == r_type,
                InterestRate.active.is_(True),
                InterestRate.effective_to.is_(None),
            ]
            if min_c is not None:
                conds.append(InterestRate.min_credit_score == min_c)
            else:
                conds.append(InterestRate.min_credit_score.is_(None))

            if max_c is not None:
                conds.append(InterestRate.max_credit_score == max_c)
            else:
                conds.append(InterestRate.max_credit_score.is_(None))

            if min_t is not None:
                conds.append(InterestRate.min_tenure_months == min_t)
            else:
                conds.append(InterestRate.min_tenure_months.is_(None))

            if max_t is not None:
                conds.append(InterestRate.max_tenure_months == max_t)
            else:
                conds.append(InterestRate.max_tenure_months.is_(None))

            matching_rate = (await db.execute(select(InterestRate).where(and_(*conds)))).scalars().first()

            if matching_rate:
                if Decimal(str(matching_rate.annual_interest_rate)) != Decimal(str(ann_rate)):
                    # Historical rate changed: close previous and insert new active rate
                    matching_rate.effective_to = eff_from_dt
                    matching_rate.active = False
                    new_rate = InterestRate(
                        loan_product_id=loan_product.id,
                        annual_interest_rate=Decimal(str(ann_rate)),
                        rate_type=r_type,
                        min_credit_score=min_c,
                        max_credit_score=max_c,
                        min_tenure_months=min_t,
                        max_tenure_months=max_t,
                        min_loan_amount=min_a,
                        max_loan_amount=max_a,
                        priority=priority,
                        effective_from=eff_from_dt,
                        effective_to=None,
                        active=True,
                        source_id=source_id,
                        source_record_id=source_record_id,
                        retrieved_at=now,
                        verification_status=ver_status,
                    )
                    db.add(new_rate)
                    is_updated = True
                else:
                    matching_rate.source_id = source_id
                    matching_rate.source_record_id = source_record_id
                    matching_rate.retrieved_at = now
                    matching_rate.verification_status = ver_status
                    matching_rate.priority = priority
            else:
                new_rate = InterestRate(
                    loan_product_id=loan_product.id,
                    annual_interest_rate=Decimal(str(ann_rate)),
                    rate_type=r_type,
                    min_credit_score=min_c,
                    max_credit_score=max_c,
                    min_tenure_months=min_t,
                    max_tenure_months=max_t,
                    min_loan_amount=min_a,
                    max_loan_amount=max_a,
                    priority=priority,
                    effective_from=eff_from_dt,
                    effective_to=None,
                    active=True,
                    source_id=source_id,
                    source_record_id=source_record_id,
                    retrieved_at=now,
                    verification_status=ver_status,
                )
                db.add(new_rate)
                is_created = True

        # 4. Resolve & Promote Eligibility Rules
        elig_data = data.get("eligibility_rules", [])
        for e_item in elig_data:
            rule_name = e_item.get("rule_name", "General Eligibility Criteria")
            existing_rule = (
                await db.execute(
                    select(LoanEligibilityRule).where(
                        LoanEligibilityRule.loan_product_id == loan_product.id,
                        LoanEligibilityRule.rule_name == rule_name,
                        LoanEligibilityRule.active.is_(True),
                    )
                )
            ).scalars().first()

            e_eff_from = e_item.get("effective_from") or data.get("effective_from")
            if isinstance(e_eff_from, str):
                eff_from_dt = datetime.fromisoformat(e_eff_from.replace("Z", "+00:00"))
            elif isinstance(e_eff_from, datetime):
                eff_from_dt = e_eff_from
            else:
                eff_from_dt = now

            if existing_rule:
                if e_item.get("min_monthly_income") is not None:
                    existing_rule.min_monthly_income = e_item["min_monthly_income"]
                if e_item.get("min_credit_score") is not None:
                    existing_rule.min_credit_score = e_item["min_credit_score"]
                if e_item.get("max_credit_score") is not None:
                    existing_rule.max_credit_score = e_item["max_credit_score"]
                if e_item.get("max_loan_amount") is not None:
                    existing_rule.max_loan_amount = e_item["max_loan_amount"]
                if e_item.get("max_ltv_percent") is not None:
                    existing_rule.max_ltv_percent = e_item["max_ltv_percent"]
                if e_item.get("max_foir_percent") is not None:
                    existing_rule.max_foir_percent = e_item["max_foir_percent"]
                if e_item.get("min_age_years") is not None:
                    existing_rule.min_age_years = e_item["min_age_years"]
                if e_item.get("max_age_years") is not None:
                    existing_rule.max_age_years = e_item["max_age_years"]
                if e_item.get("min_employment_months") is not None:
                    existing_rule.min_employment_months = e_item["min_employment_months"]
                if e_item.get("allowed_employment_types") is not None:
                    existing_rule.allowed_employment_types = e_item["allowed_employment_types"]
                if e_item.get("allowed_residency_types") is not None:
                    existing_rule.allowed_residency_types = e_item["allowed_residency_types"]
                existing_rule.source_id = source_id
                existing_rule.source_record_id = source_record_id
                existing_rule.retrieved_at = now
                existing_rule.verification_status = ver_status
            else:
                new_rule = LoanEligibilityRule(
                    loan_product_id=loan_product.id,
                    rule_name=rule_name,
                    min_monthly_income=e_item.get("min_monthly_income"),
                    min_credit_score=e_item.get("min_credit_score"),
                    max_credit_score=e_item.get("max_credit_score"),
                    max_loan_amount=e_item.get("max_loan_amount"),
                    max_ltv_percent=e_item.get("max_ltv_percent"),
                    max_foir_percent=e_item.get("max_foir_percent", Decimal("50.00")),
                    min_age_years=e_item.get("min_age_years", 21),
                    max_age_years=e_item.get("max_age_years", 65),
                    min_employment_months=e_item.get("min_employment_months", 12),
                    allowed_employment_types=e_item.get("allowed_employment_types", "SALARIED,SELF_EMPLOYED"),
                    allowed_residency_types=e_item.get("allowed_residency_types", "RESIDENT_INDIAN,NRI"),
                    effective_from=eff_from_dt,
                    effective_to=None,
                    active=True,
                    source_id=source_id,
                    source_record_id=source_record_id,
                    retrieved_at=now,
                    verification_status=ver_status,
                )
                db.add(new_rule)

        # 5. Resolve & Promote Loan Fees
        fees_data = data.get("fees", [])
        for f_item in fees_data:
            fee_name = f_item.get("fee_name", "Standard Fee")
            fee_type = f_item.get("fee_type", "PROCESSING_FEE")
            existing_fee = (
                await db.execute(
                    select(LoanFee).where(
                        LoanFee.loan_product_id == loan_product.id,
                        LoanFee.fee_name == fee_name,
                        LoanFee.active.is_(True),
                    )
                )
            ).scalars().first()

            f_eff_from = f_item.get("effective_from") or data.get("effective_from")
            if isinstance(f_eff_from, str):
                eff_from_dt = datetime.fromisoformat(f_eff_from.replace("Z", "+00:00"))
            elif isinstance(f_eff_from, datetime):
                eff_from_dt = f_eff_from
            else:
                eff_from_dt = now

            if existing_fee:
                existing_fee.fee_type = fee_type
                if f_item.get("calculation_method"):
                    existing_fee.calculation_method = f_item["calculation_method"]
                if f_item.get("fixed_amount") is not None:
                    existing_fee.fixed_amount = f_item["fixed_amount"]
                if f_item.get("percentage") is not None:
                    existing_fee.percentage = f_item["percentage"]
                if f_item.get("minimum_amount") is not None:
                    existing_fee.minimum_amount = f_item["minimum_amount"]
                if f_item.get("maximum_amount") is not None:
                    existing_fee.maximum_amount = f_item["maximum_amount"]
                existing_fee.source_id = source_id
                existing_fee.source_record_id = source_record_id
                existing_fee.retrieved_at = now
                existing_fee.verification_status = ver_status
            else:
                new_fee = LoanFee(
                    loan_product_id=loan_product.id,
                    fee_name=fee_name,
                    fee_type=fee_type,
                    calculation_method=f_item.get("calculation_method", "PERCENTAGE"),
                    fixed_amount=f_item.get("fixed_amount"),
                    percentage=f_item.get("percentage"),
                    minimum_amount=f_item.get("minimum_amount"),
                    maximum_amount=f_item.get("maximum_amount"),
                    effective_from=eff_from_dt,
                    effective_to=None,
                    active=True,
                    source_id=source_id,
                    source_record_id=source_record_id,
                    retrieved_at=now,
                    verification_status=ver_status,
                )
                db.add(new_fee)

        await db.flush()
        if is_updated:
            return "UPDATED"
        if is_created:
            return "CREATED"
        return "UNCHANGED"

    @classmethod
    async def _promote_tax_to_canonical(
        cls,
        db: AsyncSession,
        data: Dict[str, Any],
        source_id: int,
        source_record_id: Optional[str] = None,
    ) -> str:
        """Promotes validated statutory motor vehicle tax rules and bracket structures into canonical tables."""
        state_code = data.get("state_code")
        state_name = data.get("state_name")
        state_id = data.get("state_id")

        now = datetime.now(timezone.utc)
        ver_status = data.get("verification_status", VerificationStatus.VERIFIED.value)

        # 1. Resolve State
        state = None
        if state_id:
            state = await db.get(State, state_id)
        elif state_code:
            state_res = await db.execute(
                select(State).where(
                    (State.code == state_code) | (State.name.ilike(state_name or state_code))
                )
            )
            state = state_res.scalars().first()

        if not state and state_code:
            country = (await db.execute(select(Country).where(Country.iso_code == "IN"))).scalars().first()
            if not country:
                country = Country(name="India", iso_code="IN", iso3_code="IND", active=True)
                db.add(country)
                await db.flush()

            state = State(
                country_id=country.id,
                name=state_name or state_code,
                code=state_code,
                region_type="STATE",
                active=True,
                source_id=source_id,
                source_record_id=source_record_id,
                retrieved_at=now,
            )
            db.add(state)
            await db.flush()

        if not state:
            return "UNCHANGED"

        # 2. Resolve City / RTO if specified
        city = None
        city_slug = data.get("city_slug")
        city_name = data.get("city_name")
        city_id = data.get("city_id")
        if city_id:
            city = await db.get(City, city_id)
        elif city_slug or city_name:
            city_res = await db.execute(
                select(City).where(
                    (City.state_id == state.id) &
                    ((City.slug == city_slug) | (City.name.ilike(city_name or "")))
                )
            )
            city = city_res.scalars().first()

        rto = None
        rto_code = data.get("rto_code")
        rto_id = data.get("rto_id")
        if rto_id:
            rto = await db.get(RtoOffice, rto_id)
        elif rto_code:
            rto_res = await db.execute(
                select(RtoOffice).where(
                    (RtoOffice.state_id == state.id) & (RtoOffice.code == rto_code)
                )
            )
            rto = rto_res.scalars().first()

        # 3. Extract Tax Rule Attributes
        rule_name = data.get("name", "Statutory Motor Vehicle Rule")
        description = data.get("description")
        rule_category = data.get("rule_category", "TAX")
        tax_type = data.get("tax_type", "ROAD_TAX")
        calc_method = data.get("calculation_method", "PERCENTAGE")
        vehicle_type = data.get("vehicle_type", "CAR")
        fuel_type = data.get("fuel_type")
        is_ev = data.get("is_ev")
        usage_type = data.get("usage_type", "PRIVATE")
        min_price = data.get("min_price")
        max_price = data.get("max_price")
        min_engine_cc = data.get("min_engine_cc")
        max_engine_cc = data.get("max_engine_cc")
        rate = data.get("rate")
        fixed_amount = data.get("fixed_amount", Decimal("0.00"))
        base_amount_type = data.get("base_amount_type", "EX_SHOWROOM")
        formula_definition = data.get("formula_definition")
        priority = data.get("priority", 100)
        rec_id = data.get("source_record_id") or source_record_id

        eff_from = data.get("effective_from")
        if isinstance(eff_from, str):
            eff_from_dt = datetime.fromisoformat(eff_from.replace("Z", "+00:00"))
        elif isinstance(eff_from, datetime):
            eff_from_dt = eff_from
        else:
            eff_from_dt = now

        eff_to = data.get("effective_to")
        eff_to_dt = None
        if isinstance(eff_to, str):
            eff_to_dt = datetime.fromisoformat(eff_to.replace("Z", "+00:00"))
        elif isinstance(eff_to, datetime):
            eff_to_dt = eff_to

        # 4. Check for existing active matching rule
        conds = [
            TaxRule.state_id == state.id,
            TaxRule.tax_type == tax_type,
            TaxRule.active.is_(True),
            TaxRule.effective_to.is_(None),
        ]
        if city:
            conds.append(TaxRule.city_id == city.id)
        else:
            conds.append(TaxRule.city_id.is_(None))

        if rto:
            conds.append(TaxRule.rto_id == rto.id)
        else:
            conds.append(TaxRule.rto_id.is_(None))

        if rec_id:
            conds.append((TaxRule.source_record_id == rec_id) | (TaxRule.name == rule_name))
        else:
            conds.append(TaxRule.name == rule_name)

        existing_rule = (await db.execute(select(TaxRule).where(and_(*conds)))).scalars().first()

        if existing_rule:
            # Check if rates or brackets changed
            is_changed = False
            if rate is not None and existing_rule.rate is not None:
                if Decimal(str(existing_rule.rate)) != Decimal(str(rate)):
                    is_changed = True
            elif (rate is None) != (existing_rule.rate is None):
                is_changed = True

            if fixed_amount is not None and existing_rule.fixed_amount is not None:
                if Decimal(str(existing_rule.fixed_amount)) != Decimal(str(fixed_amount)):
                    is_changed = True

            if is_changed:
                # Temporal effective dating: close previous rule and create new active rule
                existing_rule.effective_to = eff_from_dt
                existing_rule.active = False
                new_rule = TaxRule(
                    name=rule_name,
                    description=description,
                    state_id=state.id,
                    city_id=city.id if city else None,
                    rto_id=rto.id if rto else None,
                    rule_category=rule_category,
                    tax_type=tax_type,
                    calculation_method=calc_method,
                    vehicle_type=vehicle_type,
                    fuel_type=fuel_type,
                    is_ev=is_ev,
                    usage_type=usage_type,
                    min_price=min_price,
                    max_price=max_price,
                    min_engine_cc=min_engine_cc,
                    max_engine_cc=max_engine_cc,
                    rate=rate,
                    fixed_amount=fixed_amount,
                    base_amount_type=base_amount_type,
                    formula_definition=formula_definition,
                    priority=priority,
                    effective_from=eff_from_dt,
                    effective_to=None,
                    active=True,
                    source_id=source_id,
                    source_record_id=rec_id,
                    retrieved_at=now,
                    verification_status=ver_status,
                )
                if calc_method == "BRACKETED" and "brackets" in data:
                    for b in data["brackets"]:
                        new_rule.brackets.append(
                            TaxRuleBracket(
                                bracket_order=b.get("bracket_order", 1),
                                minimum_value=b.get("minimum_value", Decimal("0.00")),
                                maximum_value=b.get("maximum_value"),
                                rate=b.get("rate"),
                                fixed_amount=b.get("fixed_amount", Decimal("0.00")),
                                calculation_method=b.get("calculation_method", "PERCENTAGE"),
                            )
                        )
                db.add(new_rule)
                await db.flush()
                return "UPDATED"
            else:
                # Update provenance on existing rule
                existing_rule.source_id = source_id
                existing_rule.source_record_id = rec_id
                existing_rule.retrieved_at = now
                existing_rule.verification_status = ver_status
                existing_rule.priority = priority
                if description:
                    existing_rule.description = description
                await db.flush()
                return "UNCHANGED"
        else:
            # Create new rule
            new_rule = TaxRule(
                name=rule_name,
                description=description,
                state_id=state.id,
                city_id=city.id if city else None,
                rto_id=rto.id if rto else None,
                rule_category=rule_category,
                tax_type=tax_type,
                calculation_method=calc_method,
                vehicle_type=vehicle_type,
                fuel_type=fuel_type,
                is_ev=is_ev,
                usage_type=usage_type,
                min_price=min_price,
                max_price=max_price,
                min_engine_cc=min_engine_cc,
                max_engine_cc=max_engine_cc,
                rate=rate,
                fixed_amount=fixed_amount,
                base_amount_type=base_amount_type,
                formula_definition=formula_definition,
                priority=priority,
                effective_from=eff_from_dt,
                effective_to=eff_to_dt,
                active=True,
                source_id=source_id,
                source_record_id=rec_id,
                retrieved_at=now,
                verification_status=ver_status,
            )
            if calc_method == "BRACKETED" and "brackets" in data:
                for b in data["brackets"]:
                    new_rule.brackets.append(
                        TaxRuleBracket(
                            bracket_order=b.get("bracket_order", 1),
                            minimum_value=b.get("minimum_value", Decimal("0.00")),
                            maximum_value=b.get("maximum_value"),
                            rate=b.get("rate"),
                            fixed_amount=b.get("fixed_amount", Decimal("0.00")),
                            calculation_method=b.get("calculation_method", "PERCENTAGE"),
                        )
                    )
            db.add(new_rule)
            await db.flush()
            return "CREATED"

    @classmethod
    async def _promote_fuel_price_to_canonical(
        cls,
        db: AsyncSession,
        data: Dict[str, Any],
        source_id: int,
        source_record_id: Optional[str] = None,
    ) -> str:
        """Promotes fuel price observation to canonical table with location resolution and historical retention."""
        fuel_type = data["fuel_type"].upper().strip()
        price = data["price_per_unit"]
        unit = data.get("unit", "Litre")
        currency = data.get("currency", "INR")
        obs_date = data["observed_date"]
        eff_from = data.get("effective_from", obs_date)
        state_code = data.get("state_code")
        city_name = data.get("city_name")
        ver_status = data.get("verification_status", VerificationStatus.VERIFIED.value)
        source_rec_id = source_record_id or data.get("source_record_id")

        if obs_date.tzinfo is None:
            obs_date = obs_date.replace(tzinfo=timezone.utc)
        if eff_from.tzinfo is None:
            eff_from = eff_from.replace(tzinfo=timezone.utc)

        # Resolve state and city
        state_id: Optional[int] = None
        city_id: Optional[int] = None

        if state_code:
            st_res = await db.execute(select(State).where(State.code == state_code.upper()))
            st = st_res.scalars().first()
            if not st:
                c_res = await db.execute(select(Country).where(Country.name == "India"))
                c = c_res.scalars().first()
                if not c:
                    c = Country(name="India", iso_code="IN", iso3_code="IND", active=True)
                    db.add(c)
                    await db.flush()
                st = State(name=f"State {state_code.upper()}", code=state_code.upper(), country_id=c.id, active=True)
                db.add(st)
                await db.flush()
            state_id = st.id

            if city_name:
                ct_res = await db.execute(
                    select(City).where(City.name.ilike(city_name.strip()), City.state_id == state_id)
                )
                ct = ct_res.scalars().first()
                if not ct:
                    c_slug = city_name.strip().lower().replace(" ", "-")
                    ct = City(name=city_name.strip(), slug=c_slug, state_id=state_id, active=True)
                    db.add(ct)
                    await db.flush()
                city_id = ct.id

        # Check existing matching record by fuel_type, location, and observed_date
        query = select(FuelPrice).where(
            FuelPrice.fuel_type == fuel_type,
            FuelPrice.state_id == state_id,
            FuelPrice.city_id == city_id,
            FuelPrice.observed_date == obs_date,
        )
        existing_res = await db.execute(query)
        existing = existing_res.scalars().first()

        if existing:
            if existing.price_per_unit != price or existing.verification_status != ver_status:
                existing.price_per_unit = price
                existing.unit = unit
                existing.currency = currency
                existing.source_id = source_id
                existing.source_record_id = source_rec_id
                existing.verification_status = ver_status
                existing.is_active = True
                await db.flush()
                return "UPDATED"
            return "UNCHANGED"

        # Check for previous active record to close effective_to
        prev_active_res = await db.execute(
            select(FuelPrice).where(
                FuelPrice.fuel_type == fuel_type,
                FuelPrice.state_id == state_id,
                FuelPrice.city_id == city_id,
                FuelPrice.is_active == True,
            ).order_by(FuelPrice.effective_from.desc())
        )
        prev_active = prev_active_res.scalars().first()
        if prev_active and _ensure_tz_utc(prev_active.effective_from) <= _ensure_tz_utc(eff_from):
            prev_active.effective_to = eff_from
            prev_active.is_active = False

        new_record = FuelPrice(
            fuel_type=fuel_type,
            state_id=state_id,
            state_code=state_code,
            city_id=city_id,
            city_name=city_name,
            price_per_unit=price,
            unit=unit,
            currency=currency,
            observed_date=obs_date,
            effective_from=eff_from,
            effective_to=None,
            source_id=source_id,
            source_record_id=source_rec_id,
            verification_status=ver_status,
            is_active=True,
        )
        db.add(new_record)
        await db.flush()
        return "CREATED"

    @classmethod
    async def _promote_electricity_tariff_to_canonical(
        cls,
        db: AsyncSession,
        data: Dict[str, Any],
        source_id: int,
        source_record_id: Optional[str] = None,
    ) -> str:
        """Promotes electricity tariff to canonical table with state resolution and effective dating."""
        tariff_type = data.get("tariff_type", "DOMESTIC_SLAB")
        rate = data["rate_per_kwh"]
        fixed_charge = data.get("fixed_charge_per_month")
        eff_from = data.get("effective_from", datetime.now(timezone.utc))
        state_code = data.get("state_code")
        discom_name = data.get("discom_name")
        ver_status = data.get("verification_status", VerificationStatus.VERIFIED.value)

        if eff_from.tzinfo is None:
            eff_from = eff_from.replace(tzinfo=timezone.utc)

        state_id: Optional[int] = None
        if state_code:
            st_res = await db.execute(select(State).where(State.code == state_code.upper()))
            st = st_res.scalars().first()
            if st:
                state_id = st.id

        existing_res = await db.execute(
            select(ElectricityTariff).where(
                ElectricityTariff.tariff_type == tariff_type,
                ElectricityTariff.state_id == state_id,
                ElectricityTariff.discom_name == discom_name,
                ElectricityTariff.is_active == True,
            )
        )
        existing = existing_res.scalars().first()

        if existing:
            if existing.rate_per_kwh != rate or existing.fixed_charge_per_month != fixed_charge:
                existing.effective_to = eff_from
                existing.is_active = False

                new_tariff = ElectricityTariff(
                    tariff_type=tariff_type,
                    state_id=state_id,
                    state_code=state_code,
                    discom_name=discom_name,
                    rate_per_kwh=rate,
                    fixed_charge_per_month=fixed_charge,
                    effective_from=eff_from,
                    effective_to=None,
                    source_id=source_id,
                    verification_status=ver_status,
                    is_active=True,
                )
                db.add(new_tariff)
                await db.flush()
                return "UPDATED"
            else:
                existing.source_id = source_id
                existing.verification_status = ver_status
                await db.flush()
                return "UNCHANGED"

        new_tariff = ElectricityTariff(
            tariff_type=tariff_type,
            state_id=state_id,
            state_code=state_code,
            discom_name=discom_name,
            rate_per_kwh=rate,
            fixed_charge_per_month=fixed_charge,
            effective_from=eff_from,
            effective_to=None,
            source_id=source_id,
            verification_status=ver_status,
            is_active=True,
        )
        db.add(new_tariff)
        await db.flush()
        return "CREATED"

    @classmethod
    async def _promote_maintenance_to_canonical(
        cls,
        db: AsyncSession,
        data: Dict[str, Any],
        source_id: int,
        source_record_id: Optional[str] = None,
    ) -> str:
        """Promotes maintenance cost benchmark into canonical table."""
        powertrain = data["powertrain"].upper().strip()
        segment = data.get("segment")
        annual_base = data["annual_base_cost"]
        cost_km = data["cost_per_km"]
        interval_km = data.get("service_interval_km", 10000)
        interval_mo = data.get("service_interval_months", 12)
        eff_from = data.get("effective_from", datetime.now(timezone.utc))
        ver_status = data.get("verification_status", VerificationStatus.VERIFIED.value)

        if eff_from.tzinfo is None:
            eff_from = eff_from.replace(tzinfo=timezone.utc)

        existing_res = await db.execute(
            select(MaintenanceCostBenchmark).where(
                MaintenanceCostBenchmark.powertrain == powertrain,
                MaintenanceCostBenchmark.segment == segment,
                MaintenanceCostBenchmark.is_active == True,
            )
        )
        existing = existing_res.scalars().first()

        if existing:
            if existing.annual_base_cost != annual_base or existing.cost_per_km != cost_km:
                existing.effective_to = eff_from
                existing.is_active = False

                new_maint = MaintenanceCostBenchmark(
                    powertrain=powertrain,
                    segment=segment,
                    annual_base_cost=annual_base,
                    cost_per_km=cost_km,
                    service_interval_km=interval_km,
                    service_interval_months=interval_mo,
                    effective_from=eff_from,
                    effective_to=None,
                    source_id=source_id,
                    verification_status=ver_status,
                    is_active=True,
                )
                db.add(new_maint)
                await db.flush()
                return "UPDATED"
            else:
                existing.source_id = source_id
                existing.verification_status = ver_status
                await db.flush()
                return "UNCHANGED"

        new_maint = MaintenanceCostBenchmark(
            powertrain=powertrain,
            segment=segment,
            annual_base_cost=annual_base,
            cost_per_km=cost_km,
            service_interval_km=interval_km,
            service_interval_months=interval_mo,
            effective_from=eff_from,
            effective_to=None,
            source_id=source_id,
            verification_status=ver_status,
            is_active=True,
        )
        db.add(new_maint)
        await db.flush()
        return "CREATED"

    @classmethod
    async def _promote_insurance_renewal_to_canonical(
        cls,
        db: AsyncSession,
        data: Dict[str, Any],
        source_id: int,
        source_record_id: Optional[str] = None,
    ) -> str:
        """Promotes insurance renewal benchmark into canonical table."""
        fuel_type = data.get("fuel_type")
        segment = data.get("segment")
        y2 = data["year_2_factor"]
        y3 = data["year_3_factor"]
        y4 = data["year_4_factor"]
        y5 = data["year_5_factor"]
        eff_from = data.get("effective_from", datetime.now(timezone.utc))
        ver_status = data.get("verification_status", VerificationStatus.VERIFIED.value)

        if eff_from.tzinfo is None:
            eff_from = eff_from.replace(tzinfo=timezone.utc)

        existing_res = await db.execute(
            select(InsuranceRenewalBenchmark).where(
                InsuranceRenewalBenchmark.fuel_type == fuel_type,
                InsuranceRenewalBenchmark.segment == segment,
                InsuranceRenewalBenchmark.is_active == True,
            )
        )
        existing = existing_res.scalars().first()

        if existing:
            if existing.year_2_factor != y2 or existing.year_3_factor != y3 or existing.year_4_factor != y4 or existing.year_5_factor != y5:
                existing.effective_to = eff_from
                existing.is_active = False

                new_ins = InsuranceRenewalBenchmark(
                    fuel_type=fuel_type,
                    segment=segment,
                    year_2_factor=y2,
                    year_3_factor=y3,
                    year_4_factor=y4,
                    year_5_factor=y5,
                    effective_from=eff_from,
                    effective_to=None,
                    source_id=source_id,
                    verification_status=ver_status,
                    is_active=True,
                )
                db.add(new_ins)
                await db.flush()
                return "UPDATED"
            else:
                existing.source_id = source_id
                existing.verification_status = ver_status
                await db.flush()
                return "UNCHANGED"

        new_ins = InsuranceRenewalBenchmark(
            fuel_type=fuel_type,
            segment=segment,
            year_2_factor=y2,
            year_3_factor=y3,
            year_4_factor=y4,
            year_5_factor=y5,
            effective_from=eff_from,
            effective_to=None,
            source_id=source_id,
            verification_status=ver_status,
            is_active=True,
        )
        db.add(new_ins)
        await db.flush()
        return "CREATED"

    @classmethod
    async def _promote_depreciation_to_canonical(
        cls,
        db: AsyncSession,
        data: Dict[str, Any],
        source_id: int,
        source_record_id: Optional[str] = None,
    ) -> str:
        """Promotes depreciation schedule benchmark into canonical table."""
        powertrain = data.get("powertrain")
        segment = data.get("segment")
        y1 = data["year_1_depreciation_pct"]
        y2 = data["year_2_depreciation_pct"]
        y3 = data["year_3_depreciation_pct"]
        y4 = data["year_4_depreciation_pct"]
        y5 = data["year_5_depreciation_pct"]
        methodology = data.get("methodology", "EMPIRICAL_MARKET_RESALE")
        eff_from = data.get("effective_from", datetime.now(timezone.utc))
        ver_status = data.get("verification_status", VerificationStatus.VERIFIED.value)

        if eff_from.tzinfo is None:
            eff_from = eff_from.replace(tzinfo=timezone.utc)

        existing_res = await db.execute(
            select(DepreciationBenchmark).where(
                DepreciationBenchmark.powertrain == powertrain,
                DepreciationBenchmark.segment == segment,
                DepreciationBenchmark.is_active == True,
            )
        )
        existing = existing_res.scalars().first()

        if existing:
            if (
                existing.year_1_depreciation_pct != y1
                or existing.year_2_depreciation_pct != y2
                or existing.year_3_depreciation_pct != y3
                or existing.year_4_depreciation_pct != y4
                or existing.year_5_depreciation_pct != y5
            ):
                existing.effective_to = eff_from
                existing.is_active = False

                new_dep = DepreciationBenchmark(
                    powertrain=powertrain,
                    segment=segment,
                    year_1_depreciation_pct=y1,
                    year_2_depreciation_pct=y2,
                    year_3_depreciation_pct=y3,
                    year_4_depreciation_pct=y4,
                    year_5_depreciation_pct=y5,
                    methodology=methodology,
                    effective_from=eff_from,
                    effective_to=None,
                    source_id=source_id,
                    verification_status=ver_status,
                    is_active=True,
                )
                db.add(new_dep)
                await db.flush()
                return "UPDATED"
            else:
                existing.source_id = source_id
                existing.verification_status = ver_status
                await db.flush()
                return "UNCHANGED"

        new_dep = DepreciationBenchmark(
            powertrain=powertrain,
            segment=segment,
            year_1_depreciation_pct=y1,
            year_2_depreciation_pct=y2,
            year_3_depreciation_pct=y3,
            year_4_depreciation_pct=y4,
            year_5_depreciation_pct=y5,
            methodology=methodology,
            effective_from=eff_from,
            effective_to=None,
            source_id=source_id,
            verification_status=ver_status,
            is_active=True,
        )
        db.add(new_dep)
        await db.flush()
        return "CREATED"

    @classmethod
    async def _check_conflicts(
        cls,
        db: AsyncSession,
        dataset_name: str,
        entity_type: str,
        entity_identifier: str,
        current_source_id: int,
        normalized_payload: Dict[str, Any],
    ) -> None:
        """Identifies discrepancies between the current payload and other active data source values."""
        # 1. Price discrepancies
        price_val = normalized_payload.get("ex_showroom_price")
        if price_val:
            res = await db.execute(
                select(RawIngestionRecord, IngestionRun.data_source_id)
                .join(IngestionRun, RawIngestionRecord.ingestion_run_id == IngestionRun.id)
                .where(
                    RawIngestionRecord.entity_type == entity_type,
                    IngestionRun.data_source_id != current_source_id,
                )
                .limit(10)
            )
            other_records = res.all()

            for rec, other_source_id in other_records:
                other_payload = rec.raw_payload
                other_ident = f"{other_payload.get('manufacturer', '')} {other_payload.get('model', '')} {other_payload.get('variant', '')}".strip()
                if other_ident.lower() == entity_identifier.lower():
                    other_price = other_payload.get("price")
                    if other_price and Decimal(str(other_price)) != Decimal(str(price_val)):
                        existing_conflict = (
                            await db.execute(
                                select(DataConflictRecord).where(
                                    DataConflictRecord.entity_identifier == entity_identifier,
                                    DataConflictRecord.field_name == "ex_showroom_price",
                                    DataConflictRecord.status == ConflictStatus.UNRESOLVED.value,
                                )
                            )
                        ).scalars().first()

                        if not existing_conflict:
                            conflict = DataConflictRecord(
                                dataset_name=dataset_name,
                                entity_type=entity_type,
                                entity_identifier=entity_identifier,
                                field_name="ex_showroom_price",
                                source_a_id=current_source_id,
                                source_a_value={"price": str(price_val)},
                                source_b_id=other_source_id,
                                source_b_value={"price": str(other_price)},
                                detected_at=datetime.now(timezone.utc),
                                status=ConflictStatus.UNRESOLVED.value,
                            )
                            db.add(conflict)
                            await db.flush()

        # 2. Location RTO/City discrepancies
        rto_code = normalized_payload.get("rto_code")
        if rto_code and entity_type == IngestionEntityType.LOCATION.value:
            res = await db.execute(
                select(RawIngestionRecord, IngestionRun.data_source_id)
                .join(IngestionRun, RawIngestionRecord.ingestion_run_id == IngestionRun.id)
                .where(
                    RawIngestionRecord.entity_type == entity_type,
                    IngestionRun.data_source_id != current_source_id,
                )
                .limit(10)
            )
            other_records = res.all()
            for rec, other_source_id in other_records:
                other_payload = rec.raw_payload
                other_rto = other_payload.get("rto_code") or other_payload.get("code")
                if other_rto and str(other_rto).strip().upper() == str(rto_code).strip().upper():
                    other_jurisdiction = other_payload.get("jurisdiction")
                    current_jurisdiction = normalized_payload.get("jurisdiction")
                    if current_jurisdiction and other_jurisdiction and current_jurisdiction != other_jurisdiction:
                        existing_conflict = (
                            await db.execute(
                                select(DataConflictRecord).where(
                                    DataConflictRecord.entity_identifier == entity_identifier,
                                    DataConflictRecord.field_name == "jurisdiction",
                                    DataConflictRecord.status == ConflictStatus.UNRESOLVED.value,
                                )
                            )
                        ).scalars().first()
                        if not existing_conflict:
                            conflict = DataConflictRecord(
                                dataset_name=dataset_name,
                                entity_type=entity_type,
                                entity_identifier=entity_identifier,
                                field_name="jurisdiction",
                                source_a_id=current_source_id,
                                source_a_value={"jurisdiction": current_jurisdiction},
                                source_b_id=other_source_id,
                                source_b_value={"jurisdiction": other_jurisdiction},
                                detected_at=datetime.now(timezone.utc),
                                status=ConflictStatus.UNRESOLVED.value,
                            )
                            db.add(conflict)
                            await db.flush()

        # 3. Interest rate discrepancies
        if entity_type == IngestionEntityType.FINANCE.value:
            rates_list = normalized_payload.get("rates", [])
            for r_entry in rates_list:
                r_rate = r_entry.get("annual_interest_rate")
                if r_rate:
                    res = await db.execute(
                        select(RawIngestionRecord, IngestionRun.data_source_id)
                        .join(IngestionRun, RawIngestionRecord.ingestion_run_id == IngestionRun.id)
                        .where(
                            RawIngestionRecord.entity_type == entity_type,
                            IngestionRun.data_source_id != current_source_id,
                        )
                        .limit(10)
                    )
                    other_records = res.all()
                    for rec, other_source_id in other_records:
                        other_payload = rec.raw_payload
                        other_bank = other_payload.get("bank_name", "")
                        other_product = other_payload.get("product_name", "")
                        other_ident = f"{other_bank} {other_product}".strip()
                        if other_ident.lower() == entity_identifier.lower():
                            for other_r in other_payload.get("rates", []):
                                if (
                                    other_r.get("min_credit_score") == r_entry.get("min_credit_score")
                                    and other_r.get("rate_type", "FLOATING") == r_entry.get("rate_type", "FLOATING")
                                ):
                                    other_rate_val = other_r.get("annual_interest_rate")
                                    if other_rate_val and Decimal(str(other_rate_val)) != Decimal(str(r_rate)):
                                        existing_conflict = (
                                            await db.execute(
                                                select(DataConflictRecord).where(
                                                    DataConflictRecord.entity_identifier == entity_identifier,
                                                    DataConflictRecord.field_name == "annual_interest_rate",
                                                    DataConflictRecord.status == ConflictStatus.UNRESOLVED.value,
                                                )
                                            )
                                        ).scalars().first()
                                        if not existing_conflict:
                                            conflict = DataConflictRecord(
                                                dataset_name=dataset_name,
                                                entity_type=entity_type,
                                                entity_identifier=entity_identifier,
                                                field_name="annual_interest_rate",
                                                source_a_id=current_source_id,
                                                source_a_value={"rate": str(r_rate)},
                                                source_b_id=other_source_id,
                                                source_b_value={"rate": str(other_rate_val)},
                                                detected_at=datetime.now(timezone.utc),
                                                status=ConflictStatus.UNRESOLVED.value,
                                            )
                                            db.add(conflict)
                                            await db.flush()

        # 4. Tax rule rate and fixed amount discrepancies
        if entity_type == IngestionEntityType.TAX_RULE.value:
            tax_type = normalized_payload.get("tax_type")
            state_code = normalized_payload.get("state_code")
            rule_rate = normalized_payload.get("rate")
            rule_fixed = normalized_payload.get("fixed_amount")
            rule_name = normalized_payload.get("name")
            if tax_type and state_code:
                res = await db.execute(
                    select(RawIngestionRecord, IngestionRun.data_source_id)
                    .join(IngestionRun, RawIngestionRecord.ingestion_run_id == IngestionRun.id)
                    .where(
                        RawIngestionRecord.entity_type == entity_type,
                        IngestionRun.data_source_id != current_source_id,
                    )
                    .limit(10)
                )
                other_records = res.all()
                for rec, other_source_id in other_records:
                    other_payload = rec.raw_payload
                    if (
                        other_payload.get("state_code") == state_code
                        and other_payload.get("tax_type") == tax_type
                        and other_payload.get("name") == rule_name
                    ):
                        other_rate = other_payload.get("rate")
                        if other_rate is not None and rule_rate is not None:
                            if Decimal(str(other_rate)) != Decimal(str(rule_rate)):
                                existing_conflict = (
                                    await db.execute(
                                        select(DataConflictRecord).where(
                                            DataConflictRecord.entity_identifier == entity_identifier,
                                            DataConflictRecord.field_name == "rate",
                                            DataConflictRecord.status == ConflictStatus.UNRESOLVED.value,
                                        )
                                    )
                                ).scalars().first()
                                if not existing_conflict:
                                    conflict = DataConflictRecord(
                                        dataset_name=dataset_name,
                                        entity_type=entity_type,
                                        entity_identifier=entity_identifier,
                                        field_name="rate",
                                        source_a_id=current_source_id,
                                        source_a_value={"rate": str(rule_rate)},
                                        source_b_id=other_source_id,
                                        source_b_value={"rate": str(other_rate)},
                                        detected_at=datetime.now(timezone.utc),
                                        status=ConflictStatus.UNRESOLVED.value,
                                    )
                                    db.add(conflict)
                                    await db.flush()

                        other_fixed = other_payload.get("fixed_amount")
                        if other_fixed is not None and rule_fixed is not None:
                            if Decimal(str(other_fixed)) != Decimal(str(rule_fixed)):
                                existing_conflict = (
                                    await db.execute(
                                        select(DataConflictRecord).where(
                                            DataConflictRecord.entity_identifier == entity_identifier,
                                            DataConflictRecord.field_name == "fixed_amount",
                                            DataConflictRecord.status == ConflictStatus.UNRESOLVED.value,
                                        )
                                    )
                                ).scalars().first()
                                if not existing_conflict:
                                    conflict = DataConflictRecord(
                                        dataset_name=dataset_name,
                                        entity_type=entity_type,
                                        entity_identifier=entity_identifier,
                                        field_name="fixed_amount",
                                        source_a_id=current_source_id,
                                        source_a_value={"fixed_amount": str(rule_fixed)},
                                        source_b_id=other_source_id,
                                        source_b_value={"fixed_amount": str(other_fixed)},
                                        detected_at=datetime.now(timezone.utc),
                                        status=ConflictStatus.UNRESOLVED.value,
                                    )
                                    db.add(conflict)
                                    await db.flush()

        # 5. Fuel price discrepancies across sources
        if entity_type == IngestionEntityType.FUEL_PRICE.value:
            fuel_type = normalized_payload.get("fuel_type")
            cur_price = normalized_payload.get("price_per_unit")
            state_code = normalized_payload.get("state_code")
            city_name = normalized_payload.get("city_name")
            if fuel_type and cur_price is not None:
                res = await db.execute(
                    select(RawIngestionRecord, IngestionRun.data_source_id)
                    .join(IngestionRun, RawIngestionRecord.ingestion_run_id == IngestionRun.id)
                    .where(
                        RawIngestionRecord.entity_type == entity_type,
                        IngestionRun.data_source_id != current_source_id,
                    )
                    .limit(10)
                )
                other_records = res.all()
                for rec, other_source_id in other_records:
                    other_payload = rec.raw_payload
                    if (
                        other_payload.get("fuel_type") == fuel_type
                        and other_payload.get("state_code") == state_code
                        and other_payload.get("city_name") == city_name
                    ):
                        other_price = other_payload.get("price_per_unit")
                        if other_price is not None and Decimal(str(other_price)) != Decimal(str(cur_price)):
                            existing_conflict = (
                                await db.execute(
                                    select(DataConflictRecord).where(
                                        DataConflictRecord.entity_identifier == entity_identifier,
                                        DataConflictRecord.field_name == "price_per_unit",
                                        DataConflictRecord.status == ConflictStatus.UNRESOLVED.value,
                                    )
                                )
                            ).scalars().first()
                            if not existing_conflict:
                                conflict = DataConflictRecord(
                                    dataset_name=dataset_name,
                                    entity_type=entity_type,
                                    entity_identifier=entity_identifier,
                                    field_name="price_per_unit",
                                    source_a_id=current_source_id,
                                    source_a_value={"price_per_unit": str(cur_price)},
                                    source_b_id=other_source_id,
                                    source_b_value={"price_per_unit": str(other_price)},
                                    detected_at=datetime.now(timezone.utc),
                                    status=ConflictStatus.UNRESOLVED.value,
                                )
                                db.add(conflict)
                                await db.flush()

        # 6. Electricity tariff rate discrepancies across sources
        if entity_type == IngestionEntityType.ELECTRICITY_TARIFF.value:
            tariff_type = normalized_payload.get("tariff_type")
            cur_rate = normalized_payload.get("rate_per_kwh")
            state_code = normalized_payload.get("state_code")
            discom = normalized_payload.get("discom_name")
            if tariff_type and cur_rate is not None:
                res = await db.execute(
                    select(RawIngestionRecord, IngestionRun.data_source_id)
                    .join(IngestionRun, RawIngestionRecord.ingestion_run_id == IngestionRun.id)
                    .where(
                        RawIngestionRecord.entity_type == entity_type,
                        IngestionRun.data_source_id != current_source_id,
                    )
                    .limit(10)
                )
                other_records = res.all()
                for rec, other_source_id in other_records:
                    other_payload = rec.raw_payload
                    if (
                        other_payload.get("tariff_type") == tariff_type
                        and other_payload.get("state_code") == state_code
                        and other_payload.get("discom_name") == discom
                    ):
                        other_rate = other_payload.get("rate_per_kwh")
                        if other_rate is not None and Decimal(str(other_rate)) != Decimal(str(cur_rate)):
                            existing_conflict = (
                                await db.execute(
                                    select(DataConflictRecord).where(
                                        DataConflictRecord.entity_identifier == entity_identifier,
                                        DataConflictRecord.field_name == "rate_per_kwh",
                                        DataConflictRecord.status == ConflictStatus.UNRESOLVED.value,
                                    )
                                )
                            ).scalars().first()
                            if not existing_conflict:
                                conflict = DataConflictRecord(
                                    dataset_name=dataset_name,
                                    entity_type=entity_type,
                                    entity_identifier=entity_identifier,
                                    field_name="rate_per_kwh",
                                    source_a_id=current_source_id,
                                    source_a_value={"rate_per_kwh": str(cur_rate)},
                                    source_b_id=other_source_id,
                                    source_b_value={"rate_per_kwh": str(other_rate)},
                                    detected_at=datetime.now(timezone.utc),
                                    status=ConflictStatus.UNRESOLVED.value,
                                )
                                db.add(conflict)
                                await db.flush()

    @classmethod
    async def get_freshness_report(cls, db: AsyncSession) -> List[FreshnessReportItem]:
        """Calculates freshness status for each registered dataset based on SLA rules."""
        items: List[FreshnessReportItem] = []
        now = datetime.now(timezone.utc)

        for dataset_name, sla_days in DATASET_FRESHNESS_SLA_DAYS.items():
            # Find latest completed ingestion run for this dataset
            res = await db.execute(
                select(func.max(IngestionRun.completed_at)).where(
                    IngestionRun.dataset_name.ilike(f"%{dataset_name[:4]}%"),
                    IngestionRun.status == IngestionRunStatus.COMPLETED.value,
                )
            )
            last_synced = res.scalar()

            if not last_synced:
                items.append(
                    FreshnessReportItem(
                        dataset_name=dataset_name,
                        sla_days=sla_days,
                        last_synced_at=None,
                        age_days=None,
                        status=DataFreshnessStatus.UNKNOWN,
                    )
                )
            else:
                if last_synced.tzinfo is None:
                    last_synced = last_synced.replace(tzinfo=timezone.utc)
                age_days = (now - last_synced).days
                if age_days <= sla_days:
                    status = DataFreshnessStatus.CURRENT
                elif age_days <= (sla_days * 2):
                    status = DataFreshnessStatus.STALE
                else:
                    status = DataFreshnessStatus.EXPIRED

                items.append(
                    FreshnessReportItem(
                        dataset_name=dataset_name,
                        sla_days=sla_days,
                        last_synced_at=last_synced,
                        age_days=age_days,
                        status=status,
                    )
                )

        return items

    @classmethod
    async def get_data_quality_overview(cls, db: AsyncSession) -> DataQualityOverviewResponse:
        """Computes transparent composite quality score and operational summary."""
        # 1. Total & Active sources
        sources_res = await db.execute(select(DataSource))
        sources = sources_res.scalars().all()
        total_sources = len(sources)
        active_sources = sum(1 for s in sources if s.is_active)

        # Source trust average (0 to 100)
        avg_trust = (
            Decimal(str(sum(s.trust_level for s in sources) / total_sources))
            if total_sources > 0
            else Decimal("70.00")
        )

        # 2. Ingestion runs count
        total_runs = (await db.execute(select(func.count(IngestionRun.id)))).scalar() or 0

        # 3. Conflicts count
        unresolved_conflicts = (
            await db.execute(
                select(func.count(DataConflictRecord.id)).where(
                    DataConflictRecord.status == ConflictStatus.UNRESOLVED.value
                )
            )
        ).scalar() or 0

        # 4. Review items count
        pending_reviews = (
            await db.execute(
                select(func.count(DataQualityReviewItem.id)).where(
                    DataQualityReviewItem.status == VerificationStatus.PENDING_REVIEW.value
                )
            )
        ).scalar() or 0

        # 5. Freshness report & score
        freshness_items = await cls.get_freshness_report(db)
        current_count = sum(1 for f in freshness_items if f.status == DataFreshnessStatus.CURRENT)
        freshness_score = (
            Decimal(str((current_count / len(freshness_items)) * 100.0))
            if freshness_items
            else Decimal("80.00")
        )

        # 6. Validation pass rate
        total_raw = (await db.execute(select(func.count(RawIngestionRecord.id)))).scalar() or 0
        valid_raw = (
            await db.execute(
                select(func.count(RawIngestionRecord.id)).where(
                    RawIngestionRecord.validation_status == "VALID"
                )
            )
        ).scalar() or 0
        validation_score = (
            Decimal(str((valid_raw / total_raw) * 100.0))
            if total_raw > 0
            else Decimal("95.00")
        )

        completeness_score = Decimal("92.00")

        # Composite score
        overall_score = (
            (avg_trust * DATA_QUALITY_WEIGHTS["source_trust"])
            + (freshness_score * DATA_QUALITY_WEIGHTS["freshness"])
            + (completeness_score * DATA_QUALITY_WEIGHTS["completeness"])
            + (validation_score * DATA_QUALITY_WEIGHTS["validation"])
        ).quantize(Decimal("0.1"))

        breakdown = DataQualityScoreBreakdown(
            overall_quality_score=overall_score,
            source_trust_score=avg_trust.quantize(Decimal("0.1")),
            freshness_score=freshness_score.quantize(Decimal("0.1")),
            completeness_score=completeness_score.quantize(Decimal("0.1")),
            validation_score=validation_score.quantize(Decimal("0.1")),
            weights=DATA_QUALITY_WEIGHTS,
        )

        return DataQualityOverviewResponse(
            overall_quality_score=overall_score,
            breakdown=breakdown,
            total_sources=total_sources,
            active_sources=active_sources,
            total_ingestion_runs=total_runs,
            unresolved_conflicts_count=unresolved_conflicts,
            pending_review_items_count=pending_reviews,
            freshness_report=freshness_items,
            data_status="DEMO",
            disclaimer=INGESTION_DISCLAIMER,
        )
