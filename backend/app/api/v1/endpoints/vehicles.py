from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.common import BaseResponse
from app.schemas.vehicle import (
    CarModelRead,
    ManufacturerRead,
    VariantRead,
    VehicleFilterParams,
)

router = APIRouter()


@router.get("/manufacturers", response_model=BaseResponse[List[ManufacturerRead]], summary="Get Car Manufacturers")
async def get_manufacturers(db: AsyncSession = Depends(get_db)):
    repo = VehicleRepository(db)
    items = await repo.get_manufacturers()
    return BaseResponse(data=items)


@router.get("/models", response_model=BaseResponse[List[CarModelRead]], summary="Get Car Models")
async def get_models(
    manufacturer_id: Optional[int] = Query(None, description="Filter by Manufacturer ID"),
    body_type: Optional[str] = Query(None, description="Filter by body type (e.g. SUV, Hatchback, Sedan)"),
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    items = await repo.get_models(manufacturer_id=manufacturer_id, body_type=body_type)
    return BaseResponse(data=items)


@router.get("/variants", response_model=BaseResponse[List[VariantRead]], summary="Filter & Search Variants")
async def get_variants(
    manufacturer_id: Optional[int] = Query(None),
    body_type: Optional[str] = Query(None),
    fuel_type: Optional[str] = Query(None),
    transmission: Optional[str] = Query(None),
    min_seating: Optional[int] = Query(None),
    min_safety_rating: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    params = VehicleFilterParams(
        manufacturer_id=manufacturer_id,
        body_type=body_type,
        fuel_type=fuel_type,
        transmission=transmission,
        min_seating=min_seating,
        min_safety_rating=min_safety_rating,
        search=search,
    )
    items = await repo.filter_variants(params)
    return BaseResponse(data=items)


@router.get("/variants/{variant_id}", response_model=BaseResponse[VariantRead], summary="Get Variant by ID")
async def get_variant_by_id(variant_id: int, db: AsyncSession = Depends(get_db)):
    repo = VehicleRepository(db)
    item = await repo.get_variant_by_id(variant_id)
    if not item:
        raise HTTPException(status_code=404, detail="Vehicle variant not found")
    return BaseResponse(data=item)
