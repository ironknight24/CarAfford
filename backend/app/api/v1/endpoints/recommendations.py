from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.schemas.affordability import AffordabilityAnalysisRequest
from app.schemas.common import BaseResponse
from app.schemas.recommendation import RecommendationResponse
from app.services.recommendation_engine import RecommendationEngine

router = APIRouter()


@router.post("", response_model=BaseResponse[RecommendationResponse], summary="Generate Ranked Affordable Car Recommendations")
async def get_recommendations(
    request: AffordabilityAnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    engine = RecommendationEngine(db)
    try:
        recommendations = await engine.get_car_recommendations(request)
        return BaseResponse(data=recommendations)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
