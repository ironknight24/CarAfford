from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.core.exceptions import ResourceNotFoundException
from app.repositories.pricing_repo import PricingRepository
from app.schemas.common import BaseResponse
from app.schemas.pricing import (
    OnRoadPriceBreakdown,
    OnRoadPriceRequest,
    PriceHistoryRead,
)
from app.services.pricing_service import PricingService

router = APIRouter()


@router.post("/on-road-breakdown", response_model=BaseResponse[OnRoadPriceBreakdown], summary="Calculate Detailed On-Road Price Breakdown")
async def get_on_road_price(request: OnRoadPriceRequest, db: AsyncSession = Depends(get_db)):
    service = PricingService(db)
    try:
        breakdown = await service.calculate_on_road_price(request)
        return BaseResponse(data=breakdown)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history/{variant_id}", response_model=BaseResponse[List[PriceHistoryRead]], summary="Get Historical Price Logs for Variant")
async def get_price_history(variant_id: int, db: AsyncSession = Depends(get_db)):
    repo = PricingRepository(db)
    history = await repo.get_price_history(variant_id)
    return BaseResponse(data=history)
