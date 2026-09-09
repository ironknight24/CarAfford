from decimal import Decimal
from typing import Any, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.affordability import AffordabilityAnalysisRequest
from app.schemas.recommendation import RecommendationRequest, RecommendationResponse
from app.services.recommendation_service import RecommendationService


class RecommendationEngine:
    """Backward-compatible wrapper delegating to RecommendationService."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_car_recommendations(
        self,
        request: Any,
    ) -> RecommendationResponse:
        if isinstance(request, RecommendationRequest):
            rec_req = request
        elif isinstance(request, AffordabilityAnalysisRequest):
            fuel_pref = request.preferred_fuel_types[0] if request.preferred_fuel_types else None
            body_pref = request.preferred_body_types[0] if request.preferred_body_types else None
            trans_pref = request.preferred_transmission[0] if request.preferred_transmission else None

            rec_req = RecommendationRequest(
                monthly_take_home_income=request.monthly_take_home_income,
                existing_monthly_emi=request.existing_monthly_emis,
                available_down_payment=request.available_down_payment,
                state_id=request.state_id,
                city_id=request.city_id,
                credit_score=request.cibil_score or 750,
                preferred_loan_tenure_months=request.desired_tenure_months or 60,
                monthly_driving_distance_km=Decimal(str(request.monthly_commute_km or 1000)),
                fuel_preference=fuel_pref,
                body_type=body_pref,
                transmission=trans_pref,
            )
        else:
            rec_req = RecommendationRequest.model_validate(request)

        return await RecommendationService.get_car_recommendations(self.session, rec_req)
