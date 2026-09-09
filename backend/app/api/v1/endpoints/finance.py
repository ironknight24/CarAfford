from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.exceptions import InvalidFinancialInputException, ResourceNotFoundException
from app.repositories.finance_repo import FinanceRepository
from app.schemas.common import BaseResponse, PaginatedResponse
from app.schemas.finance import (
    AmortizationScheduleRequest,
    AmortizationScheduleResponse,
    BankComparisonRequest,
    BankComparisonResponse,
    BankRead,
    EmiCalculationRequest,
    EmiCalculationResponse,
    FinanceCalculationRequest,
    FinanceCalculationResponse,
    InterestRateRead,
    LoanEligibilityRequest,
    LoanEligibilityResponse,
    LoanProductRead,
    MaxLoanCalculationRequest,
    MaxLoanCalculationResponse,
)
from app.services.affordability_engine import AffordabilityEngine
from app.services.finance_service import FinanceService
from app.services.financing_engine_service import FinancingEngineService

router = APIRouter()


# =============================================================================
# 1. HIGH-LEVEL VEHICLE FINANCING & BANK COMPARISON APIs
# =============================================================================

@router.post(
    "/calculate",
    response_model=BaseResponse[FinanceCalculationResponse],
    summary="Calculate Vehicle Loan Financing & Repayment Terms",
    description="Calculates comprehensive auto loan financing for a vehicle variant (with on-road price auto-resolution) or explicit on-road price.",
)
async def calculate_vehicle_financing(
    request: FinanceCalculationRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        response = await FinancingEngineService.calculate_financing(db=db, request=request)
        return BaseResponse(data=response)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidFinancialInputException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/compare",
    response_model=BaseResponse[BankComparisonResponse],
    summary="Compare Auto Loan Offers Across Partner Banks",
    description="Evaluates interest rates, fees, monthly EMIs, and eligibility criteria across multiple commercial banks and NBFCs.",
)
async def compare_bank_financing_offers(
    request: BankComparisonRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        response = await FinancingEngineService.compare_bank_financing_offers(db=db, request=request)
        return BaseResponse(data=response)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except InvalidFinancialInputException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# 2. STANDALONE MATHEMATICAL FINANCIAL CALCULATION UTILITIES
# =============================================================================

@router.post(
    "/emi",
    response_model=BaseResponse[EmiCalculationResponse],
    summary="Pure Mathematical EMI Calculation",
)
async def calculate_pure_emi(request: EmiCalculationRequest):
    try:
        emi = FinanceService.calculate_emi(
            principal=request.principal_amount,
            annual_interest_rate=request.annual_interest_rate,
            tenure_months=request.tenure_months,
        )
        total_payable = emi * Decimal(str(request.tenure_months))
        total_interest = total_payable - request.principal_amount
        return BaseResponse(
            data=EmiCalculationResponse(
                principal_amount=request.principal_amount,
                annual_interest_rate=request.annual_interest_rate,
                tenure_months=request.tenure_months,
                monthly_emi=emi,
                total_interest_payable=total_interest,
                total_amount_payable=total_payable,
            )
        )
    except InvalidFinancialInputException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/max-loan",
    response_model=BaseResponse[MaxLoanCalculationResponse],
    summary="Calculate Maximum Principal from Monthly EMI Budget (Reverse EMI)",
)
async def calculate_max_loan_from_emi(request: MaxLoanCalculationRequest):
    try:
        max_principal = FinanceService.maximum_loan_for_emi(
            maximum_emi=request.maximum_emi,
            annual_interest_rate=request.annual_interest_rate,
            tenure_months=request.tenure_months,
        )
        return BaseResponse(
            data=MaxLoanCalculationResponse(
                maximum_emi=request.maximum_emi,
                annual_interest_rate=request.annual_interest_rate,
                tenure_months=request.tenure_months,
                maximum_principal=max_principal,
            )
        )
    except InvalidFinancialInputException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/amortization",
    response_model=BaseResponse[AmortizationScheduleResponse],
    summary="Generate Complete Monthly Amortization Repayment Schedule",
)
async def generate_amortization_schedule(request: AmortizationScheduleRequest):
    try:
        schedule = FinanceService.calculate_amortization_schedule(
            principal=request.principal,
            annual_interest_rate=request.annual_interest_rate,
            tenure_months=request.tenure_months,
        )
        emi = schedule[0].emi if schedule else Decimal("0.00")
        total_interest = sum(item.interest_component for item in schedule)
        total_repayment = sum(item.emi for item in schedule)
        return BaseResponse(
            data=AmortizationScheduleResponse(
                principal=request.principal,
                annual_interest_rate=request.annual_interest_rate,
                tenure_months=request.tenure_months,
                monthly_emi=emi,
                total_interest=total_interest,
                total_repayment=total_repayment,
                schedule=schedule,
            )
        )
    except InvalidFinancialInputException as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# =============================================================================
