from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, utc_now
from app.core.ingestion_constants import DataSourceType


class DataSource(Base, TimestampMixin):
    """Catalog of external data sources (e.g. Parivahan, IRDAI, RBI/SBI, SIAM)."""

    __tablename__ = "data_sources"

    name: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(
        String(50), default=DataSourceType.DEMO_SEED.value, nullable=False, index=True
    )
    provider_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # government, bank, oem, aggregator
    organization: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    base_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    licensing_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    terms_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    trust_level: Mapped[int] = mapped_column(Integer, default=70, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    @property
    def active(self) -> bool:
        return self.is_active

    @active.setter
    def active(self, value: bool) -> None:
        self.is_active = value
