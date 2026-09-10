from decimal import Decimal
from typing import Optional
from sqlalchemy import Boolean, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import AuditableMixin, Base, TimestampMixin


class InsuranceRateRule(Base, TimestampMixin, AuditableMixin):
    """IRDAI-benchmarked car insurance tariff rules by engine cc / EV power."""

    __tablename__ = "insurance_rate_rules"

    min_engine_cc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_engine_cc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_ev: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    third_party_3yr_tariff_inr: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False
    )  # 3-year mandatory TP cover
    own_damage_base_rate_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("2.80"), nullable=False
    )  # % of IDV
    zero_dep_addon_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.70"), nullable=False
    )  # % of IDV
    engine_protect_addon_inr: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("1500.00"), nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