# 3. BANKS, LOAN PRODUCTS & RATES CATALOG APIs (Paginated)
# =============================================================================

@router.get(
    "/banks",
    response_model=PaginatedResponse[BankRead],
    summary="List Partner Banks and NBFCs",
)
async def get_banks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    repo = FinanceRepository(db)
    items, total = await repo.get_banks(page=page, page_size=page_size, active=active, search=search)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.get(
    "/banks/{bank_id}",
    response_model=BaseResponse[BankRead],
    summary="Get Bank Details by ID",
)
async def get_bank_by_id(
    bank_id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = FinanceRepository(db)
    bank = await repo.get_bank_by_id(bank_id)
    if not bank:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Bank with ID {bank_id} not found.")
    return BaseResponse(data=bank)


@router.get(
    "/loan-products",
    response_model=PaginatedResponse[LoanProductRead],
    summary="List Auto Loan Products",
)
async def get_loan_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    bank_id: Optional[int] = Query(None),
    vehicle_type: Optional[str] = Query(None),
    vehicle_condition: Optional[str] = Query(None),
    product_category: Optional[str] = Query(None),
    active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    repo = FinanceRepository(db)
    items, total = await repo.get_loan_products(
        page=page,
        page_size=page_size,
        bank_id=bank_id,
        vehicle_type=vehicle_type,
        vehicle_condition=vehicle_condition,
        product_category=product_category,
        active=active,
        search=search,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.get(
    "/loan-products/{product_id}",
    response_model=BaseResponse[LoanProductRead],
    summary="Get Loan Product Details by ID",
)
async def get_loan_product_by_id(
    product_id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = FinanceRepository(db)
    product = await repo.get_loan_product_by_id(product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Loan product with ID {product_id} not found.")
    return BaseResponse(data=product)


@router.get(
    "/rates",
    response_model=PaginatedResponse[InterestRateRead],
    summary="List Interest Rate Records",
)
async def get_interest_rates(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    loan_product_id: Optional[int] = Query(None),
    active: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    repo = FinanceRepository(db)
    items, total = await repo.get_interest_rates(
        page=page,
        page_size=page_size,
        loan_product_id=loan_product_id,
        active=active,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse(items=items, total=total, page=page, page_size=page_size, total_pages=total_pages)


@router.get(
    "/rates/{rate_id}",
    response_model=BaseResponse[InterestRateRead],
    summary="Get Interest Rate by ID",
)
async def get_interest_rate_by_id(
    rate_id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = FinanceRepository(db)
    rate = await repo.get_interest_rate_by_id(rate_id)
    if not rate:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Interest rate with ID {rate_id} not found.")
    return BaseResponse(data=rate)


# =============================================================================
# 4. LEGACY BACKWARDS-COMPATIBILITY ENDPOINTS
# =============================================================================

@router.post(
    "/calculate-emi",
    response_model=BaseResponse[EmiCalculationResponse],
    summary="Calculate Auto Loan EMI & Amortization (Legacy)",
)
async def calculate_emi_legacy(
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
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/loan-eligibility",
    response_model=BaseResponse[LoanEligibilityResponse],
    summary="Estimate Maximum Loan Eligibility (Legacy Budget Approach)",
)
async def calculate_loan_eligibility_legacy(
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

    status_str = "Eligible"
    if summary.available_car_emi_budget <= Decimal("5000.00"):
        status_str = "Marginal"
    if summary.available_car_emi_budget <= Decimal("0.00"):
        status_str = "Ineligible"

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
            eligibility_status=status_str,
        )
    )
