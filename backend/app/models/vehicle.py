from decimal import Decimal
from typing import List, Optional
from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableMixin, Base, TimestampMixin


class Manufacturer(Base, TimestampMixin, AuditableMixin):
    """Car manufacturers / OEMs (e.g. Maruti Suzuki, Tata Motors, Hyundai, Mahindra)."""
    __tablename__ = "manufacturers"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    country_of_origin: Mapped[str] = mapped_column(String(50), default="India", nullable=False)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    models: Mapped[List["CarModel"]] = relationship("CarModel", back_populates="manufacturer", cascade="all, delete-orphan")


class CarModel(Base, TimestampMixin, AuditableMixin):
    """Car models (e.g. Nexon, Brezza, Creta, Thar, Punch, City)."""
    __tablename__ = "car_models"

    manufacturer_id: Mapped[int] = mapped_column(ForeignKey("manufacturers.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    body_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # SUV, Hatchback, Sedan, Compact SUV, MUV, EV
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    launch_year: Mapped[int] = mapped_column(Integer, default=2024, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_discontinued: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    manufacturer: Mapped["Manufacturer"] = relationship("Manufacturer", back_populates="models")
    variants: Mapped[List["Variant"]] = relationship("Variant", back_populates="model", cascade="all, delete-orphan")


class Variant(Base, TimestampMixin, AuditableMixin):
    """Specific variant of a car model (e.g. Tata Nexon Creative Plus 1.2 Petrol AMT)."""
    __tablename__ = "variants"

    model_id: Mapped[int] = mapped_column(ForeignKey("car_models.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    trim_level: Mapped[str] = mapped_column(String(50), default="Base", nullable=False)  # Base, Mid, Top, Top+
    fuel_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # Petrol, Diesel, CNG, Electric, Hybrid
    transmission: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # Manual, Automatic, AMT, CVT, DCT
    seating_capacity: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    model: Mapped["CarModel"] = relationship("CarModel", back_populates="variants")
    specification: Mapped[Optional["VariantSpecification"]] = relationship(
        "VariantSpecification", back_populates="variant", uselist=False, cascade="all, delete-orphan"
    )
    ex_showroom_prices: Mapped[List["ExShowroomPrice"]] = relationship(
        "ExShowroomPrice", back_populates="variant", cascade="all, delete-orphan"
    )


class VariantSpecification(Base, TimestampMixin, AuditableMixin):
    """Detailed technical specifications for a vehicle variant."""
    __tablename__ = "variant_specifications"

    variant_id: Mapped[int] = mapped_column(ForeignKey("variants.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    engine_displacement_cc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 1199 cc
    battery_capacity_kwh: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)  # e.g. 40.5 kWh
    max_power_bhp: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    max_torque_nm: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    arai_mileage_kmpl: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("18.00"), nullable=False)  # km/l or km/kg or km/kWh
    fuel_tank_capacity_l: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    boot_space_l: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    airbags_count: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    safety_rating_stars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1 to 5 stars (Bharat/Global NCAP)
    ground_clearance_mm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    variant: Mapped["Variant"] = relationship("Variant", back_populates="specification")
