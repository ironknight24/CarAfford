from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.models.data_source import DataSource
from app.schemas.common import BaseResponse
from app.schemas.data_source import DataSourceRead

router = APIRouter()


@router.get("", response_model=BaseResponse[List[DataSourceRead]], summary="List Tracked External Data Sources and Freshness")
async def list_data_sources(db: AsyncSession = Depends(get_db)):
    stmt = select(DataSource).order_by(DataSource.name)
    result = await db.execute(stmt)
    sources = list(result.scalars().all())
    return BaseResponse(data=sources)
