from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import InvalidFinancialInputException, ResourceNotFoundException
from app.schemas.affordability import (
    AffordabilityBudgetBreakdown,
    AffordabilityCalculateRequest,
    AffordabilityComparisonRequest,
    AffordabilityComparisonResponse,
    AffordabilityProfileInfo,
    MultiVehicleAffordabilityRequest,
    MultiVehicleAffordabilityResponse,
    VehicleAffordabilityRequest,
    VehicleAffordabilityResponse,
)
from app.schemas.common import BaseResponse
from app.services.affordability_service import AffordabilityService

router = APIRouter()


@router.get(
    "/profiles",
    response_model=BaseResponse[List[AffordabilityProfileInfo]],
    summary="Get Configured Affordability Profiles",
    description="Returns all active risk profiles (CONSERVATIVE, BALANCED, STRETCH) with their FOIR thresholds and safe budget multipliers.",
)
async def get_affordability_profiles() -> BaseResponse[List[AffordabilityProfileInfo]]:
    profiles = AffordabilityService.get_profiles()
    return BaseResponse(data=profiles)


@router.post(
    "/calculate",
    response_model=BaseResponse[AffordabilityBudgetBreakdown],
    summary="Calculate User Affordability Capacity",
    description="Calculates user's total purchasing power, max loan, EMI limits, and safe on-road budget boundaries based on net income and selected risk profile.",
)
async def calculate_affordability(
    request: AffordabilityCalculateRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse[AffordabilityBudgetBreakdown]:
    try:
        breakdown = await AffordabilityService.calculate_capacity(db=db, request=request)
        return BaseResponse(data=breakdown)
    except ResourceNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except InvalidFinancialInputException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)


@router.post(
    "/vehicle",
    response_model=BaseResponse[VehicleAffordabilityResponse],
    summary="Evaluate Single Vehicle Affordability",
    description="Evaluates whether a specific vehicle variant is affordable for the user by calculating location-specific on-road price and bank financing terms.",
)
async def evaluate_vehicle_affordability(
    request: VehicleAffordabilityRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse[VehicleAffordabilityResponse]:
    try:
        response = await AffordabilityService.evaluate_vehicle_affordability(db=db, request=request)
        return BaseResponse(data=response)
    except ResourceNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except InvalidFinancialInputException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)


@router.post(
    "/vehicles",
    response_model=BaseResponse[MultiVehicleAffordabilityResponse],
    summary="Evaluate Multiple Vehicles Affordability",
    description="Evaluates a list of vehicle variant IDs against the user's financial profile.",
)
async def evaluate_multiple_vehicles_affordability(
    request: MultiVehicleAffordabilityRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse[MultiVehicleAffordabilityResponse]:
    try:
        response = await AffordabilityService.evaluate_multiple_vehicles(db=db, request=request)
        return BaseResponse(data=response)
    except ResourceNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except InvalidFinancialInputException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)


@router.post(
    "/compare",
    response_model=BaseResponse[AffordabilityComparisonResponse],
    summary="Compare Multiple Vehicles Affordability",
    description="Compares 2 to 5 vehicles side by side against the user's financial capacity and generates comparative insights.",
)
async def compare_vehicles_affordability(
    request: AffordabilityComparisonRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse[AffordabilityComparisonResponse]:
    try:
        response = await AffordabilityService.compare_vehicles(db=db, request=request)
        return BaseResponse(data=response)
    except ResourceNotFoundException as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=exc.message)
    except InvalidFinancialInputException as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message)


# Backward compatibility endpoint
@router.post(
    "/budget-summary",
    response_model=BaseResponse[AffordabilityBudgetBreakdown],
    summary="Compute User Affordability Budget Limits (Legacy Alias)",
    include_in_schema=False,
)
async def analyze_budget_legacy(
    request: AffordabilityCalculateRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse[AffordabilityBudgetBreakdown]:
    return await calculate_affordability(request=request, db=db)
