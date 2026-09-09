from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, utc_now


class DataSource(Base, TimestampMixin):
    """Catalog of external data sources (e.g. Parivahan, IRDAI, RBI/SBI, SIAM)."""
    __tablename__ = "data_sources"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    provider_type: Mapped[str] = mapped_column(String(100), nullable=False)  # government, bank, oem, aggregator
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
