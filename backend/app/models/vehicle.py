from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import AuditableMixin, Base, TimestampMixin, utc_now


class Manufacturer(Base, TimestampMixin, AuditableMixin):
    """Car manufacturers / OEMs (e.g. Maruti Suzuki, Tata Motors, Hyundai, Mahindra, Toyota)."""
    __tablename__ = "manufacturers"

    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    country: Mapped[str] = mapped_column(String(50), default="India", nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationship
    models: Mapped[List["CarModel"]] = relationship(
        "CarModel", back_populates="manufacturer", cascade="all, delete-orphan", order_by="CarModel.name"
    )

    # Aliases for backward compatibility
    @property
    def is_active(self) -> bool:
        return self.active

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.active = value

    @property
    def country_of_origin(self) -> str:
        return self.country

    @country_of_origin.setter
    def country_of_origin(self, value: str) -> None:
        self.country = value


class CarModel(Base, TimestampMixin, AuditableMixin):
    """Car models (e.g. Nexon, Brezza, Creta, Thar, Punch, City)."""
    __tablename__ = "car_models"
    __table_args__ = (
        UniqueConstraint("manufacturer_id", "name", name="uq_car_models_manufacturer_name"),
    )

    manufacturer_id: Mapped[int] = mapped_column(
        ForeignKey("manufacturers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    body_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # Hatchback, Sedan, SUV, MUV, Coupe
    segment: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)  # A-Segment, B-Segment, Compact SUV, etc.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    launch_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    discontinued_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    launch_year: Mapped[int] = mapped_column(Integer, default=2024, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Relationships
    manufacturer: Mapped["Manufacturer"] = relationship("Manufacturer", back_populates="models")
    variants: Mapped[List["Variant"]] = relationship(
        "Variant", back_populates="model", cascade="all, delete-orphan", order_by="Variant.name"
    )
    media: Mapped[List["VehicleMedia"]] = relationship(
        "VehicleMedia", back_populates="model", cascade="all, delete-orphan", foreign_keys="VehicleMedia.model_id"
    )

    # Aliases for backward compatibility
    @property
    def is_active(self) -> bool:
        return self.active

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.active = value

    @property
    def is_discontinued(self) -> bool:
        return self.discontinued_date is not None or not self.active


class Variant(Base, TimestampMixin, AuditableMixin):
    """Specific variant of a car model (e.g. Tata Nexon Smart 1.2 Petrol 5MT)."""
    __tablename__ = "variants"
    __table_args__ = (
        CheckConstraint("seating_capacity > 0", name="chk_variants_seating_capacity_positive"),
        CheckConstraint("engine_cc IS NULL OR engine_cc >= 0", name="chk_variants_engine_cc_positive"),
        CheckConstraint("battery_capacity_kwh IS NULL OR battery_capacity_kwh >= 0", name="chk_variants_battery_kwh_positive"),
    )

    model_id: Mapped[int] = mapped_column(
        ForeignKey("car_models.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False, index=True)
    trim_level: Mapped[str] = mapped_column(String(50), default="Base", nullable=False)
    fuel_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)  # Petrol, Diesel, CNG, Electric, Hybrid
    transmission: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # Manual, Automatic, AMT, CVT, DCT
    drivetrain: Mapped[Optional[str]] = mapped_column(String(20), default="FWD", nullable=True, index=True)  # FWD, RWD, AWD, 4WD
    
    # Engine specifications (NULL for pure Electric Vehicles)
    engine_cc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    engine_power_bhp: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    torque_nm: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    
    # Seating & Claimed Efficiency
    seating_capacity: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    mileage_claimed: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)  # ARAI km/l, km/kg, or km/kWh
    
    # Battery specifications (NULL for non-EVs)
    battery_capacity_kwh: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    range_km: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    model: Mapped["CarModel"] = relationship("CarModel", back_populates="variants")
    prices: Mapped[List["VehiclePrice"]] = relationship(
        "VehiclePrice", back_populates="variant", cascade="all, delete-orphan", order_by="VehiclePrice.effective_from.desc()"
    )
    media: Mapped[List["VehicleMedia"]] = relationship(
        "VehicleMedia", back_populates="variant", cascade="all, delete-orphan", foreign_keys="VehicleMedia.variant_id"
    )
    
    # Optional legacy specification relationship
    specification: Mapped[Optional["VariantSpecification"]] = relationship(
        "VariantSpecification", back_populates="variant", uselist=False, cascade="all, delete-orphan"
    )
    ex_showroom_prices: Mapped[List["ExShowroomPrice"]] = relationship(
        "ExShowroomPrice", back_populates="variant", cascade="all, delete-orphan"
    )

    # Backward compatibility helpers
    @property
    def is_active(self) -> bool:
        return self.active

    @is_active.setter
    def is_active(self, value: bool) -> None:
        self.active = value

    @property
    def arai_mileage_kmpl(self) -> Decimal:
        if self.mileage_claimed is not None:
            return self.mileage_claimed
        if self.specification and self.specification.arai_mileage_kmpl is not None:
            return self.specification.arai_mileage_kmpl
        return Decimal("18.00")


class VariantSpecification(Base, TimestampMixin, AuditableMixin):
    """Detailed technical specifications for a vehicle variant (backward compatibility & extra specs)."""
    __tablename__ = "variant_specifications"

    variant_id: Mapped[int] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    engine_displacement_cc: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    battery_capacity_kwh: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    max_power_bhp: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    max_torque_nm: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    arai_mileage_kmpl: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("18.00"), nullable=False)
    fuel_tank_capacity_l: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    boot_space_l: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    airbags_count: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    safety_rating_stars: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ground_clearance_mm: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    variant: Mapped["Variant"] = relationship("Variant", back_populates="specification")


class VehicleMedia(Base):
    """Vehicle images, brochures, and media references."""
    __tablename__ = "vehicle_media"
    __table_args__ = (
        CheckConstraint("variant_id IS NOT NULL OR model_id IS NOT NULL", name="chk_vehicle_media_target_not_null"),
    )

    variant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("variants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    model_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("car_models.id", ondelete="CASCADE"), nullable=True, index=True
    )
    media_type: Mapped[str] = mapped_column(String(50), default="IMAGE_EXTERIOR", nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(1024), nullable=False)
    alt_text: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )

    variant: Mapped[Optional["Variant"]] = relationship("Variant", back_populates="media", foreign_keys=[variant_id])
    model: Mapped[Optional["CarModel"]] = relationship("CarModel", back_populates="media", foreign_keys=[model_id])


# Import VehiclePrice here to resolve circular relationships cleanly
from app.models.pricing import VehiclePrice, ExShowroomPrice  # noqa: E402
