from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableMixin, Base, TimestampMixin, utc_now


class Bank(Base, TimestampMixin):
    """Indian commercial banks and NBFCs offering auto loans (e.g. SBI, HDFC, ICICI, Axis, PNB, Kotak)."""
    __tablename__ = "banks"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    bank_type: Mapped[str] = mapped_column(String(50), default="Public", nullable=False)  # Public, Private, NBFC
    website_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )
    verification_status: Mapped[str] = mapped_column(String(50), default="DEMO", nullable=False, index=True)

    # Relationships
    loan_products: Mapped[List["LoanProduct"]] = relationship(
        "LoanProduct", back_populates="bank", cascade="all, delete-orphan", order_by="LoanProduct.name"
    )
    source: Mapped[Optional["DataSource"]] = relationship("DataSource")

    # Backward compatibility
    @property
    def is_active(self) -> bool:
        return self.active

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.active = value


class LoanProduct(Base, TimestampMixin):
    """Specific auto-loan scheme offered by a bank (e.g. SBI Car Loan, SBI Green Car Loan, HDFC CustomFit)."""
    __tablename__ = "loan_products"

    bank_id: Mapped[int] = mapped_column(ForeignKey("banks.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    
    vehicle_type: Mapped[str] = mapped_column(String(50), default="CAR", nullable=False)  # CAR, TWO_WHEELER, COMMERCIAL, ANY
    vehicle_condition: Mapped[str] = mapped_column(String(50), default="NEW", nullable=False)  # NEW, USED, ANY
    product_category: Mapped[str] = mapped_column(String(50), default="STANDARD", nullable=False)  # STANDARD, EV_GREEN, PRE_OWNED, PROMOTIONAL
    
    min_loan_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("100000.00"), nullable=False)
    max_loan_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("10000000.00"), nullable=False)
    min_tenure_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    max_tenure_months: Mapped[int] = mapped_column(Integer, default=84, nullable=False)  # up to 7 years
    max_ltv_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("90.00"), nullable=False)  # Up to 90% on-road
    
    # Default fee structure indicators
    processing_fee_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.50"), nullable=False)
    min_processing_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1500.00"), nullable=False)
    max_processing_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("10000.00"), nullable=False)
    
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Data Source Provenance
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )
    verification_status: Mapped[str] = mapped_column(String(50), default="DEMO", nullable=False, index=True)

    # Relationships
    bank: Mapped["Bank"] = relationship("Bank", back_populates="loan_products")
    source: Mapped[Optional["DataSource"]] = relationship("DataSource")
    interest_rates: Mapped[List["InterestRate"]] = relationship(
        "InterestRate", back_populates="loan_product", cascade="all, delete-orphan", order_by="InterestRate.priority.desc()"
    )
    eligibility_rules: Mapped[List["LoanEligibilityRule"]] = relationship(
        "LoanEligibilityRule", back_populates="loan_product", cascade="all, delete-orphan"
    )
    fees: Mapped[List["LoanFee"]] = relationship(
        "LoanFee", back_populates="loan_product", cascade="all, delete-orphan"
    )
    interest_rate_slabs: Mapped[List["InterestRateSlab"]] = relationship(
        "InterestRateSlab", back_populates="loan_product", cascade="all, delete-orphan"
    )

    # Backward compatibility
    @property
    def is_active(self) -> bool:
        return self.active

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.active = value


class InterestRate(Base, TimestampMixin):
    """Historical and currently effective interest rate schedule for loan products."""
    __tablename__ = "interest_rates"
    __table_args__ = (
        CheckConstraint("annual_interest_rate >= 0", name="chk_interest_rates_rate_non_negative"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="chk_interest_rates_period_valid"),
        CheckConstraint("min_credit_score IS NULL OR max_credit_score IS NULL OR max_credit_score >= min_credit_score", name="chk_interest_rates_cibil_range"),
        CheckConstraint("min_tenure_months IS NULL OR max_tenure_months IS NULL OR max_tenure_months >= min_tenure_months", name="chk_interest_rates_tenure_range"),
        CheckConstraint("min_loan_amount IS NULL OR max_loan_amount IS NULL OR max_loan_amount >= min_loan_amount", name="chk_interest_rates_amount_range"),
        Index("ix_interest_rates_resolution", "loan_product_id", "active", "effective_from", "effective_to"),
    )

    loan_product_id: Mapped[int] = mapped_column(
        ForeignKey("loan_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    annual_interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # e.g. 8.75%
    rate_type: Mapped[str] = mapped_column(String(30), default="FLOATING", nullable=False)  # FIXED, FLOATING, VARIABLE
    
    # Optional tier matching criteria
    min_credit_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 750
    max_credit_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 900
    min_tenure_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 12
    max_tenure_months: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 60
    min_loan_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    max_loan_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    employment_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # SALARIED, SELF_EMPLOYED, ANY
    
    # Priority & Temporal Validity
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False, index=True)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Data Source Provenance
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )
    verification_status: Mapped[str] = mapped_column(String(50), default="DEMO", nullable=False, index=True)

    # Relationships
    loan_product: Mapped["LoanProduct"] = relationship("LoanProduct", back_populates="interest_rates")
    source: Mapped[Optional["DataSource"]] = relationship("DataSource")

    # Backward compatibility
    @property
    def is_active(self) -> bool:
        return self.active

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.active = value


