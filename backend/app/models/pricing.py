from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableMixin, Base, TimestampMixin, utc_now


class VehiclePrice(Base):
    """Historical and currently effective ex-showroom pricing for vehicle variants."""
    __tablename__ = "vehicle_prices"
    __table_args__ = (
        CheckConstraint("ex_showroom_price > 0", name="chk_vehicle_prices_amount_positive"),
        CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="chk_vehicle_prices_period_valid"),
    )

    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ex_showroom_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    price_type: Mapped[str] = mapped_column(
        String(30), default="EX_SHOWROOM", nullable=False, index=True
    )  # EX_SHOWROOM, INTRODUCTORY, PROMOTIONAL, OTHER
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )  # NULL indicates currently active price
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )
    verification_status: Mapped[str] = mapped_column(String(50), default="DEMO", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    # Relationships
    variant: Mapped["Variant"] = relationship("Variant", back_populates="prices")
    source: Mapped[Optional["DataSource"]] = relationship("DataSource")


class ExShowroomPrice(Base, TimestampMixin, AuditableMixin):
    """Legacy/location-specific ex-showroom price mapping."""
    __tablename__ = "ex_showroom_prices"

    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"), nullable=False, index=True)
    state_id: Mapped[Optional[int]] = mapped_column(ForeignKey("states.id", ondelete="CASCADE"), nullable=True, index=True)
    city_id: Mapped[Optional[int]] = mapped_column(ForeignKey("cities.id", ondelete="SET NULL"), nullable=True, index=True)
    price_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    variant: Mapped["Variant"] = relationship("Variant", back_populates="ex_showroom_prices")
    state: Mapped[Optional["State"]] = relationship("State")
    city: Mapped[Optional["City"]] = relationship("City")


class PriceHistory(Base, TimestampMixin):
    """Audit log of price modifications."""
    __tablename__ = "price_histories"

    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"), nullable=False, index=True)
    state_id: Mapped[Optional[int]] = mapped_column(ForeignKey("states.id", ondelete="CASCADE"), nullable=True, index=True)
    price_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)


from app.models.data_source import DataSource  # noqa: E402
from app.models.location import State, City  # noqa: E402
