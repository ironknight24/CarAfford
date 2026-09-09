from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models.data_source import DataSource
from app.schemas.common import BaseResponse
from app.schemas.ingestion import DataSourceCreate, DataSourceRead, DataSourceUpdate

router = APIRouter()


@router.get("", response_model=BaseResponse[List[DataSourceRead]], summary="List Tracked External Data Sources and Freshness")
async def list_data_sources(db: AsyncSession = Depends(get_db)):
    """Returns all registered official, licensed, manual, and demo data sources."""
    stmt = select(DataSource).order_by(DataSource.name)
    result = await db.execute(stmt)
    sources = list(result.scalars().all())
    return BaseResponse(data=sources)


@router.get("/{id}", response_model=BaseResponse[DataSourceRead], summary="Get Data Source by ID")
async def get_data_source(id: int, db: AsyncSession = Depends(get_db)):
    """Fetches details, licensing terms, and trust level of a single data source."""
    res = await db.execute(select(DataSource).where(DataSource.id == id))
    ds = res.scalars().first()
    if not ds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source with ID {id} not found",
        )
    return BaseResponse(data=ds)


@router.post("", response_model=BaseResponse[DataSourceRead], status_code=status.HTTP_201_CREATED, summary="Register New Data Source")
async def create_data_source(request: DataSourceCreate, db: AsyncSession = Depends(get_db)):
    """Registers a new external data source with provenance and trust level settings."""
    existing = (
        await db.execute(select(DataSource).where(DataSource.slug == request.slug))
    ).scalars().first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Data source with slug '{request.slug}' already exists",
        )

    ds = DataSource(
        name=request.name,
        slug=request.slug,
        source_type=request.source_type.value,
        provider_type=request.provider_type,
        organization=request.organization,
        base_url=request.base_url,
        description=request.description,
        licensing_notes=request.licensing_notes,
        terms_url=request.terms_url,
        trust_level=request.trust_level,
        is_active=request.is_active,
    )
    db.add(ds)
    await db.commit()
    await db.refresh(ds)
    return BaseResponse(data=ds)
