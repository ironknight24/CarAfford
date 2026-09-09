from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.common import AuditSchemaMixin


# ==========================================
# Vehicle Media Schemas
# ==========================================
class VehicleMediaRead(BaseModel):
    id: int
    variant_id: Optional[int] = None
    model_id: Optional[int] = None
    media_type: str
    url: str
    alt_text: Optional[str] = None
    sort_order: int = 0
    active: bool = True
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Vehicle Price Schemas
# ==========================================
class VehiclePriceRead(BaseModel):
    id: int
    variant_id: int
    ex_showroom_price: Decimal
    price_type: str
    effective_from: datetime
    effective_to: Optional[datetime] = None
    source_id: Optional[int] = None
    source_record_id: Optional[str] = None
    retrieved_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Manufacturer Schemas
# ==========================================
class ManufacturerBase(BaseModel):
    name: str = Field(..., max_length=100, description="Manufacturer official name")
    slug: str = Field(..., max_length=100, description="URL-friendly unique slug")
    country: str = Field(default="India", max_length=50, description="Country of origin")
    active: bool = Field(default=True, description="Whether the manufacturer is currently active")
    logo_url: Optional[str] = Field(default=None, max_length=500, description="Manufacturer logo URL")


class ManufacturerCreate(ManufacturerBase):
    pass


class ManufacturerRead(ManufacturerBase, AuditSchemaMixin):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManufacturerSimple(BaseModel):
    id: int
    name: str
    slug: str
    country: str
    active: bool
    logo_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Model Schemas
# ==========================================
class CarModelBase(BaseModel):
    name: str = Field(..., max_length=100, description="Model commercial name")
    slug: str = Field(..., max_length=100, description="Unique model slug")
    manufacturer_id: int = Field(..., description="Foreign key to manufacturer")
    body_type: str = Field(..., max_length=50, description="Body type (e.g. SUV, Hatchback, Sedan, MUV, Coupe)")
    segment: Optional[str] = Field(default=None, max_length=50, description="Automotive segment (e.g. Compact SUV, B-Segment)")
    active: bool = Field(default=True, description="Whether currently on sale")
    launch_date: Optional[date] = Field(default=None, description="Original launch date")
    discontinued_date: Optional[date] = Field(default=None, description="Discontinuation date if discontinued")
    launch_year: int = Field(default=2024, description="Launch year")
    description: Optional[str] = Field(default=None, description="Model overview")
    image_url: Optional[str] = Field(default=None, max_length=500, description="Primary model image URL")


class CarModelCreate(CarModelBase):
    pass


class CarModelRead(CarModelBase, AuditSchemaMixin):
    id: int
    created_at: datetime
    updated_at: datetime
    manufacturer: Optional[ManufacturerSimple] = None

    model_config = ConfigDict(from_attributes=True)


