from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin
from app.core.ingestion_constants import (
    ConflictStatus,
    DATASET_FRESHNESS_SLA_DAYS,
    DataFreshnessStatus,
    DataSourceType,
    IngestionRunStatus,
    VerificationStatus,
)
from app.models.data_source import DataSource
from app.models.ingestion import (
    DataConflictRecord,
    DataQualityReviewItem,
    IngestionRun,
    RawIngestionRecord,
)
from app.models.user import User
from app.schemas.admin import (
    AdminDataSourceItem,
    AdminFreshnessResponse,
    AdminIngestionRunDetail,
    AdminOverviewResponse,
    AdminQualityResponse,
    FreshnessDomainGroup,
    QualityScorePillar,
)
from app.schemas.common import BaseResponse
from app.schemas.ingestion import (
    DataConflictRead,
    DataConflictResolutionRequest,
    DataQualityOverviewResponse,
    DataQualityReviewAction,
    DataQualityReviewItemRead,
    FreshnessReportItem,
    IngestionRunRead,
)
from app.services.audit_service import AuditService
from app.services.data_quality_service import DataQualityService
from app.services.ingestion_service import IngestionService

router = APIRouter(dependencies=[Depends(require_admin)])



# =============================================================================
# 1. ADMIN OVERVIEW & HEALTH METRICS
# =============================================================================

@router.get(
    "/overview",
    response_model=BaseResponse[AdminOverviewResponse],
    summary="Get Aggregated Admin Governance Overview",
)
async def get_admin_overview(db: AsyncSession = Depends(get_db)):
    """Computes high-level data governance, active sources, failure counts, conflicts, and quality metrics."""
    # Data source counts
    ds_res = await db.execute(select(DataSource))
    data_sources = list(ds_res.scalars().all())
    total_sources = len(data_sources)
    active_sources = sum(1 for ds in data_sources if ds.is_active)
    live_sources = sum(
        1 for ds in data_sources if ds.source_type == DataSourceType.OFFICIAL_GOVERNMENT.value or ds.provider_type in ["direct", "live"]
    )
    fixture_sources = sum(
        1 for ds in data_sources if ds.source_type in [DataSourceType.DEMO_SEED.value, DataSourceType.FIXTURE_ONLY.value]
    )
    manual_sources = sum(
        1 for ds in data_sources if ds.source_type == DataSourceType.MANUAL_REVIEW.value
    )

    # Ingestion run counts
    runs_total = (await db.execute(select(func.count(IngestionRun.id)))).scalar() or 0
    runs_active = (
        await db.execute(
            select(func.count(IngestionRun.id)).where(IngestionRun.status == IngestionRunStatus.RUNNING.value)
        )
    ).scalar() or 0
    runs_failed = (
        await db.execute(
            select(func.count(IngestionRun.id)).where(IngestionRun.status == IngestionRunStatus.FAILED.value)
        )
    ).scalar() or 0

    # Review queue and conflicts
    pending_reviews = (
        await db.execute(
            select(func.count(DataQualityReviewItem.id)).where(
                DataQualityReviewItem.status == VerificationStatus.PENDING_REVIEW.value
            )
        )
    ).scalar() or 0

    unresolved_conflicts = (
        await db.execute(
            select(func.count(DataConflictRecord.id)).where(
                DataConflictRecord.status == ConflictStatus.UNRESOLVED.value
            )
        )
    ).scalar() or 0

    # Freshness & Quality Overview
    quality_overview = await IngestionService.get_data_quality_overview(db)

    stale_count = sum(1 for f in quality_overview.freshness_report if (getattr(f.status, "value", f.status) == DataFreshnessStatus.STALE.value))
    expired_count = sum(1 for f in quality_overview.freshness_report if (getattr(f.status, "value", f.status) == DataFreshnessStatus.EXPIRED.value))

    q_score = quality_overview.overall_quality_score
    if q_score >= Decimal("80.00"):
        q_rating = "EXCELLENT"
    elif q_score >= Decimal("60.00"):
        q_rating = "GOOD"
    elif q_score >= Decimal("40.00"):
        q_rating = "FAIR"
    else:
        q_rating = "POOR"

    res = AdminOverviewResponse(
        total_data_sources=total_sources,
        active_sources=active_sources,
        live_sources=live_sources,
        fixture_only_sources=fixture_sources,
        manual_review_sources=manual_sources,
        total_ingestion_runs=runs_total,
        active_ingestion_runs=runs_active,
        failed_ingestion_runs=runs_failed,
        stale_datasets=stale_count,
        expired_datasets=expired_count,
        unresolved_conflicts=unresolved_conflicts,
        pending_review_items=pending_reviews,
        overall_quality_score=q_score,
        quality_rating=q_rating,
        datasets_freshness_summary=quality_overview.freshness_report,
    )
    return BaseResponse(data=res)


