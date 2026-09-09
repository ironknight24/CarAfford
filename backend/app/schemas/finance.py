from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.common import AuditSchemaMixin


# =============================================================================
# 1. READ / WRITE DTOs FOR ENTITIES
# =============================================================================

class BankBase(BaseModel):
    name: str = Field(..., max_length=100)
    slug: str = Field(..., max_length=100)
    bank_type: str = Field(default="Public", max_length=50)
    website_url: Optional[str] = None
    logo_url: Optional[str] = None
    active: bool = True


class BankCreate(BankBase):
    source_id: Optional[int] = None


class BankRead(BankBase):
    id: int
    source_id: Optional[int] = None
    is_active: Optional[bool] = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InterestRateBase(BaseModel):
    annual_interest_rate: Decimal = Field(..., gt=0, le=36, description="Annual percentage rate (e.g. 8.75)")
    rate_type: str = Field(default="FLOATING", description="FIXED, FLOATING, VARIABLE")
    min_credit_score: Optional[int] = Field(None, ge=300, le=900)
    max_credit_score: Optional[int] = Field(None, ge=300, le=900)
    min_tenure_months: Optional[int] = Field(None, ge=1, le=120)
    max_tenure_months: Optional[int] = Field(None, ge=1, le=120)
    min_loan_amount: Optional[Decimal] = Field(None, ge=0)
    max_loan_amount: Optional[Decimal] = Field(None, ge=0)
    employment_type: Optional[str] = None
    priority: int = 100
    effective_from: datetime
    effective_to: Optional[datetime] = None
    active: bool = True


class InterestRateCreate(InterestRateBase):
    loan_product_id: int
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None


class InterestRateRead(InterestRateBase):
    id: int
    loan_product_id: int
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LoanEligibilityRuleBase(BaseModel):
    rule_name: str = Field(..., max_length=150)
    min_monthly_income: Optional[Decimal] = Field(None, ge=0)
    min_credit_score: Optional[int] = Field(None, ge=300, le=900)
    max_credit_score: Optional[int] = Field(None, ge=300, le=900)
    max_loan_amount: Optional[Decimal] = Field(None, ge=0)
    max_ltv_percent: Optional[Decimal] = Field(None, ge=0, le=100)
    max_foir_percent: Optional[Decimal] = Field(default=Decimal("50.00"), ge=10, le=90)
    min_age_years: Optional[int] = Field(default=21, ge=18, le=100)
    max_age_years: Optional[int] = Field(default=65, ge=18, le=100)
    min_employment_months: Optional[int] = Field(default=12, ge=0)
    allowed_employment_types: Optional[str] = "SALARIED,SELF_EMPLOYED"
    allowed_residency_types: Optional[str] = "RESIDENT_INDIAN,NRI"
    effective_from: datetime
    effective_to: Optional[datetime] = None
    active: bool = True


class LoanEligibilityRuleCreate(LoanEligibilityRuleBase):
    loan_product_id: int
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None


class LoanEligibilityRuleRead(LoanEligibilityRuleBase):
    id: int
    loan_product_id: int
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LoanFeeBase(BaseModel):
    fee_name: str = Field(..., max_length=150)
    fee_type: str = Field(default="PROCESSING_FEE", description="PROCESSING_FEE, DOCUMENTATION_FEE, VALUATION_FEE, FORECLOSURE_CHARGE, OTHER")
    calculation_method: str = Field(default="PERCENTAGE", description="FIXED, PERCENTAGE, CAPPED_PERCENTAGE, WAIVED")
    fixed_amount: Optional[Decimal] = Field(None, ge=0)
    percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    minimum_amount: Optional[Decimal] = Field(None, ge=0)
    maximum_amount: Optional[Decimal] = Field(None, ge=0)
    effective_from: datetime
    effective_to: Optional[datetime] = None
    active: bool = True


class LoanFeeCreate(LoanFeeBase):
    loan_product_id: int
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None


