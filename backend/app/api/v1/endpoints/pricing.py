from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import ResourceNotFoundException
from app.repositories.pricing_repo import PricingRepository
from app.schemas.common import BaseResponse
from app.schemas.pricing import (
    OnRoadPriceBreakdown,
    OnRoadPriceCalculationRequest,
    OnRoadPriceRequest,
    OnRoadPriceResponse,
    PriceHistoryRead,
)
from app.services.on_road_price_service import OnRoadPriceCalculationService
from app.services.pricing_service import PricingService

router = APIRouter()


@router.post(
    "/on-road",
    response_model=BaseResponse[OnRoadPriceResponse],
    summary="Calculate Full Location-Specific On-Road Price",
    description="Calculates comprehensive on-road price breakdown with statutory taxes, fees, TCS, insurance, and audit provenance.",
)
async def calculate_on_road_price(
    request: OnRoadPriceCalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        response = await OnRoadPriceCalculationService.calculate_on_road_price(
            db=db,
            request=request,
        )
        return BaseResponse(data=response)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/on-road/{variant_id}",
    response_model=BaseResponse[OnRoadPriceResponse],
    summary="Calculate On-Road Price for Variant by Query Params",
    description="Quick calculation endpoint for a variant given state, optional city/RTO, and calculation preferences.",
)
async def get_on_road_price_by_variant(
    variant_id: int,
    state_id: int = Query(..., description="ID of the State/UT"),
    city_id: Optional[int] = Query(None, description="Optional ID of the City"),
    rto_id: Optional[int] = Query(None, description="Optional ID of the RTO"),
    calculation_date: Optional[datetime] = Query(None, description="Target calculation date"),
    insurance_option: str = Query("DEFAULT_ESTIMATE", description="DEFAULT_ESTIMATE, USER_PROVIDED, ZERO_DEP, THIRD_PARTY_ONLY"),
    insurance_amount: Optional[Decimal] = Query(None, description="Custom insurance quote if USER_PROVIDED"),
    is_bh_series: bool = Query(False, description="Apply BH-series calculation"),
    is_financed: bool = Query(True, description="Vehicle is financed (affects hypothecation fees)"),
    db: AsyncSession = Depends(get_db),
):
    request = OnRoadPriceCalculationRequest(
        variant_id=variant_id,
        state_id=state_id,
        city_id=city_id,
        rto_id=rto_id,
        calculation_date=calculation_date,
        insurance_option=insurance_option,
        insurance_amount=insurance_amount,
        is_bh_series=is_bh_series,
        is_financed=is_financed,
    )
    try:
        response = await OnRoadPriceCalculationService.calculate_on_road_price(
            db=db,
            request=request,
        )
        return BaseResponse(data=response)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/on-road-breakdown",
    response_model=BaseResponse[OnRoadPriceBreakdown],
    summary="Calculate Detailed On-Road Price Breakdown (Legacy)",
)
async def get_on_road_price_legacy(
    request: OnRoadPriceRequest,
    db: AsyncSession = Depends(get_db),
):
    service = PricingService(db)
    try:
        breakdown = await service.calculate_on_road_price(request)
        return BaseResponse(data=breakdown)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/history/{variant_id}",
    response_model=BaseResponse[List[PriceHistoryRead]],
    summary="Get Historical Price Logs for Variant",
)
async def get_price_history(
    variant_id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = PricingRepository(db)
    history = await repo.get_price_history(variant_id)
    return BaseResponse(data=history)