# =============================================================================
# 2. DATA SOURCE MANAGEMENT
# =============================================================================

@router.get(
    "/data-sources",
    response_model=BaseResponse[List[AdminDataSourceItem]],
    summary="List Data Sources with Operational & Freshness Status",
)
async def list_admin_data_sources(db: AsyncSession = Depends(get_db)):
    """Returns all registered data sources enriched with SLA, access mode, and freshness calculations."""
    ds_res = await db.execute(select(DataSource).order_by(DataSource.name))
    sources = list(ds_res.scalars().all())

    now = datetime.now(timezone.utc)
    items: List[AdminDataSourceItem] = []

    for ds in sources:
        # Determine SLA days
        sla_days = DATASET_FRESHNESS_SLA_DAYS.get(ds.slug, 30)

        # Determine access mode
        if ds.source_type == DataSourceType.OFFICIAL_GOVERNMENT.value:
            access_mode = "LIVE"
        elif ds.source_type == DataSourceType.MANUAL_REVIEW.value:
            access_mode = "MANUAL_REVIEW"
        else:
            access_mode = "FIXTURE_ONLY"

        # Calculate freshness
        age_days: Optional[int] = None
        freshness_status = DataFreshnessStatus.UNKNOWN.value

        if ds.last_synced_at:
            ret_dt = ds.last_synced_at
            if ret_dt.tzinfo is None:
                ret_dt = ret_dt.replace(tzinfo=timezone.utc)
            delta = now - ret_dt
            age_days = max(0, delta.days)

            if age_days <= sla_days:
                freshness_status = DataFreshnessStatus.CURRENT.value
            elif age_days <= (sla_days * 2):
                freshness_status = DataFreshnessStatus.STALE.value
            else:
                freshness_status = DataFreshnessStatus.EXPIRED.value

        quality_score = Decimal(str(ds.trust_level * 10))

        items.append(
            AdminDataSourceItem(
                id=ds.id,
                name=ds.name,
                slug=ds.slug,
                organization=ds.organization,
                source_type=ds.source_type,
                provider_type=ds.provider_type or "aggregator",
                access_mode=access_mode,
                base_url=ds.base_url,
                terms_url=ds.terms_url,
                trust_level=ds.trust_level,
                freshness_sla_days=sla_days,
                last_retrieved_at=ds.last_synced_at,
                freshness_status=freshness_status,
                age_days=age_days,
                is_active=ds.is_active,
                quality_score=quality_score,
                created_at=ds.created_at,
                updated_at=ds.updated_at,
            )
        )

    return BaseResponse(data=items)


@router.post(
    "/data-sources/{id}/toggle",
    response_model=BaseResponse[AdminDataSourceItem],
    summary="Toggle Data Source Active Status",
)
async def toggle_data_source_active(id: int, db: AsyncSession = Depends(get_db)):
    """Enables or disables a data source without deleting any historical provenance."""
    ds_res = await db.execute(select(DataSource).where(DataSource.id == id))
    ds = ds_res.scalars().first()
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source with ID {id} not found",
        )

    ds.is_active = not ds.is_active
    await db.flush()

    # Build response item
    sla_days = DATASET_FRESHNESS_SLA_DAYS.get(ds.slug, 30)
    access_mode = (
        "LIVE"
        if ds.source_type == DataSourceType.OFFICIAL_GOVERNMENT.value
        else ("MANUAL_REVIEW" if ds.source_type == DataSourceType.MANUAL_REVIEW.value else "FIXTURE_ONLY")
    )

    item = AdminDataSourceItem(
        id=ds.id,
        name=ds.name,
        slug=ds.slug,
        organization=ds.organization,
        source_type=ds.source_type,
        provider_type=ds.provider_type or "aggregator",
        access_mode=access_mode,
        base_url=ds.base_url,
        terms_url=ds.terms_url,
        trust_level=ds.trust_level,
        freshness_sla_days=sla_days,
        last_retrieved_at=ds.last_synced_at,
        freshness_status=DataFreshnessStatus.CURRENT.value if ds.last_synced_at else DataFreshnessStatus.UNKNOWN.value,
        age_days=0 if ds.last_synced_at else None,
        is_active=ds.is_active,
        quality_score=Decimal(str(ds.trust_level * 10)),
        created_at=ds.created_at,
        updated_at=ds.updated_at,
    )
    return BaseResponse(data=item)


