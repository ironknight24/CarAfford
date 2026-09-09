from decimal import Decimal
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.common import AuditSchemaMixin


class ManufacturerBase(BaseModel):
    name: str
    slug: str
    country_of_origin: str = "India"
    logo_url: Optional[str] = None
    is_active: bool = True


class ManufacturerRead(ManufacturerBase, AuditSchemaMixin):
    id: int
    model_config = ConfigDict(from_attributes=True)


class CarModelBase(BaseModel):
    name: str
    slug: str
    manufacturer_id: int
    body_type: str
    image_url: Optional[str] = None
    launch_year: int = 2024
    description: Optional[str] = None
    is_discontinued: bool = False


class CarModelRead(CarModelBase, AuditSchemaMixin):
    id: int
    manufacturer: Optional[ManufacturerRead] = None
    model_config = ConfigDict(from_attributes=True)


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


class VariantRead(AuditSchemaMixin):
    id: int
    model_id: int
    name: str
    slug: str
    trim_level: str
    fuel_type: str
    transmission: str
    seating_capacity: int
    is_active: bool
    model: Optional[CarModelRead] = None
    specification: Optional[VariantSpecificationRead] = None

    model_config = ConfigDict(from_attributes=True)


class VehicleFilterParams(BaseModel):
    manufacturer_id: Optional[int] = None
    body_type: Optional[str] = None
    fuel_type: Optional[str] = None
    transmission: Optional[str] = None
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    min_seating: Optional[int] = None
    min_safety_rating: Optional[int] = None
    search: Optional[str] = None
