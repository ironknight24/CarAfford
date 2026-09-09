from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.core.exceptions import InvalidFinancialInputException
from app.repositories.finance_repo import FinanceRepository
from app.schemas.common import BaseResponse
from app.schemas.finance import (
    BankRead,
    EmiCalculationRequest,
    EmiCalculationResponse,
    LoanEligibilityRequest,
    LoanEligibilityResponse,
    LoanProductRead,
)
from app.services.affordability_engine import AffordabilityEngine
from app.services.finance_service import FinanceService

router = APIRouter()


@router.get("/banks", response_model=BaseResponse[List[BankRead]], summary="Get Partner Banks and Loan Products")
async def get_banks(db: AsyncSession = Depends(get_db)):
    repo = FinanceRepository(db)
    banks = await repo.get_banks()
    return BaseResponse(data=banks)


@router.post("/calculate-emi", response_model=BaseResponse[EmiCalculationResponse], summary="Calculate Auto Loan EMI & Amortization")
async def calculate_emi(
    request: EmiCalculationRequest,
    generate_schedule: bool = Query(False, description="Whether to include month-by-month amortization schedule"),
):
    try:
        response = FinanceService.calculate_full_loan_summary(
            principal=request.principal_amount,
            annual_interest_rate=request.annual_interest_rate,
            tenure_months=request.tenure_months,
            generate_amortization=generate_schedule,
        )
        return BaseResponse(data=response)
    except InvalidFinancialInputException as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/loan-eligibility", response_model=BaseResponse[LoanEligibilityResponse], summary="Estimate Maximum Loan Eligibility")
async def calculate_loan_eligibility(
    request: LoanEligibilityRequest,
    db: AsyncSession = Depends(get_db),
):
    cibil = request.cibil_score or 750
    interest_rate = request.annual_interest_rate or FinanceService.resolve_interest_rate_by_cibil(cibil)
    foir_ratio = (request.foir_limit_percent or Decimal("40.0")) / Decimal("100.0")

    summary = AffordabilityEngine.calculate_budget_summary(
        monthly_take_home_income=request.monthly_take_home_income,
        existing_monthly_emis=request.existing_monthly_emis,
        desired_tenure_months=request.tenure_months,
        cibil_score=cibil,
        foir_limit_ratio=foir_ratio,
    )

    status = "Eligible"
    if summary.available_car_emi_budget <= Decimal("5000.00"):
        status = "Marginal"
    if summary.available_car_emi_budget <= Decimal("0.00"):
        status = "Ineligible"

    return BaseResponse(
        data=LoanEligibilityResponse(
            monthly_take_home_income=summary.monthly_take_home_income,
            existing_monthly_emis=summary.existing_monthly_emis,
            max_total_emi_allowed=summary.max_total_emi_allowed,
            available_car_emi_budget=summary.available_car_emi_budget,
            interest_rate_used=interest_rate,
            tenure_months=request.tenure_months,
            max_affordable_loan_amount=summary.max_affordable_loan,
            recommended_bank="State Bank of India (SBI)" if cibil >= 750 else "HDFC Bank",
            eligibility_status=status,
        )
    )
