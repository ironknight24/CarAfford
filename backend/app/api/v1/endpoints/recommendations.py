from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import InvalidFinancialInputException, ResourceNotFoundException
from app.schemas.common import BaseResponse
from app.schemas.recommendation import (
    QuickRecommendationRequest,
    RecommendationCompareRequest,
    RecommendationCompareResponse,
    RecommendationRequest,
    RecommendationResponse,
    ScoringConfigResponse,
)
from app.services.recommendation_service import RecommendationService

router = APIRouter()


@router.get(
    "/scoring-config",
    response_model=BaseResponse[ScoringConfigResponse],
    summary="Get recommendation scoring weights and categories",
    description="Returns active scoring dimension weights (Affordability, TCO, Preferences, Monthly Cost, Vehicle Value) and category definitions.",
)
async def get_scoring_config() -> BaseResponse[ScoringConfigResponse]:
    config = RecommendationService.get_scoring_config()
    return BaseResponse(
        success=True,
        data=config,
    )


@router.post(
    "",
    response_model=BaseResponse[RecommendationResponse],
    summary="Generate ranked vehicle recommendations",
    description="Orchestrates vehicle filtering, location-specific on-road pricing, bank financing, and 5-year TCO to score and rank matching cars.",
)
async def get_recommendations(
    request: RecommendationRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse[RecommendationResponse]:
    try:
        recommendations = await RecommendationService.get_car_recommendations(db, request)
        return BaseResponse(
            success=True,
            data=recommendations,
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InvalidFinancialInputException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/quick",
    response_model=BaseResponse[RecommendationResponse],
    summary="Generate quick vehicle recommendations",
    description="Simplified recommendation workflow using minimal user financial inputs.",
)
async def get_quick_recommendations(
    request: QuickRecommendationRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse[RecommendationResponse]:
    try:
        recommendations = await RecommendationService.get_quick_recommendations(db, request)
        return BaseResponse(
            success=True,
            data=recommendations,
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InvalidFinancialInputException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/compare",
    response_model=BaseResponse[RecommendationCompareResponse],
    summary="Compare specific vehicles using recommendation scoring",
    description="Ranks explicitly selected vehicle variants using the multi-dimensional recommendation scoring model.",
)
async def compare_recommendations(
    request: RecommendationCompareRequest,
    db: AsyncSession = Depends(get_db),
) -> BaseResponse[RecommendationCompareResponse]:
    try:
        comparison = await RecommendationService.compare_recommendations(db, request)
        return BaseResponse(
            success=True,
            data=comparison,
        )
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (InvalidFinancialInputException, ValueError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
