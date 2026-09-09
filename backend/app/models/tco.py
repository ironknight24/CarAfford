from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class FuelPrice(Base, TimestampMixin):
    """Authoritative and observed retail fuel prices by state/city and fuel type."""
    __tablename__ = "fuel_prices"

    fuel_type: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # PETROL, DIESEL, CNG
    state_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("states.id"), nullable=True, index=True)
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    city_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("cities.id"), nullable=True, index=True)
    city_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit: Mapped[str] = mapped_column(String(20), default="Litre", nullable=False)  # Litre, kg
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    
    observed_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    source_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("data_sources.id"), nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source_record_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(50), default="DEMO", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    state = relationship("State", foreign_keys=[state_id], lazy="select")
    city = relationship("City", foreign_keys=[city_id], lazy="select")
    data_source = relationship("DataSource", foreign_keys=[source_id], lazy="select")


class ElectricityTariff(Base, TimestampMixin):
    """Authoritative and benchmark electricity tariffs for domestic EV home charging and commercial rates."""
    __tablename__ = "electricity_tariffs"

    tariff_type: Mapped[str] = mapped_column(String(50), default="DOMESTIC_SLAB", nullable=False)  # DOMESTIC_SLAB, EV_SPECIAL_TARIFF, COMMERCIAL
    state_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("states.id"), nullable=True, index=True)
    state_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)
    discom_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    
    rate_per_kwh: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    fixed_charge_per_month: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(10), default="INR", nullable=False)
    
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    source_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("data_sources.id"), nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(50), default="DEMO", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    state = relationship("State", foreign_keys=[state_id], lazy="select")
    data_source = relationship("DataSource", foreign_keys=[source_id], lazy="select")


class MaintenanceCostBenchmark(Base, TimestampMixin):
    """Scheduled and consumable maintenance benchmarks per powertrain and vehicle segment."""
    __tablename__ = "maintenance_cost_benchmarks"

    powertrain: Mapped[str] = mapped_column(String(50), index=True, nullable=False)  # PETROL, DIESEL, CNG, ELECTRIC, HYBRID
    segment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)  # HATCHBACK, SEDAN, SUV, LUXURY
    manufacturer_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("manufacturers.id"), nullable=True)
    model_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("car_models.id"), nullable=True)
    
    annual_base_cost: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    cost_per_km: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    service_interval_km: Mapped[int] = mapped_column(Integer, default=10000, nullable=False)
    service_interval_months: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    source_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("data_sources.id"), nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(50), default="DEMO", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    data_source = relationship("DataSource", foreign_keys=[source_id], lazy="select")


class InsuranceRenewalBenchmark(Base, TimestampMixin):
    """Empirical annual insurance renewal factors relative to Year 1 total premium."""
    __tablename__ = "insurance_renewal_benchmarks"

    fuel_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    segment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    
    year_2_factor: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    year_3_factor: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    year_4_factor: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    year_5_factor: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    source_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("data_sources.id"), nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(50), default="DEMO", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    data_source = relationship("DataSource", foreign_keys=[source_id], lazy="select")


class DepreciationBenchmark(Base, TimestampMixin):
    """Empirical cumulative depreciation schedules on vehicle Ex-Showroom price for economic cost estimation."""
    __tablename__ = "depreciation_benchmarks"

    powertrain: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    segment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    
    year_1_depreciation_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    year_2_depreciation_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    year_3_depreciation_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    year_4_depreciation_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    year_5_depreciation_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    
    methodology: Mapped[str] = mapped_column(String(100), default="EMPIRICAL_MARKET_RESALE", nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    source_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("data_sources.id"), nullable=True)
    source_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(50), default="DEMO", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    data_source = relationship("DataSource", foreign_keys=[source_id], lazy="select")