class LoanEligibilityRule(Base, TimestampMixin):
    """Underwriting and pre-qualification criteria for a loan product."""
    __tablename__ = "loan_eligibility_rules"
    __table_args__ = (
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="chk_eligibility_rules_period_valid"),
    )

    loan_product_id: Mapped[int] = mapped_column(
        ForeignKey("loan_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    rule_name: Mapped[str] = mapped_column(String(150), nullable=False)
    
    min_monthly_income: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)  # e.g. 25,000 INR
    min_credit_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 650
    max_credit_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_loan_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    max_ltv_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)  # e.g. 90.00
    max_foir_percent: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), default=Decimal("50.00"), nullable=True)  # FOIR / DTI cap %
    
    min_age_years: Mapped[Optional[int]] = mapped_column(Integer, default=21, nullable=True)
    max_age_years: Mapped[Optional[int]] = mapped_column(Integer, default=65, nullable=True)
    min_employment_months: Mapped[Optional[int]] = mapped_column(Integer, default=12, nullable=True)
    allowed_employment_types: Mapped[Optional[str]] = mapped_column(String(150), default="SALARIED,SELF_EMPLOYED", nullable=True)
    allowed_residency_types: Mapped[Optional[str]] = mapped_column(String(150), default="RESIDENT_INDIAN,NRI", nullable=True)

    # Temporal Validity
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Provenance
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )
    verification_status: Mapped[str] = mapped_column(String(50), default="DEMO", nullable=False, index=True)

    # Relationships
    loan_product: Mapped["LoanProduct"] = relationship("LoanProduct", back_populates="eligibility_rules")
    source: Mapped[Optional["DataSource"]] = relationship("DataSource")


class LoanFee(Base, TimestampMixin):
    """Specific fees and charges associated with auto loan processing."""
    __tablename__ = "loan_fees"
    __table_args__ = (
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="chk_loan_fees_period_valid"),
    )

    loan_product_id: Mapped[int] = mapped_column(
        ForeignKey("loan_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fee_name: Mapped[str] = mapped_column(String(150), nullable=False)
    fee_type: Mapped[str] = mapped_column(
        String(50), default="PROCESSING_FEE", nullable=False, index=True
    )  # PROCESSING_FEE, DOCUMENTATION_FEE, VALUATION_FEE, FORECLOSURE_CHARGE, STAMP_DUTY, OTHER
    
    calculation_method: Mapped[str] = mapped_column(
        String(30), default="PERCENTAGE", nullable=False
    )  # FIXED, PERCENTAGE, CAPPED_PERCENTAGE, WAIVED
    
    fixed_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)  # e.g. 0.50 for 0.5%
    minimum_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)  # e.g. 1500.00
    maximum_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)  # e.g. 10000.00

    # Temporal Validity
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Provenance
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )
    verification_status: Mapped[str] = mapped_column(String(50), default="DEMO", nullable=False, index=True)

    # Relationships
    loan_product: Mapped["LoanProduct"] = relationship("LoanProduct", back_populates="fees")
    source: Mapped[Optional["DataSource"]] = relationship("DataSource")


class InterestRateSlab(Base, TimestampMixin, AuditableMixin):
    """Legacy interest rate tiers linked to CIBIL credit score bands (preserved for backwards compatibility)."""
    __tablename__ = "interest_rate_slabs"

    loan_product_id: Mapped[int] = mapped_column(
        ForeignKey("loan_products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    min_cibil_score: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    max_cibil_score: Mapped[int] = mapped_column(Integer, default=900, nullable=False)
    min_interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # e.g. 8.70%
    max_interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # e.g. 9.10%
    default_interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # e.g. 8.75%
    is_fixed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Floating vs Fixed

    loan_product: Mapped["LoanProduct"] = relationship("LoanProduct", back_populates="interest_rate_slabs")


# Ensure DataSource import is available for type annotations and relationships
from app.models.data_source import DataSource  # noqa: E402
