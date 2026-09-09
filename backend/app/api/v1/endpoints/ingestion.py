from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.ingestion.adapters.demo_adapter import DemoDataSourceAdapter
from app.ingestion.adapters.government_location_adapter import GovernmentLocationDataSourceAdapter
from app.models.ingestion import (
    DataConflictRecord,
    DataQualityReviewItem,
    IngestionRun,
)
from app.schemas.common import BaseResponse
from app.schemas.ingestion import (
    DataConflictRead,
    DataConflictResolutionRequest,
    DataQualityOverviewResponse,
    DataQualityReviewAction,
    DataQualityReviewItemRead,
    IngestionRunCreate,
    IngestionRunRead,
)
from app.services.data_quality_service import DataQualityService
from app.services.ingestion_service import IngestionService

router = APIRouter()


# =============================================================================
# INGESTION RUNS
# =============================================================================

@router.post("/runs", response_model=BaseResponse[IngestionRunRead], status_code=status.HTTP_201_CREATED, summary="Trigger Ingestion Run")
async def trigger_ingestion_run(
    request: IngestionRunCreate,
    db: AsyncSession = Depends(get_db),
):
    """Triggers an ingestion run for a supported dataset adapter (e.g. demo-seed-catalogue, locations_rto_directory)."""
    if request.dataset_name in {"locations_rto_directory", "locations", "rto_directory", "government_location"}:
        adapter = GovernmentLocationDataSourceAdapter()
    else:
        adapter = DemoDataSourceAdapter()

    run = await IngestionService.run_adapter(db=db, adapter=adapter, notes=request.notes)
    return BaseResponse(data=run)


@router.get("/runs", response_model=BaseResponse[List[IngestionRunRead]], summary="List Ingestion Runs")
async def list_ingestion_runs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Returns recent ingestion runs with counters and statuses."""
    res = await db.execute(
        select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)
    )
    runs = list(res.scalars().all())
    return BaseResponse(data=runs)


@router.get("/runs/{id}", response_model=BaseResponse[IngestionRunRead], summary="Get Ingestion Run Details")
async def get_ingestion_run(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    """Fetches full audit metrics and status of a single ingestion run."""
    res = await db.execute(select(IngestionRun).where(IngestionRun.id == id))
    run = res.scalars().first()
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ingestion run with ID {id} not found",
        )
    return BaseResponse(data=run)


# =============================================================================
# DATA QUALITY & GOVERNANCE
# =============================================================================

@router.get("/data-quality", response_model=BaseResponse[DataQualityOverviewResponse], summary="Get Data Quality Overview")
async def get_data_quality_overview(db: AsyncSession = Depends(get_db)):
    """Computes transparent data quality score, source trust average, freshness SLAs, and unresolved counts."""
    overview = await IngestionService.get_data_quality_overview(db)
    return BaseResponse(data=overview)


@router.get("/data-quality/conflicts", response_model=BaseResponse[List[DataConflictRead]], summary="List Data Conflicts")
async def list_data_conflicts(
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Lists cross-source value discrepancies requiring review or resolution."""
    conflicts = await DataQualityService.get_unresolved_conflicts(db, limit=limit)
    return BaseResponse(data=conflicts)


@router.post("/data-quality/conflicts/{conflict_id}/resolve", response_model=BaseResponse[DataConflictRead], summary="Resolve Data Conflict")
async def resolve_data_conflict(
    conflict_id: int,
    request: DataConflictResolutionRequest,
    db: AsyncSession = Depends(get_db),
):
    """Resolves a conflict by adopting one source's value."""
    conflict = await DataQualityService.resolve_conflict(
        db=db,
        conflict_id=conflict_id,
        accepted_source_id=request.accepted_source_id,
        notes=request.resolution_notes,
    )
    if not conflict:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conflict with ID {conflict_id} not found",
        )
    return BaseResponse(data=conflict)


@router.get("/data-quality/review-queue", response_model=BaseResponse[List[DataQualityReviewItemRead]], summary="Get Review Queue")
async def get_review_queue(
    status: Optional[str] = Query(None, description="Optional status filter (e.g. PENDING_REVIEW, VERIFIED, REJECTED)"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Returns items awaiting human verification before promotion to canonical status."""
    items = await DataQualityService.get_review_queue(db, status=status, limit=limit)
    return BaseResponse(data=items)


@router.post("/data-quality/{record_id}/approve", response_model=BaseResponse[DataQualityReviewItemRead], summary="Approve Review Item")
async def approve_review_item(
    record_id: int,
    action: DataQualityReviewAction,
    db: AsyncSession = Depends(get_db),
):
    """Approves a review queue item, marking its verification status as VERIFIED."""
    item = await DataQualityService.approve_review_item(
        db=db,
        item_id=record_id,
        reviewer_name=action.reviewer_name or "Admin",
        notes=action.reviewer_notes,
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review item with ID {record_id} not found",
        )
    return BaseResponse(data=item)


@router.post("/data-quality/{record_id}/reject", response_model=BaseResponse[DataQualityReviewItemRead], summary="Reject Review Item")
async def reject_review_item(
    record_id: int,
    action: DataQualityReviewAction,
    db: AsyncSession = Depends(get_db),
):
    """Rejects a review queue item, marking its verification status as REJECTED."""
    item = await DataQualityService.reject_review_item(
        db=db,
        item_id=record_id,
        reviewer_name=action.reviewer_name or "Admin",
        notes=action.reviewer_notes,
    )
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Review item with ID {record_id} not found",
        )
    return BaseResponse(data=item)
