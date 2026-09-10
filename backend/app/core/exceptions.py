from typing import Any, Optional


class CarAffordException(Exception):
    """Base exception for all CarAfford domain and application errors."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(message)
        self.message = message
        self.details = details


class ResourceNotFoundException(CarAffordException):
    """Raised when a requested resource is not found."""

    pass


class InvalidFinancialInputException(CarAffordException):
    """Raised when input financial parameters (income, EMI, rate) are invalid or mathematically impossible."""

    pass


class TaxCalculationException(CarAffordException):
    """Raised when tax slab rules cannot be applied or are missing."""

    pass


class LoanIneligibleException(CarAffordException):
    """Raised when loan parameters violate banking policies or negative disposable income."""

    pass