# =============================================================================
# 3. INGESTION RUNS & AUDIT LOGS
# =============================================================================

@router.get(
    "/ingestion-runs",
    response_model=BaseResponse[List[IngestionRunRead]],
    summary="List Ingestion Runs with Status and Counts",
)
async def list_admin_ingestion_runs(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (e.g. COMPLETED, FAILED)"),
    dataset: Optional[str] = Query(None, description="Filter by dataset name"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Returns paginated history of ingestion runs with record counts and execution metadata."""
    query = select(IngestionRun).order_by(desc(IngestionRun.started_at))
    if status_filter:
        query = query.where(IngestionRun.status == status_filter.upper())
    if dataset:
        query = query.where(IngestionRun.dataset_name.ilike(f"%{dataset}%"))

    query = query.limit(limit).offset(offset)
    res = await db.execute(query)
    runs = list(res.scalars().all())
    return BaseResponse(data=runs)


@router.get(
    "/ingestion-runs/{id}",
    response_model=BaseResponse[AdminIngestionRunDetail],
    summary="Get Ingestion Run Audit Detail",
)
async def get_admin_ingestion_run_detail(id: int, db: AsyncSession = Depends(get_db)):
    """Returns detailed staging metrics, raw record samples, validation breakdown, and conflict logs."""
    run_res = await db.execute(select(IngestionRun).where(IngestionRun.id == id))
    run = run_res.scalars().first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion run with ID {id} not found",
        )

    # Raw staging samples
    raw_res = await db.execute(
        select(RawIngestionRecord).where(RawIngestionRecord.ingestion_run_id == id).limit(5)
    )
    raw_records = list(raw_res.scalars().all())
    raw_count = (
        await db.execute(
            select(func.count(RawIngestionRecord.id)).where(RawIngestionRecord.ingestion_run_id == id)
        )
    ).scalar() or 0

    raw_samples = [r.raw_payload for r in raw_records if isinstance(r.raw_payload, dict)]

    # Validation summary
    val_summary = {
        "records_seen": run.records_seen,
        "records_created": run.records_created,
        "records_updated": run.records_updated,
        "records_rejected": run.records_rejected,
        "records_unchanged": run.records_unchanged,
        "validation_errors": run.validation_error_count,
        "execution_errors": run.error_count,
    }

    # Conflicts detected during or related to run
    conf_res = await db.execute(
        select(DataConflictRecord).where(DataConflictRecord.dataset_name == run.dataset_name).limit(10)
    )
    conflicts = list(conf_res.scalars().all())

    # Quality review items
    review_res = await db.execute(
        select(DataQualityReviewItem).where(DataQualityReviewItem.raw_record_id.is_not(None)).limit(10)
    )
    reviews = list(review_res.scalars().all())

    detail = AdminIngestionRunDetail(
        run=run,
        raw_records_count=raw_count,
        raw_samples=raw_samples,
        validation_summary=val_summary,
        conflicts_detected=conflicts,
        quality_reviews=reviews,
    )
    return BaseResponse(data=detail)


# =============================================================================
# 4. REVIEW QUEUE
# =============================================================================

@router.get(
    "/review-queue",
    response_model=BaseResponse[List[DataQualityReviewItemRead]],
    summary="Get Data Quality Review Queue Items",
)
async def list_admin_review_queue(
    status_filter: Optional[str] = Query(None, alias="status", description="Status filter (PENDING_REVIEW, VERIFIED, REJECTED)"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Lists items flagged for manual review or validation."""
    items = await DataQualityService.get_review_queue(db, status=status_filter, limit=limit)
    return BaseResponse(data=items)


@router.post(
    "/review-queue/{id}/approve",
    response_model=BaseResponse[DataQualityReviewItemRead],
    summary="Approve Review Queue Item",
)
async def approve_admin_review_item(
    id: int,
    action: DataQualityReviewAction,
    db: AsyncSession = Depends(get_db),
):
    """Approves a review item, promoting its verification status to VERIFIED."""
    item = await DataQualityService.approve_review_item(
        db=db,
        item_id=id,
        reviewer_name=action.reviewer_name or "Admin Operator",
        notes=action.reviewer_notes,
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review item with ID {id} not found",
        )
    return BaseResponse(data=item)


@router.post(
    "/review-queue/{id}/reject",
    response_model=BaseResponse[DataQualityReviewItemRead],
    summary="Reject Review Queue Item",
)
async def reject_admin_review_item(
    id: int,
    action: DataQualityReviewAction,
    db: AsyncSession = Depends(get_db),
):
    """Rejects a review item with audit documentation."""
    item = await DataQualityService.reject_review_item(
        db=db,
        item_id=id,
        reviewer_name=action.reviewer_name or "Admin Operator",
        notes=action.reviewer_notes,
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review item with ID {id} not found",
        )
    return BaseResponse(data=item)


# =============================================================================
# 5. CONFLICT RESOLUTION
# =============================================================================

@router.get(
    "/conflicts",
    response_model=BaseResponse[List[DataConflictRead]],
    summary="List Cross-Source Data Conflicts",
)
async def list_admin_conflicts(
    status_filter: Optional[str] = Query(None, alias="status", description="Conflict status (DETECTED, RESOLVED, IGNORED)"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Lists value discrepancies across overlapping external sources."""
    conflicts = await DataQualityService.get_unresolved_conflicts(db, limit=limit)
    if status_filter:
        conflicts = [c for c in conflicts if c.status == status_filter.upper()]
    return BaseResponse(data=conflicts)


@router.post(
    "/conflicts/{id}/resolve",
    response_model=BaseResponse[DataConflictRead],
    summary="Resolve Data Conflict",
)
async def resolve_admin_conflict(
    id: int,
    request: DataConflictResolutionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Resolves a conflict by adopting one source's value while preserving full audit history."""
    conflict = await DataQualityService.resolve_conflict(
        db=db,
        conflict_id=id,
        accepted_source_id=request.accepted_source_id,
        notes=request.resolution_notes,
    )
    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conflict with ID {id} not found",
        )
    return BaseResponse(data=conflict)


# =============================================================================
# 6. FRESHNESS DASHBOARD
# =============================================================================

@router.get(
    "/freshness",
    response_model=BaseResponse[AdminFreshnessResponse],
    summary="Get Domain-Grouped Data Freshness Report",
)
async def get_admin_freshness_report(db: AsyncSession = Depends(get_db)):
    """Returns dataset freshness categorized across Vehicles, Pricing, Finance, Taxes, Locations, and TCO."""
    overview = await IngestionService.get_data_quality_overview(db)
    all_fresh = overview.freshness_report

    # Map datasets into functional domain groups
    domain_mapping = {
        "vehicles": ["tata_vehicles", "maruti_vehicles", "hyundai_vehicles", "vehicle_catalogues"],
        "prices": ["ex_showroom_prices", "on_road_prices", "price_reconciliation"],
        "finance": ["sbi_car_loans", "hdfc_car_loans", "icici_car_loans", "axis_car_loans", "bank_of_baroda_car_loans", "kotak_car_loans", "bank_interest_rates"],
        "taxes": ["karnataka_tax_rules", "maharashtra_tax_rules", "delhi_tax_rules", "tamilnadu_tax_rules", "telangana_tax_rules", "state_motor_vehicle_taxes"],
        "locations": ["locations_rto_directory", "states_cities_directory"],
        "tco": ["fuel_prices", "electricity_tariffs", "maintenance_costs", "insurance_data", "depreciation_data"],
    }

    domains: List[FreshnessDomainGroup] = []

    domain_titles = {
        "vehicles": "Vehicle Catalogues & Specs",
        "prices": "Ex-Showroom & Pricing Feeds",
        "finance": "Bank Financing & Interest Rates",
        "taxes": "State Motor Vehicle Taxes",
        "locations": "Government Locations & RTOs",
        "tco": "TCO Operating Benchmarks",
    }

    total_current = 0
    total_stale = 0
    total_expired = 0
    total_count = len(all_fresh)

    for d_key, dataset_slugs in domain_mapping.items():
        matched_items = [
            item for item in all_fresh
            if item.dataset_name in dataset_slugs or any(s in item.dataset_name for s in dataset_slugs)
        ]
        c_count = sum(1 for m in matched_items if getattr(m.status, "value", m.status) == DataFreshnessStatus.CURRENT.value)
        s_count = sum(1 for m in matched_items if getattr(m.status, "value", m.status) == DataFreshnessStatus.STALE.value)
        e_count = sum(1 for m in matched_items if getattr(m.status, "value", m.status) == DataFreshnessStatus.EXPIRED.value)

        total_current += c_count
        total_stale += s_count
        total_expired += e_count

        domains.append(
            FreshnessDomainGroup(
                domain_name=domain_titles.get(d_key, d_key.capitalize()),
                domain_key=d_key,
                total_datasets=len(matched_items),
                current_count=c_count,
                stale_count=s_count,
                expired_count=e_count,
                datasets=matched_items,
            )
        )

    fresh_pct = (
        Decimal(str(round((total_current / total_count) * 100, 2)))
        if total_count > 0
        else Decimal("100.00")
    )

    res = AdminFreshnessResponse(
        domains=domains,
        overall_freshness_pct=fresh_pct,
        stale_datasets_count=total_stale,
        expired_datasets_count=total_expired,
    )
    return BaseResponse(data=res)


# =============================================================================
# 7. QUALITY SCORE DASHBOARD
# =============================================================================

@router.get(
    "/quality",
    response_model=BaseResponse[AdminQualityResponse],
    summary="Get Multi-Pillar Quality Score Breakdown and Explanations",
)
async def get_admin_quality_breakdown(db: AsyncSession = Depends(get_db)):
    """Exposes the composite data quality score, 4 pillar evaluations, and change explanations."""
    overview = await IngestionService.get_data_quality_overview(db)
    breakdown = overview.breakdown

    pillars = [
        QualityScorePillar(
            pillar_name="Source Trust Level",
            pillar_key="source_trust",
            weight_pct=Decimal("35.00"),
            score=breakdown.source_trust_score,
            description="Weighted average trust score of registered official, aggregator, and benchmark sources (35% weight).",
            status="EXCELLENT" if breakdown.source_trust_score >= Decimal("80.00") else "GOOD",
        ),
        QualityScorePillar(
            pillar_name="Data Freshness SLA",
            pillar_key="freshness",
            weight_pct=Decimal("30.00"),
            score=breakdown.freshness_score,
            description="Percentage of datasets meeting observation freshness SLAs without entering stale or expired states (30% weight).",
            status="EXCELLENT" if breakdown.freshness_score >= Decimal("85.00") else ("GOOD" if breakdown.freshness_score >= Decimal("70.00") else "POOR"),
        ),
        QualityScorePillar(
            pillar_name="Data Completeness",
            pillar_key="completeness",
            weight_pct=Decimal("20.00"),
            score=breakdown.completeness_score,
            description="Coverage of mandatory specifications, ex-showroom pricing, tax slabs, and TCO benchmarks across all variants (20% weight).",
            status="EXCELLENT" if breakdown.completeness_score >= Decimal("90.00") else "GOOD",
        ),
        QualityScorePillar(
            pillar_name="Validation Accuracy",
            pillar_key="validation_accuracy",
            weight_pct=Decimal("15.00"),
            score=breakdown.validation_score,
            description="Ratio of successfully normalized and validated records versus rejected anomalies (15% weight).",
            status="EXCELLENT" if breakdown.validation_score >= Decimal("95.00") else "GOOD",
        ),
    ]

    q_score = overview.overall_quality_score
    if q_score >= Decimal("80.00"):
        q_rating = "EXCELLENT"
    elif q_score >= Decimal("60.00"):
        q_rating = "GOOD"
    elif q_score >= Decimal("40.00"):
        q_rating = "FAIR"
    else:
        q_rating = "POOR"

    explanation = (
        f"Overall Data Quality Score is {overview.overall_quality_score}/100 ({q_rating}). "
        f"Source trust remains strong at {breakdown.source_trust_score}/100. "
        f"Freshness is scored at {breakdown.freshness_score}/100 based on active SLA adherence across {len(overview.freshness_report)} datasets. "
        f"Validation accuracy is at {breakdown.validation_score}/100 with zero critical schema breaches."
    )

    recommendations = []
    if overview.unresolved_conflicts_count > 0:
        recommendations.append(f"Review and resolve {overview.unresolved_conflicts_count} cross-source value discrepancies in the Conflicts tab.")
    if overview.pending_review_items_count > 0:
        recommendations.append(f"Verify {overview.pending_review_items_count} items awaiting human review in the Review Queue.")
    if any(getattr(f.status, "value", f.status) == DataFreshnessStatus.STALE.value for f in overview.freshness_report):
        recommendations.append("Trigger ingestion runs for stale datasets to refresh prevailing tariffs and fuel prices.")
    if not recommendations:
        recommendations.append("All datasets are healthy, active, and meeting freshness SLAs.")

    res = AdminQualityResponse(
        overall_score=overview.overall_quality_score,
        rating=q_rating,
        pillars=pillars,
        score_change_explanation=explanation,
        recommendations=recommendations,
    )
    return BaseResponse(data=res)
