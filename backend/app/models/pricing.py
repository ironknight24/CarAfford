from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableMixin, Base, TimestampMixin, utc_now


class ExShowroomPrice(Base, TimestampMixin, AuditableMixin):
    """Ex-showroom price for a variant in a specific state/city."""
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
    """Audit log of vehicle price changes over time."""
    __tablename__ = "price_histories"

    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"), nullable=False, index=True)
    state_id: Mapped[Optional[int]] = mapped_column(ForeignKey("states.id", ondelete="CASCADE"), nullable=True, index=True)
    price_inr: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    change_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