class LoanFeeRead(LoanFeeBase):
    id: int
    loan_product_id: int
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InterestRateSlabRead(BaseModel):
    """Legacy slab schema for backward compatibility."""
    id: int
    loan_product_id: int
    min_cibil_score: int
    max_cibil_score: int
    min_interest_rate: Decimal
    max_interest_rate: Decimal
    default_interest_rate: Decimal
    is_fixed: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class LoanProductBase(BaseModel):
    name: str = Field(..., max_length=150)
    slug: str = Field(..., max_length=150)
    vehicle_type: str = Field(default="CAR")
    vehicle_condition: str = Field(default="NEW")
    product_category: str = Field(default="STANDARD")
    min_loan_amount: Decimal = Field(default=Decimal("100000.00"), ge=0)
    max_loan_amount: Decimal = Field(default=Decimal("10000000.00"), ge=0)
    min_tenure_months: int = Field(default=12, ge=1)
    max_tenure_months: int = Field(default=84, ge=1)
    max_ltv_percent: Decimal = Field(default=Decimal("90.00"), ge=0, le=100)
    processing_fee_percent: Decimal = Field(default=Decimal("0.50"), ge=0)
    min_processing_fee: Decimal = Field(default=Decimal("1500.00"), ge=0)
    max_processing_fee: Decimal = Field(default=Decimal("10000.00"), ge=0)
    description: Optional[str] = None
    active: bool = True


class LoanProductCreate(LoanProductBase):
    bank_id: int


class LoanProductRead(LoanProductBase):
    id: int
    bank_id: int
    bank: Optional[BankRead] = None
    interest_rates: List[InterestRateRead] = []
    eligibility_rules: List[LoanEligibilityRuleRead] = []
    fees: List[LoanFeeRead] = []
    interest_rate_slabs: List[InterestRateSlabRead] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# 2. FINANCIAL CALCULATION DTOs (EMI, AMORTIZATION, MAX LOAN, LTV)
# =============================================================================

