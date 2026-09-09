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
from app.models.vehicle import Manufacturer, CarModel, Variant
from app.models.pricing import VehiclePrice
from app.models.location import State, City, RtoOffice
from app.schemas.ingestion import (
    DataQualityOverviewResponse,
    DataQualityScoreBreakdown,
    FreshnessReportItem,
    IngestionRunRead,
)


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
                promoted = await cls._promote_vehicle_to_canonical(db, mapped_data, ds.id)
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
    ) -> str:
        """Promotes validated vehicle & price data into canonical tables with effective dating."""
        mfg_name = data.get("manufacturer_name")
        model_name = data.get("model_name")
        variant_name = data.get("variant_name")

        if not mfg_name or not model_name or not variant_name:
            return "UNCHANGED"

        # 1. Resolve Manufacturer
        mfg_slug = mfg_name.lower().replace(" ", "-")
        mfg_res = await db.execute(
            select(Manufacturer).where(
                (Manufacturer.slug == mfg_slug) | (Manufacturer.name.ilike(mfg_name))
            )
        )
        mfg = mfg_res.scalars().first()
        if not mfg:
            mfg = Manufacturer(name=mfg_name, slug=mfg_slug, country="India", is_active=True)
            db.add(mfg)
            await db.flush()

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
                is_active=True,
            )
            db.add(car_model)
            await db.flush()

        # 3. Resolve Variant
        variant_slug = f"{car_model.slug}-{variant_name.lower().replace(' ', '-')}"
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
                fuel_type=data.get("fuel_type", "Petrol"),
                transmission=data.get("transmission", "Manual"),
                seating_capacity=data.get("seating_capacity", 5),
                mileage_claimed=data.get("arai_mileage_kmpl"),
                is_active=True,
            )
            db.add(variant)
            await db.flush()
            is_created = True

        # 4. Manage Effective-Dated Ex-Showroom Price
        ex_price = data.get("ex_showroom_price")
        if ex_price:
            eff_from = data.get("effective_from")
            if isinstance(eff_from, str):
                eff_from_dt = datetime.fromisoformat(eff_from.replace("Z", "+00:00"))
            elif isinstance(eff_from, datetime):
                eff_from_dt = eff_from
            else:
                eff_from_dt = datetime.now(timezone.utc)

            # Close existing active price if different
            active_price = (
                await db.execute(
                    select(VehiclePrice).where(
                        VehiclePrice.variant_id == variant.id,
                        VehiclePrice.effective_to.is_(None),
                    )
                )
            ).scalars().first()

            if active_price:
                if active_price.ex_showroom_price != ex_price:
                    # Close the previous record
                    active_price.effective_to = eff_from_dt
                    new_price = VehiclePrice(
                        variant_id=variant.id,
                        ex_showroom_price=ex_price,
                        effective_from=eff_from_dt,
                        effective_to=None,
                        source_id=source_id,
                    )
                    db.add(new_price)
                    await db.flush()
                    return "UPDATED"
                else:
                    return "CREATED" if is_created else "UNCHANGED"
            else:
                new_price = VehiclePrice(
                    variant_id=variant.id,
                    ex_showroom_price=ex_price,
                    effective_from=eff_from_dt,
                    effective_to=None,
                    source_id=source_id,
                )
                db.add(new_price)
                await db.flush()
                return "CREATED"

        return "CREATED" if is_created else "UNCHANGED"

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
        price_val = normalized_payload.get("ex_showroom_price")
        if not price_val:
            return

        # Query existing recent raw records for the same entity from DIFFERENT sources
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
                    # Check if conflict already logged
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
