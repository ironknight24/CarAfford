from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import InvalidFinancialInputException, ResourceNotFoundException
from app.schemas.common import BaseResponse
from app.schemas.tco import (
    TCOAssumptionsResponse,
    TCOCalculationRequest,
    TCOCalculationResponse,
    TCOComparisonRequest,
    TCOComparisonResponse,
    TCOVehicleRequest,
)
from app.services.tco_service import TCOService

router = APIRouter()


@router.get(
    "/assumptions",
    response_model=BaseResponse[TCOAssumptionsResponse],
    summary="Get active TCO baseline assumptions",
    description="Returns configurable benchmark fuel prices, maintenance rates, insurance renewal factors, and depreciation curves with data provenance.",
)
async def get_tco_assumptions() -> BaseResponse[TCOAssumptionsResponse]:
    assumptions = TCOService.get_assumptions()
    return BaseResponse(
        success=True,
        data=assumptions,
    )


@router.post(
    "/calculate",
    response_model=BaseResponse[TCOCalculationResponse],
    summary="Calculate Total Cost of Ownership (TCO)",
    description="Calculates comprehensive ongoing ownership costs (fuel, insurance, maintenance, loan financing) across 1-year, 3-year, and 5-year periods.",
)
async def calculate_tco(
    request: TCOCalculationRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse[TCOCalculationResponse]:
    try:
        response = await TCOService.calculate_tco(db, request)
        return BaseResponse(
            success=True,
            data=response,
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InvalidFinancialInputException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/vehicle",
    response_model=BaseResponse[TCOCalculationResponse],
    summary="Calculate vehicle-specific TCO",
    description="Calculates TCO for a specific variant using location-specific on-road price, OEM efficiency, and banking products.",
)
async def calculate_vehicle_tco(
    request: TCOVehicleRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse[TCOCalculationResponse]:
    try:
        response = await TCOService.calculate_vehicle_tco(db, request)
        return BaseResponse(
            success=True,
            data=response,
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InvalidFinancialInputException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/compare",
    response_model=BaseResponse[TCOComparisonResponse],
    summary="Compare TCO across multiple vehicles",
    description="Evaluates and ranks multiple vehicle variants side-by-side on 1-year, 3-year, and 5-year TCO.",
)
async def compare_vehicles_tco(
    request: TCOComparisonRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse[TCOComparisonResponse]:
    try:
        response = await TCOService.compare_vehicles_tco(db, request)
        return BaseResponse(
            success=True,
            data=response,
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InvalidFinancialInputException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
