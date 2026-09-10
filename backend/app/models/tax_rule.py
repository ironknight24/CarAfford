from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableMixin, Base, TimestampMixin, utc_now


class TaxRule(Base, TimestampMixin):
    """Statutory vehicle taxation and registration charge rule with temporal and location scoping."""

    __tablename__ = "tax_rules"
    __table_args__ = (
        CheckConstraint("priority >= 0", name="chk_tax_rules_priority_non_negative"),
        CheckConstraint("rate IS NULL OR rate >= 0", name="chk_tax_rules_rate_non_negative"),
        CheckConstraint(
            "fixed_amount IS NULL OR fixed_amount >= 0",
            name="chk_tax_rules_fixed_amount_non_negative",
        ),
        CheckConstraint(
            "effective_to IS NULL OR effective_to >= effective_from",
            name="chk_tax_rules_effective_period_valid",
        ),
        CheckConstraint(
            "min_price IS NULL OR max_price IS NULL OR max_price >= min_price",
            name="chk_tax_rules_price_range_valid",
        ),
        CheckConstraint(
            "min_engine_cc IS NULL OR max_engine_cc IS NULL OR max_engine_cc >= min_engine_cc",
            name="chk_tax_rules_engine_cc_range_valid",
        ),
        Index("ix_tax_rules_state_tax_type", "state_id", "tax_type"),
        Index("ix_tax_rules_effective_dates", "effective_from", "effective_to"),
        Index("ix_tax_rules_resolution_lookup", "state_id", "city_id", "rto_id", "active"),
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Location Scoping (Hierarchical: RTO > City > State)
    state_id: Mapped[int] = mapped_column(
        ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True
    )
    city_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rto_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("rto_offices.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Classification
    rule_category: Mapped[str] = mapped_column(
        String(30), default="TAX", nullable=False, index=True
    )  # TAX, REGISTRATION, FEE, CESS
    tax_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # ROAD_TAX, MOTOR_VEHICLE_TAX, REGISTRATION_FEE, SMART_CARD_FEE, HSRP_FEE, HYPOTHECATION_FEE, CESS, SURCHARGE, GREEN_TAX, FASTAG_FEE, OTHER

    # Calculation Method
    calculation_method: Mapped[str] = mapped_column(
        String(30), default="PERCENTAGE", nullable=False, index=True
    )  # FIXED, PERCENTAGE, BRACKETED, FORMULA

    # Vehicle Eligibility Conditions
    vehicle_type: Mapped[str] = mapped_column(
        String(30), default="CAR", nullable=False, index=True
    )  # CAR, TWO_WHEELER, COMMERCIAL, ANY
    fuel_type: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True, index=True
    )  # Petrol, Diesel, CNG, Electric, Hybrid, ANY, null
    is_ev: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    usage_type: Mapped[str] = mapped_column(
        String(30), default="PRIVATE", nullable=False, index=True
    )  # PRIVATE, COMMERCIAL, ANY

    min_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    max_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    min_engine_cc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_engine_cc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    min_seating_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_seating_capacity: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Calculation Values (for FIXED and PERCENTAGE methods)
    rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4), nullable=True
    )  # e.g., 14.0000 for 14%
    fixed_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=True
    )  # e.g., ₹600.00
    base_amount_type: Mapped[str] = mapped_column(
        String(30), default="EX_SHOWROOM", nullable=False
    )  # EX_SHOWROOM, ROAD_TAX, BASE_TAX, FIXED, CUSTOM

    # Safe Structured Formula Definition (No arbitrary code execution, JSON parameter tree)
    formula_definition: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    # Precedence & Temporal Validity
    priority: Mapped[int] = mapped_column(Integer, default=100, nullable=False, index=True)
    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    effective_to: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Data Source / Provenance
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )
    verification_status: Mapped[str] = mapped_column(
        String(50), default="DEMO", nullable=False, index=True
    )

    # Relationships
    state: Mapped["State"] = relationship("State", backref="tax_rules")
    city: Mapped[Optional["City"]] = relationship("City")
    rto: Mapped[Optional["RtoOffice"]] = relationship("RtoOffice")
    source: Mapped[Optional["DataSource"]] = relationship("DataSource")
    brackets: Mapped[List["TaxRuleBracket"]] = relationship(
        "TaxRuleBracket",
        back_populates="tax_rule",
        cascade="all, delete-orphan",
        order_by="TaxRuleBracket.bracket_order, TaxRuleBracket.minimum_value",
    )


class TaxRuleBracket(Base, TimestampMixin):
    """Tiered slab bracket for bracketed vehicle tax or fee rules."""

    __tablename__ = "tax_rule_brackets"
    __table_args__ = (
        CheckConstraint("minimum_value >= 0", name="chk_tax_brackets_min_non_negative"),
        CheckConstraint(
            "maximum_value IS NULL OR maximum_value > minimum_value",
            name="chk_tax_brackets_max_greater_than_min",
        ),
        CheckConstraint("rate IS NULL OR rate >= 0", name="chk_tax_brackets_rate_non_negative"),
        CheckConstraint(
            "fixed_amount IS NULL OR fixed_amount >= 0",
            name="chk_tax_brackets_fixed_non_negative",
        ),
        Index("ix_tax_rule_brackets_rule_order", "tax_rule_id", "bracket_order"),
    )

    tax_rule_id: Mapped[int] = mapped_column(
        ForeignKey("tax_rules.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bracket_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    minimum_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    maximum_value: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )  # NULL indicates no upper bound (infinity)
    rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4), nullable=True
    )  # Percentage rate, e.g. 13.00 for 13%
    fixed_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=True
    )
    calculation_method: Mapped[str] = mapped_column(
        String(30), default="PERCENTAGE", nullable=False
    )  # PERCENTAGE, FIXED, FORMULA

    # Relationships
    tax_rule: Mapped["TaxRule"] = relationship("TaxRule", back_populates="brackets")


from app.models.data_source import DataSource  # noqa: E402
from app.models.location import City, RtoOffice, State  # noqa: E402
