from decimal import Decimal
from typing import List, Optional
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableMixin, Base, TimestampMixin


class Bank(Base, TimestampMixin, AuditableMixin):
    """Indian banks offering auto loans (e.g. SBI, HDFC, ICICI, Axis, PNB)."""
    __tablename__ = "banks"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    bank_type: Mapped[str] = mapped_column(String(50), default="Public", nullable=False)  # Public, Private, NBFC
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    loan_products: Mapped[List["LoanProduct"]] = relationship("LoanProduct", back_populates="bank", cascade="all, delete-orphan")


class LoanProduct(Base, TimestampMixin, AuditableMixin):
    """Specific auto-loan scheme offered by a bank."""
    __tablename__ = "loan_products"

    bank_id: Mapped[int] = mapped_column(ForeignKey("banks.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slug: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    min_loan_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("100000.00"), nullable=False)
    max_loan_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("10000000.00"), nullable=False)
    min_tenure_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    max_tenure_months: Mapped[int] = mapped_column(Integer, default=84, nullable=False)  # up to 7 years
    max_ltv_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("90.00"), nullable=False)  # Up to 90% on-road
    processing_fee_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.50"), nullable=False)
    min_processing_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("1500.00"), nullable=False)
    max_processing_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("10000.00"), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    bank: Mapped["Bank"] = relationship("Bank", back_populates="loan_products")
    interest_rate_slabs: Mapped[List["InterestRateSlab"]] = relationship(
        "InterestRateSlab", back_populates="loan_product", cascade="all, delete-orphan"
    )


class InterestRateSlab(Base, TimestampMixin, AuditableMixin):
    """Interest rate tiers linked to CIBIL credit score bands."""
    __tablename__ = "interest_rate_slabs"

    loan_product_id: Mapped[int] = mapped_column(ForeignKey("loan_products.id", ondelete="CASCADE"), nullable=False, index=True)
    min_cibil_score: Mapped[int] = mapped_column(Integer, default=300, nullable=False)
    max_cibil_score: Mapped[int] = mapped_column(Integer, default=900, nullable=False)
    min_interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # e.g. 8.70%
    max_interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # e.g. 9.10%
    default_interest_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # e.g. 8.75%
    is_fixed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Floating vs Fixed

    loan_product: Mapped["LoanProduct"] = relationship("LoanProduct", back_populates="interest_rate_slabs")
