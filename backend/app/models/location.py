from decimal import Decimal
from typing import List, Optional
from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableMixin, Base, TimestampMixin


class State(Base, TimestampMixin):
    """Indian States and Union Territories."""
    __tablename__ = "states"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False, index=True)  # DL, MH, KA, TN etc.
    is_ut: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    cities: Mapped[List["City"]] = relationship("City", back_populates="state", cascade="all, delete-orphan")
    rtos: Mapped[List["RtoOffice"]] = relationship("RtoOffice", back_populates="state", cascade="all, delete-orphan")
    tax_slabs: Mapped[List["TaxSlab"]] = relationship("TaxSlab", back_populates="state", cascade="all, delete-orphan")


class City(Base, TimestampMixin):
    """Major Indian Cities."""
    __tablename__ = "cities"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    state_id: Mapped[int] = mapped_column(ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(String(10), default="Tier 1", nullable=False)  # Tier 1, Tier 2, Tier 3

    state: Mapped["State"] = relationship("State", back_populates="cities")
    rtos: Mapped[List["RtoOffice"]] = relationship("RtoOffice", back_populates="city", cascade="all, delete-orphan")


class RtoOffice(Base, TimestampMixin):
    """RTO (Regional Transport Office) records."""
    __tablename__ = "rto_offices"

    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)  # e.g., MH-01, DL-01, KA-01
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    state_id: Mapped[int] = mapped_column(ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True)
    city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cities.id", ondelete="SET NULL"), nullable=True, index=True)

    state: Mapped["State"] = relationship("State", back_populates="rtos")
    city: Mapped[Optional["City"]] = relationship("City", back_populates="rtos")


class TaxSlab(Base, TimestampMixin, AuditableMixin):
    """State/RTO Motor Vehicle Road Tax slabs based on fuel, price, and engine capacity."""
    __tablename__ = "tax_slabs"

    state_id: Mapped[int] = mapped_column(ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True)
    fuel_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # Petrol, Diesel, CNG, Electric, Hybrid
    min_ex_showroom: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    max_ex_showroom: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)  # Null means no upper cap
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)  # e.g. 10.00%
    cess_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0.00"), nullable=False)  # e.g. 10% on tax
    flat_registration_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("600.00"), nullable=False)
    fastag_fee: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("600.00"), nullable=False)
    green_cess_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0.00"), nullable=False)
    is_bh_series: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    state: Mapped["State"] = relationship("State", back_populates="tax_slabs")