class EmiCalculationRequest(BaseModel):
    principal_amount: Optional[Decimal] = Field(None, gt=0, description="Loan principal amount in INR")
    loan_amount: Optional[Decimal] = Field(None, gt=0, description="Alternative alias for principal amount")
    annual_interest_rate: Decimal = Field(gt=0, le=36, description="Annual interest rate percentage (e.g. 8.75)")
    tenure_months: int = Field(ge=1, le=120, description="Loan tenure in months (e.g. 60 for 5 years)")

    @model_validator(mode="before")
    @classmethod
    def resolve_principal(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "principal_amount" not in data and "loan_amount" in data:
                data["principal_amount"] = data["loan_amount"]
        return data


class AmortizationScheduleItem(BaseModel):
    installment_number: int
    month: int
    opening_balance: Decimal
    beginning_balance: Optional[Decimal] = None  # alias
    emi: Decimal
    principal_component: Decimal
    principal_paid: Optional[Decimal] = None  # alias
    interest_component: Decimal
    interest_paid: Optional[Decimal] = None  # alias
    closing_balance: Decimal
    ending_balance: Optional[Decimal] = None  # alias


class EmiCalculationResponse(BaseModel):
    principal_amount: Decimal
    annual_interest_rate: Decimal
    tenure_months: int
    monthly_emi: Decimal
    total_interest_payable: Decimal
    total_amount_payable: Decimal
    total_payment: Optional[Decimal] = None  # alias
    amortization_schedule: Optional[List[AmortizationScheduleItem]] = None

    @model_validator(mode="after")
    def populate_aliases(self) -> "EmiCalculationResponse":
        if self.total_payment is None:
            self.total_payment = self.total_amount_payable
        return self


class MaxLoanCalculationRequest(BaseModel):
    maximum_emi: Optional[Decimal] = Field(None, gt=0, description="Maximum affordable monthly EMI in INR")
    desired_monthly_emi: Optional[Decimal] = Field(None, gt=0, description="Alternative alias for maximum EMI")
    annual_interest_rate: Decimal = Field(gt=0, le=36, description="Annual interest rate percentage (e.g. 8.75)")
    tenure_months: int = Field(ge=1, le=120, description="Loan tenure in months")

    @model_validator(mode="before")
    @classmethod
    def resolve_emi(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "maximum_emi" not in data and "desired_monthly_emi" in data:
                data["maximum_emi"] = data["desired_monthly_emi"]
        return data


class MaxLoanCalculationResponse(BaseModel):
    maximum_emi: Decimal
    annual_interest_rate: Decimal
    tenure_months: int
    maximum_principal: Decimal
    maximum_loan_amount: Optional[Decimal] = None  # alias

    @model_validator(mode="after")
    def populate_aliases(self) -> "MaxLoanCalculationResponse":
        if self.maximum_loan_amount is None:
            self.maximum_loan_amount = self.maximum_principal
        return self


class AmortizationScheduleRequest(BaseModel):
    principal: Optional[Decimal] = Field(None, gt=0, description="Loan principal amount in INR")
    loan_amount: Optional[Decimal] = Field(None, gt=0, description="Alternative alias for principal amount")
    annual_interest_rate: Decimal = Field(gt=0, le=36, description="Annual interest rate percentage (e.g. 8.75)")
    tenure_months: int = Field(ge=1, le=120, description="Loan tenure in months")

    @model_validator(mode="before")
    @classmethod
    def resolve_principal(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "principal" not in data and "loan_amount" in data:
                data["principal"] = data["loan_amount"]
        return data


class AmortizationScheduleResponse(BaseModel):
    principal: Decimal
    annual_interest_rate: Decimal
    tenure_months: int
    monthly_emi: Decimal
    total_interest: Decimal
    total_repayment: Decimal
    schedule: List[AmortizationScheduleItem]


# =============================================================================
# 3. HIGH-LEVEL FINANCING & BANK COMPARISON DTOs
# =============================================================================

class FinanceCalculationRequest(BaseModel):
    vehicle_variant_id: Optional[int] = Field(None, description="Vehicle variant ID to auto-calculate authoritative on-road price")
    state_id: Optional[int] = Field(None, description="State ID for on-road pricing if vehicle_variant_id is supplied")
    city_id: Optional[int] = Field(None, description="Optional City ID")
    rto_id: Optional[int] = Field(None, description="Optional RTO ID")
    on_road_price: Optional[Decimal] = Field(None, gt=0, description="Explicit on-road price if vehicle_variant_id is omitted")
    loan_amount: Optional[Decimal] = Field(None, gt=0, description="Direct loan principal amount")
    
    down_payment: Decimal = Field(default=Decimal("0.00"), ge=0, description="Available down payment in INR")
    loan_tenure_months: int = Field(default=60, ge=12, le=120, description="Desired loan tenure in months")
    tenure_months: Optional[int] = Field(None, ge=12, le=120, description="Alternative alias for loan_tenure_months")
    credit_score: Optional[int] = Field(default=750, ge=300, le=900, description="Applicant credit score (e.g. CIBIL)")
    monthly_income: Optional[Decimal] = Field(None, ge=0, description="Monthly take-home income for eligibility check")
    employment_type: Optional[str] = Field(default="SALARIED", description="SALARIED or SELF_EMPLOYED")
    applicant_age: Optional[int] = Field(default=30, ge=18, le=100)
    
    bank_id: Optional[int] = Field(None, description="Optional specific bank to target")
    loan_product_id: Optional[int] = Field(None, description="Optional specific loan product to target")
    calculation_date: Optional[datetime] = Field(None, description="Target calculation date for historical rate resolution")
    include_amortization: bool = Field(default=False, description="Include full month-by-month amortization schedule")

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "tenure_months" in data and "loan_tenure_months" not in data:
                data["loan_tenure_months"] = data["tenure_months"]
            if "loan_amount" in data and "on_road_price" not in data and "vehicle_variant_id" not in data:
                dp = Decimal(str(data.get("down_payment", "0.00")))
                data["on_road_price"] = Decimal(str(data["loan_amount"])) + dp
        return data


class FeeBreakdownItem(BaseModel):
    fee_name: str
    fee_type: str
    calculation_method: str
    rate_or_amount: Optional[Decimal] = None
    calculated_amount: Decimal


class LoanOfferItem(BaseModel):
    bank_id: int
    bank_name: str
    bank_slug: str
    bank_type: str
    logo_url: Optional[str] = None
    loan_product_id: int
    product_name: str
    product_slug: str
    product_category: str
    
    annual_interest_rate: Decimal
    rate_type: str  # FIXED, FLOATING, VARIABLE
    tenure_months: int
    principal_loan_amount: Decimal
    monthly_emi: Decimal
    total_interest: Decimal
    total_repayment: Decimal
    
    ltv_percent: Decimal
    processing_fee: Decimal
    total_fees: Decimal
    fees_breakdown: List[FeeBreakdownItem] = []
    
    estimated_eligibility: bool
    eligibility_status: str  # ESTIMATED_ELIGIBLE, MARGINAL, ESTIMATED_INELIGIBLE
    eligibility_reasons: List[str] = []
    
    rate_effective_from: datetime
    rate_effective_to: Optional[datetime] = None
    rate_source_name: Optional[str] = None
    is_recommended: bool = False
    data_status: str = "DEMO"
    disclaimer: str = "Estimated eligibility only - not a credit sanction. Actual rates and fees depend on bank underwriting."


class FinanceCalculationResponse(BaseModel):
    variant_id: Optional[int] = None
    variant_name: Optional[str] = None
    model_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    on_road_price: Decimal
    down_payment: Decimal
    loan_amount: Decimal
    tenure_months: int
    credit_score_used: int
    calculation_date: datetime
    
    selected_offer: LoanOfferItem
    amortization_schedule: Optional[List[AmortizationScheduleItem]] = None
    
    bank_name: Optional[str] = None
    applied_interest_rate: Optional[Decimal] = None
    eligibility: Optional[Dict[str, Any]] = None
    
    data_quality: Dict[str, Any] = {
        "is_estimated": True,
        "data_status": "DEMO",
        "disclaimer": "Financing terms are based on demonstration bank products and do not constitute an official loan sanction.",
    }

    @model_validator(mode="after")
    def populate_convenience_fields(self) -> "FinanceCalculationResponse":
        if self.bank_name is None:
            self.bank_name = self.selected_offer.bank_name
        if self.applied_interest_rate is None:
            self.applied_interest_rate = self.selected_offer.annual_interest_rate
        if self.eligibility is None:
            self.eligibility = {
                "is_eligible": self.selected_offer.estimated_eligibility,
                "status": self.selected_offer.eligibility_status,
                "reasons": self.selected_offer.eligibility_reasons,
            }
        return self


class BankComparisonRequest(BaseModel):
    vehicle_variant_id: Optional[int] = Field(None, description="Vehicle variant ID")
    state_id: Optional[int] = Field(None, description="State ID")
    city_id: Optional[int] = Field(None, description="City ID")
    rto_id: Optional[int] = Field(None, description="RTO ID")
    on_road_price: Optional[Decimal] = Field(None, gt=0, description="Explicit on-road price if vehicle_variant_id is omitted")
    loan_amount: Optional[Decimal] = Field(None, gt=0, description="Direct loan principal amount")
    
    down_payment: Decimal = Field(default=Decimal("0.00"), ge=0, description="Available down payment in INR")
    loan_tenure_months: int = Field(default=60, ge=12, le=120)
    tenure_months: Optional[int] = Field(None, ge=12, le=120)
    credit_score: Optional[int] = Field(default=750, ge=300, le=900)
    monthly_income: Optional[Decimal] = Field(None, ge=0)
    employment_type: Optional[str] = Field(default="SALARIED")
    applicant_age: Optional[int] = Field(default=30, ge=18, le=100)
    calculation_date: Optional[datetime] = Field(None, description="Calculation date")

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "tenure_months" in data and "loan_tenure_months" not in data:
                data["loan_tenure_months"] = data["tenure_months"]
            if "loan_amount" in data and "on_road_price" not in data and "vehicle_variant_id" not in data:
                dp = Decimal(str(data.get("down_payment", "0.00")))
                data["on_road_price"] = Decimal(str(data["loan_amount"])) + dp
        return data


class BankComparisonResponse(BaseModel):
    variant_id: Optional[int] = None
    variant_name: Optional[str] = None
    model_name: Optional[str] = None
    manufacturer_name: Optional[str] = None
    on_road_price: Decimal
    down_payment: Decimal
    loan_amount: Decimal
    tenure_months: int
    credit_score_used: int
    calculation_date: datetime
    
    offers: List[LoanOfferItem]
    total_offers_count: int
    eligible_offers_count: int
    data_quality: Dict[str, Any] = {
        "is_estimated": True,
        "data_status": "DEMO",
        "disclaimer": "Financing terms are based on demonstration bank products and do not constitute an official loan sanction.",
    }


# =============================================================================
# 4. LEGACY ELIGIBILITY SCHEMAS (Backwards Compatibility)
# =============================================================================

class LoanEligibilityRequest(BaseModel):
    monthly_take_home_income: Decimal = Field(gt=0, description="Net monthly income in INR")
    existing_monthly_emis: Decimal = Field(default=Decimal("0.00"), ge=0, description="Existing ongoing EMIs")
    tenure_months: int = Field(default=60, ge=12, le=120)
    cibil_score: Optional[int] = Field(default=750, ge=300, le=900)
    foir_limit_percent: Optional[Decimal] = Field(default=Decimal("40.0"), ge=10, le=70, description="FOIR / DTI limit %")
    annual_interest_rate: Optional[Decimal] = None


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
