from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableMixin, Base, TimestampMixin, utc_now


class Country(Base, TimestampMixin):
    """Sovereign nation entities for geographical and regulatory partitioning."""
    __tablename__ = "countries"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    iso_code: Mapped[str] = mapped_column(String(2), unique=True, nullable=False, index=True)  # e.g., IN, US
    iso3_code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False, index=True)  # e.g., IND, USA
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    states: Mapped[List["State"]] = relationship(
        "State", back_populates="country", cascade="all, delete-orphan", order_by="State.name"
    )


class State(Base, TimestampMixin):
    """First-level administrative divisions (States, Union Territories, Provinces)."""
    __tablename__ = "states"
    __table_args__ = (
        UniqueConstraint("country_id", "code", name="uq_states_country_code"),
        UniqueConstraint("country_id", "name", name="uq_states_country_name"),
    )

    country_id: Mapped[int] = mapped_column(
        ForeignKey("countries.id", ondelete="CASCADE"), default=1, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)  # e.g., DL, MH, KA, TN
    region_type: Mapped[str] = mapped_column(
        String(30), default="STATE", nullable=False, index=True
    )  # STATE, UNION_TERRITORY
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Data Source / Provenance
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )

    # Relationships
    country: Mapped["Country"] = relationship("Country", back_populates="states")
    cities: Mapped[List["City"]] = relationship(
        "City", back_populates="state", cascade="all, delete-orphan", order_by="City.name"
    )
    rtos: Mapped[List["RtoOffice"]] = relationship(
        "RtoOffice", back_populates="state", cascade="all, delete-orphan", order_by="RtoOffice.code"
    )
    tax_slabs: Mapped[List["TaxSlab"]] = relationship(
        "TaxSlab", back_populates="state", cascade="all, delete-orphan"
    )
    source: Mapped[Optional["DataSource"]] = relationship("DataSource")

    @property
    def is_ut(self) -> bool:
        return self.region_type == "UNION_TERRITORY"

    @is_ut.setter
    def is_ut(self, value: bool) -> None:
        self.region_type = "UNION_TERRITORY" if value else "STATE"


class City(Base, TimestampMixin):
    """Major urban municipal areas and district centers."""
    __tablename__ = "cities"
    __table_args__ = (
        UniqueConstraint("state_id", "name", name="uq_cities_state_name"),
        UniqueConstraint("state_id", "slug", name="uq_cities_state_slug"),
    )

    state_id: Mapped[int] = mapped_column(
        ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    tier: Mapped[str] = mapped_column(
        String(10), default="Tier 1", nullable=False
    )  # Tier 1, Tier 2, Tier 3
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Data Source / Provenance
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )

    # Relationships
    state: Mapped["State"] = relationship("State", back_populates="cities")
    rtos: Mapped[List["RtoOffice"]] = relationship(
        "RtoOffice", back_populates="city", order_by="RtoOffice.code"
    )
    source: Mapped[Optional["DataSource"]] = relationship("DataSource")


class RtoOffice(Base, TimestampMixin):
    """Regional Transport Office (RTO) jurisdictions responsible for vehicle registration & taxation."""
    __tablename__ = "rto_offices"
    __table_args__ = (
        UniqueConstraint("state_id", "code", name="uq_rto_offices_state_code"),
    )

    state_id: Mapped[int] = mapped_column(
        ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True
    )
    city_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("cities.id", ondelete="SET NULL"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(
        String(20), nullable=False, index=True
    )  # e.g., MH-01, DL-01, KA-01, KA-53
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    jurisdiction: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Structured or descriptive boundaries
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Data Source / Provenance
    source_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    retrieved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=True
    )

    # Relationships
    state: Mapped["State"] = relationship("State", back_populates="rtos")
    city: Mapped[Optional["City"]] = relationship("City", back_populates="rtos")
    source: Mapped[Optional["DataSource"]] = relationship("DataSource")


# Model alias for convenience
RTO = RtoOffice


class TaxSlab(Base, TimestampMixin, AuditableMixin):
    """State/RTO Motor Vehicle Road Tax slabs based on fuel, price, and engine capacity."""
    __tablename__ = "tax_slabs"

    state_id: Mapped[int] = mapped_column(
        ForeignKey("states.id", ondelete="CASCADE"), nullable=False, index=True
    )
    fuel_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # Petrol, Diesel, CNG, Electric, Hybrid
    min_ex_showroom: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), default=Decimal("0.00"), nullable=False
    )
    max_ex_showroom: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 2), nullable=True
    )  # Null means no upper cap
    tax_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False
    )  # e.g. 10.00%
    cess_percent: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0.00"), nullable=False
    )  # e.g. 10% on tax
    flat_registration_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("600.00"), nullable=False
    )
    fastag_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("600.00"), nullable=False
    )
    green_cess_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0.00"), nullable=False
    )
    is_bh_series: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    state: Mapped["State"] = relationship("State", back_populates="tax_slabs")


from app.models.data_source import DataSource  # noqa: E402
