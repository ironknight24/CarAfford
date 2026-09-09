from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.schemas.affordability import (
    AffordabilityAnalysisRequest,
    AffordabilityBudgetSummary,
)
from app.schemas.common import BaseResponse
from app.services.affordability_engine import AffordabilityEngine

router = APIRouter()


@router.post("/budget-summary", response_model=BaseResponse[AffordabilityBudgetSummary], summary="Compute User Affordability Budget Limits")
async def analyze_budget(
    request: AffordabilityAnalysisRequest,
    db: AsyncSession = Depends(get_db),
):
    cibil = request.cibil_score or 750
    summary = AffordabilityEngine.calculate_budget_summary(
        monthly_take_home_income=request.monthly_take_home_income,
        existing_monthly_emis=request.existing_monthly_emis,
        available_down_payment=request.available_down_payment,
        desired_tenure_months=request.desired_tenure_months,
        cibil_score=cibil,
    )
    return BaseResponse(data=summary)