class CarModelSimple(BaseModel):
    id: int
    name: str
    slug: str
    body_type: str
    segment: Optional[str] = None
    active: bool
    image_url: Optional[str] = None
    manufacturer: Optional[ManufacturerSimple] = None

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Variant Schemas
# ==========================================
class VariantSpecificationRead(AuditSchemaMixin):
    id: int
    variant_id: int
    engine_displacement_cc: Optional[int] = None
    battery_capacity_kwh: Optional[Decimal] = None
    max_power_bhp: Optional[Decimal] = None
    max_torque_nm: Optional[Decimal] = None
    arai_mileage_kmpl: Decimal
    fuel_tank_capacity_l: Optional[Decimal] = None
    boot_space_l: Optional[int] = None
    airbags_count: int
    safety_rating_stars: Optional[int] = None
    ground_clearance_mm: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class VariantBase(BaseModel):
    model_id: int
    name: str = Field(..., max_length=150, description="Variant name")
    slug: str = Field(..., max_length=150, description="Unique variant slug")
    trim_level: str = Field(default="Base", max_length=50)
    fuel_type: str = Field(..., max_length=30, description="Petrol, Diesel, CNG, Electric, Hybrid, etc.")
    transmission: str = Field(..., max_length=50, description="Manual, Automatic, AMT, CVT, DCT, etc.")
    drivetrain: Optional[str] = Field(default="FWD", max_length=20, description="FWD, RWD, AWD, 4WD")
    engine_cc: Optional[int] = Field(default=None, description="Engine displacement in CC (NULL for EV)")
    engine_power_bhp: Optional[Decimal] = Field(default=None, description="Power in BHP")
    torque_nm: Optional[Decimal] = Field(default=None, description="Torque in Nm")
    seating_capacity: int = Field(default=5, ge=1, le=15, description="Number of passenger seats")
    mileage_claimed: Optional[Decimal] = Field(default=None, description="Claimed mileage (km/l or km/kg or km/kWh)")
    battery_capacity_kwh: Optional[Decimal] = Field(default=None, description="Battery pack size in kWh (EV/Hybrid)")
    range_km: Optional[Decimal] = Field(default=None, description="Driving range in km (EV/Hybrid)")
    active: bool = Field(default=True, description="Whether variant is active")


class VariantCreate(VariantBase):
    pass


class VariantListItemRead(VariantBase, AuditSchemaMixin):
    id: int
    created_at: datetime
    updated_at: datetime
    model: Optional[CarModelSimple] = None
    current_price: Optional[VehiclePriceRead] = None

    model_config = ConfigDict(from_attributes=True)


class VariantDetailRead(VariantBase, AuditSchemaMixin):
    id: int
    created_at: datetime
    updated_at: datetime
    model: Optional[CarModelSimple] = None
    current_price: Optional[VehiclePriceRead] = None
    price_history: List[VehiclePriceRead] = []
    media: List[VehicleMediaRead] = []
    specification: Optional[VariantSpecificationRead] = None

    model_config = ConfigDict(from_attributes=True)


# Legacy alias
VariantRead = VariantListItemRead


# ==========================================
# Detail Aggregation Schemas
# ==========================================
class ManufacturerDetailRead(ManufacturerRead):
    models_count: int = 0
    models: List[CarModelSimple] = []


class CarModelDetailRead(CarModelRead):
    variants_count: int = 0
    variants: List[VariantListItemRead] = []
    media: List[VehicleMediaRead] = []


# ==========================================
# Vehicle Search Schemas
# ==========================================
class VehicleFilterParams(BaseModel):
    manufacturer: Optional[str] = None
    manufacturer_id: Optional[int] = None
    model: Optional[str] = None
    model_id: Optional[int] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    body_type: Optional[str] = None
    segment: Optional[str] = None
    minimum_price: Optional[Decimal] = None
    maximum_price: Optional[Decimal] = None
    minimum_seating_capacity: Optional[int] = None
    active: Optional[bool] = True
    min_safety_rating: Optional[int] = None
    search: Optional[str] = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class VehicleSearchResultItem(BaseModel):
    variant_id: int
    variant_name: str
    variant_slug: str
    trim_level: str
    model_id: int
    model_name: str
    model_slug: str
    body_type: str
    segment: Optional[str] = None
    manufacturer_id: int
    manufacturer_name: str
    manufacturer_slug: str
    country: str
    fuel_type: str
    transmission: str
    drivetrain: Optional[str] = "FWD"
    seating_capacity: int
    engine_cc: Optional[int] = None
    engine_power_bhp: Optional[Decimal] = None
    torque_nm: Optional[Decimal] = None
    mileage_claimed: Optional[Decimal] = None
    battery_capacity_kwh: Optional[Decimal] = None
    range_km: Optional[Decimal] = None
    active: bool
    current_ex_showroom_price: Optional[Decimal] = None
    price_type: Optional[str] = None
    price_effective_from: Optional[datetime] = None
    image_url: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
