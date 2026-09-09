from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import AuditSchemaMixin


class BankRead(AuditSchemaMixin):
    id: int
    name: str
    slug: str
    bank_type: str
    logo_url: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class InterestRateSlabRead(AuditSchemaMixin):
    id: int
    loan_product_id: int
    min_cibil_score: int
    max_cibil_score: int
    min_interest_rate: Decimal
    max_interest_rate: Decimal
    default_interest_rate: Decimal
    is_fixed: bool

    model_config = ConfigDict(from_attributes=True)


class LoanProductRead(AuditSchemaMixin):
    id: int
    bank_id: int
    name: str
    slug: str
    min_loan_amount: Decimal
    max_loan_amount: Decimal
    min_tenure_months: int
    max_tenure_months: int
    max_ltv_percent: Decimal
    processing_fee_percent: Decimal
    min_processing_fee: Decimal
    max_processing_fee: Decimal
    is_active: bool
    bank: Optional[BankRead] = None
    interest_rate_slabs: List[InterestRateSlabRead] = []

    model_config = ConfigDict(from_attributes=True)


class EmiCalculationRequest(BaseModel):
    principal_amount: Decimal = Field(gt=0, description="Loan principal amount in INR")
    annual_interest_rate: Decimal = Field(gt=0, le=36, description="Annual interest rate percentage (e.g. 8.75)")
    tenure_months: int = Field(ge=12, le=120, description="Loan tenure in months (e.g. 60 for 5 years)")


class AmortizationScheduleItem(BaseModel):
    month: int
    beginning_balance: Decimal
    emi: Decimal
    principal_paid: Decimal
    interest_paid: Decimal
    ending_balance: Decimal


class EmiCalculationResponse(BaseModel):
    principal_amount: Decimal
    annual_interest_rate: Decimal
    tenure_months: int
    monthly_emi: Decimal
    total_interest_payable: Decimal
    total_amount_payable: Decimal
    amortization_schedule: Optional[List[AmortizationScheduleItem]] = None


class LoanEligibilityRequest(BaseModel):
    monthly_take_home_income: Decimal = Field(gt=0, description="Net monthly income in INR")
    existing_monthly_emis: Decimal = Field(default=Decimal("0.00"), ge=0, description="Existing ongoing EMIs")
    tenure_months: int = Field(default=60, ge=12, le=120)
    cibil_score: Optional[int] = Field(default=750, ge=300, le=900)
    foir_limit_percent: Optional[Decimal] = Field(default=Decimal("40.0"), ge=10, le=70, description="FOIR / DTI limit %")
    annual_interest_rate: Optional[Decimal] = None  # If not provided, determined from CIBIL/Bank slabs


class LoanEligibilityResponse(BaseModel):
    monthly_take_home_income: Decimal
    existing_monthly_emis: Decimal
    max_total_emi_allowed: Decimal
    available_car_emi_budget: Decimal
    interest_rate_used: Decimal
    tenure_months: int
    max_affordable_loan_amount: Decimal
    recommended_bank: Optional[str] = None
    eligibility_status: str  # Eligible, Marginal, Ineligible
