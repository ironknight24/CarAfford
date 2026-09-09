from app.schemas.common import BaseResponse, PaginatedResponse, AuditSchemaMixin
from app.schemas.data_source import DataSourceRead, DataSourceCreate
from app.schemas.location import StateRead, CityRead, RtoOfficeRead, TaxSlabRead
from app.schemas.vehicle import (
    ManufacturerRead,
    CarModelRead,
    VariantRead,
    VariantSpecificationRead,
    VehicleFilterParams,
)
from app.schemas.pricing import (
    ExShowroomPriceRead,
    PriceHistoryRead,
    OnRoadPriceRequest,
    OnRoadPriceBreakdown,
)
from app.schemas.finance import (
    BankRead,
    LoanProductRead,
    InterestRateSlabRead,
    EmiCalculationRequest,
    EmiCalculationResponse,
    LoanEligibilityRequest,
    LoanEligibilityResponse,
    AmortizationScheduleItem,
)
from app.schemas.affordability import (
    AffordabilityAnalysisRequest,
    AffordabilityBudgetSummary,
    AffordabilityCategory,
    OwnershipCostBreakdown,
)
from app.schemas.recommendation import (
    RecommendedVehicleItem,
    RecommendationResponse,
)

__all__ = [
    "BaseResponse",
    "PaginatedResponse",
    "AuditSchemaMixin",
    "DataSourceRead",
    "DataSourceCreate",
    "StateRead",
    "CityRead",
    "RtoOfficeRead",
    "TaxSlabRead",
    "ManufacturerRead",
    "CarModelRead",
    "VariantRead",
    "VariantSpecificationRead",
    "VehicleFilterParams",
    "ExShowroomPriceRead",
    "PriceHistoryRead",
    "OnRoadPriceRequest",
    "OnRoadPriceBreakdown",
    "BankRead",
    "LoanProductRead",
    "InterestRateSlabRead",
    "EmiCalculationRequest",
    "EmiCalculationResponse",
    "LoanEligibilityRequest",
    "LoanEligibilityResponse",
    "AmortizationScheduleItem",
    "AffordabilityAnalysisRequest",
    "AffordabilityBudgetSummary",
    "AffordabilityCategory",
    "OwnershipCostBreakdown",
    "RecommendedVehicleItem",
    "RecommendationResponse",
]
