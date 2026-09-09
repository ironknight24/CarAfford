from decimal import Decimal
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.common import BaseResponse, PaginatedResponse
from app.schemas.vehicle import (
    CarModelDetailRead,
    CarModelRead,
    ManufacturerDetailRead,
    ManufacturerRead,
    VariantDetailRead,
    VariantListItemRead,
    VehicleFilterParams,
    VehicleSearchResultItem,
)

# Individual modular routers for clean mounting
manufacturers_router = APIRouter(prefix="/manufacturers", tags=["Manufacturers"])
models_router = APIRouter(prefix="/models", tags=["Models"])
variants_router = APIRouter(prefix="/variants", tags=["Variants"])
vehicles_search_router = APIRouter(prefix="/vehicles", tags=["Vehicles"])


# ==============================================================================
# MANUFACTURER ENDPOINTS
# ==============================================================================
@manufacturers_router.get(
    "",
    response_model=PaginatedResponse[ManufacturerRead],
    summary="List Car Manufacturers",
    description="Retrieve a paginated list of car manufacturers with optional search and active status filters.",
)
async def get_manufacturers(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(default=None, description="Search by manufacturer name, slug, or country"),
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    items, total = await repo.get_manufacturers(
        page=page,
        page_size=page_size,
        active=active,
        search=search,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@manufacturers_router.get(
    "/{id}",
    response_model=BaseResponse[ManufacturerDetailRead],
    summary="Get Manufacturer by ID",
    description="Retrieve detailed manufacturer information including all associated car models.",
    responses={404: {"description": "Manufacturer not found"}},
)
async def get_manufacturer_by_id(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    mfg = await repo.get_manufacturer_by_id(id)
    if not mfg:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manufacturer with ID {id} not found.",
        )
    detail = ManufacturerDetailRead(
        id=mfg.id,
        name=mfg.name,
        slug=mfg.slug,
        country=mfg.country,
        active=mfg.active,
        logo_url=mfg.logo_url,
        created_at=mfg.created_at,
        updated_at=mfg.updated_at,
        models_count=len(mfg.models),
        models=mfg.models,
    )
    return BaseResponse(data=detail)


# ==============================================================================
# MODEL ENDPOINTS
# ==============================================================================
@models_router.get(
    "",
    response_model=PaginatedResponse[CarModelRead],
    summary="List Car Models",
    description="Retrieve a paginated list of car models filtered by manufacturer, body type, segment, or active status.",
)
async def get_models(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    manufacturer_id: Optional[int] = Query(default=None, description="Filter by Manufacturer ID"),
    body_type: Optional[str] = Query(default=None, description="Filter by body type (e.g. SUV, Hatchback, Sedan)"),
    segment: Optional[str] = Query(default=None, description="Filter by automotive segment"),
    active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(default=None, description="Search by model or manufacturer name"),
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    items, total = await repo.get_models(
        page=page,
        page_size=page_size,
        manufacturer_id=manufacturer_id,
        body_type=body_type,
        segment=segment,
        active=active,
        search=search,
    )
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@models_router.get(
    "/{id}",
    response_model=BaseResponse[CarModelDetailRead],
    summary="Get Car Model by ID",
    description="Retrieve detailed car model information including manufacturer, variants, and media.",
    responses={404: {"description": "Car model not found"}},
)
async def get_model_by_id(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    model = await repo.get_model_by_id(id)
    if not model:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Car model with ID {id} not found.",
        )

    # Format variants with current active price if present
    variant_items = []
    for v in model.variants:
        active_price = next((p for p in v.prices if p.effective_to is None), None)
        if not active_price and v.prices:
            active_price = v.prices[0]
        variant_items.append(
            VariantListItemRead(
                id=v.id,
                model_id=v.model_id,
                name=v.name,
                slug=v.slug,
                trim_level=v.trim_level,
                fuel_type=v.fuel_type,
                transmission=v.transmission,
                drivetrain=v.drivetrain,
                engine_cc=v.engine_cc,
                engine_power_bhp=v.engine_power_bhp,
                torque_nm=v.torque_nm,
                seating_capacity=v.seating_capacity,
                mileage_claimed=v.mileage_claimed or v.arai_mileage_kmpl,
                battery_capacity_kwh=v.battery_capacity_kwh,
                range_km=v.range_km,
                active=v.active,
                created_at=v.created_at,
                updated_at=v.updated_at,
                current_price=active_price,
            )
        )

    detail = CarModelDetailRead(
        id=model.id,
        name=model.name,
        slug=model.slug,
        manufacturer_id=model.manufacturer_id,
        body_type=model.body_type,
        segment=model.segment,
        active=model.active,
        launch_date=model.launch_date,
        discontinued_date=model.discontinued_date,
        launch_year=model.launch_year,
        description=model.description,
        image_url=model.image_url,
        created_at=model.created_at,
        updated_at=model.updated_at,
        manufacturer=model.manufacturer,
        variants_count=len(variant_items),
        variants=variant_items,
        media=model.media,
    )
    return BaseResponse(data=detail)


# ==============================================================================
# VARIANT ENDPOINTS
# ==============================================================================
@variants_router.get(
    "",
    response_model=PaginatedResponse[VariantListItemRead],
    summary="List Variants",
    description="Retrieve a paginated list of vehicle variants filtered by model, manufacturer, fuel type, or transmission.",
)
async def get_variants(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    model_id: Optional[int] = Query(default=None, description="Filter by Car Model ID"),
    manufacturer_id: Optional[int] = Query(default=None, description="Filter by Manufacturer ID"),
    fuel_type: Optional[str] = Query(default=None, description="Petrol, Diesel, CNG, Electric, Hybrid"),
    transmission: Optional[str] = Query(default=None, description="Manual, Automatic, AMT, CVT, DCT"),
    drivetrain: Optional[str] = Query(default=None, description="FWD, RWD, AWD, 4WD"),
    active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(default=None, description="Search term across variant, model, and manufacturer"),
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    items, total = await repo.get_variants(
        page=page,
        page_size=page_size,
        model_id=model_id,
        manufacturer_id=manufacturer_id,
        fuel_type=fuel_type,
        transmission=transmission,
        drivetrain=drivetrain,
        active=active,
        search=search,
    )

    formatted_items = []
    for v in items:
        active_price = next((p for p in v.prices if p.effective_to is None), None)
        if not active_price and v.prices:
            active_price = v.prices[0]
        formatted_items.append(
            VariantListItemRead(
                id=v.id,
                model_id=v.model_id,
                name=v.name,
                slug=v.slug,
                trim_level=v.trim_level,
                fuel_type=v.fuel_type,
                transmission=v.transmission,
                drivetrain=v.drivetrain,
                engine_cc=v.engine_cc,
                engine_power_bhp=v.engine_power_bhp,
                torque_nm=v.torque_nm,
                seating_capacity=v.seating_capacity,
                mileage_claimed=v.mileage_claimed or v.arai_mileage_kmpl,
                battery_capacity_kwh=v.battery_capacity_kwh,
                range_km=v.range_km,
                active=v.active,
                created_at=v.created_at,
                updated_at=v.updated_at,
                model=v.model,
                current_price=active_price,
            )
        )

    total_pages = (total + page_size - 1) // page_size if total > 0 else 0
    return PaginatedResponse(
        items=formatted_items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@variants_router.get(
    "/{id}",
    response_model=BaseResponse[VariantDetailRead],
    summary="Get Variant by ID",
    description="Retrieve detailed variant specifications, current ex-showroom price, historical price records, and media.",
    responses={404: {"description": "Variant not found"}},
)
async def get_variant_by_id(
    id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    variant = await repo.get_variant_by_id(id)
    if not variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vehicle variant with ID {id} not found.",
        )

    current_price = await repo.get_current_price(variant.id)
    price_history = await repo.get_price_history(variant.id)

    detail = VariantDetailRead(
        id=variant.id,
        model_id=variant.model_id,
        name=variant.name,
        slug=variant.slug,
        trim_level=variant.trim_level,
        fuel_type=variant.fuel_type,
        transmission=variant.transmission,
        drivetrain=variant.drivetrain,
        engine_cc=variant.engine_cc,
        engine_power_bhp=variant.engine_power_bhp,
        torque_nm=variant.torque_nm,
        seating_capacity=variant.seating_capacity,
        mileage_claimed=variant.mileage_claimed or variant.arai_mileage_kmpl,
        battery_capacity_kwh=variant.battery_capacity_kwh,
        range_km=variant.range_km,
        active=variant.active,
        created_at=variant.created_at,
        updated_at=variant.updated_at,
        model=variant.model,
        current_price=current_price,
        price_history=price_history,
        media=variant.media,
        specification=variant.specification,
    )
    return BaseResponse(data=detail)


# ==============================================================================
# VEHICLE SEARCH ENDPOINT
# ==============================================================================
@vehicles_search_router.get(
    "/search",
    response_model=PaginatedResponse[VehicleSearchResultItem],
    summary="Search Vehicle Catalogue",
    description="Multi-factor vehicle search filtered by brand, model, fuel type, transmission, body type, segment, price range, and seating capacity.",
)
async def search_vehicles(
    manufacturer: Optional[str] = Query(default=None, description="Manufacturer name or slug (e.g. Tata, Hyundai)"),
    manufacturer_id: Optional[int] = Query(default=None, description="Manufacturer ID"),
    model: Optional[str] = Query(default=None, description="Model name or slug (e.g. Nexon, Creta)"),
    model_id: Optional[int] = Query(default=None, description="Model ID"),
    fuel_type: Optional[str] = Query(default=None, description="Petrol, Diesel, CNG, Electric, Hybrid"),
    transmission: Optional[str] = Query(default=None, description="Manual, Automatic, AMT, CVT, DCT"),
    body_type: Optional[str] = Query(default=None, description="SUV, Hatchback, Sedan, MUV"),
    segment: Optional[str] = Query(default=None, description="Segment (e.g. Compact SUV, B-Segment)"),
    minimum_price: Optional[Decimal] = Query(default=None, ge=0, description="Minimum ex-showroom price in INR"),
    maximum_price: Optional[Decimal] = Query(default=None, ge=0, description="Maximum ex-showroom price in INR"),
    minimum_seating_capacity: Optional[int] = Query(default=None, ge=1, description="Minimum seating capacity"),
    active: Optional[bool] = Query(default=True, description="Filter by active status"),
    search: Optional[str] = Query(default=None, description="General search query"),
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
):
    if minimum_price is not None and maximum_price is not None and minimum_price > maximum_price:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="minimum_price cannot be greater than maximum_price.",
        )

    params = VehicleFilterParams(
        manufacturer=manufacturer,
        manufacturer_id=manufacturer_id,
        model=model,
        model_id=model_id,
        fuel_type=fuel_type,
        transmission=transmission,
        body_type=body_type,
        segment=segment,
        minimum_price=minimum_price,
        maximum_price=maximum_price,
        minimum_seating_capacity=minimum_seating_capacity,
        active=active,
        search=search,
        page=page,
        page_size=page_size,
    )

    repo = VehicleRepository(db)
    items, total = await repo.search_vehicles(params)
    total_pages = (total + page_size - 1) // page_size if total > 0 else 0

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@vehicles_search_router.get(
    "/variants",
    response_model=BaseResponse[List[VariantListItemRead]],
    summary="List Variants (Legacy Alias)",
    include_in_schema=False,
)
async def get_vehicles_variants_legacy(
    model_id: Optional[int] = Query(default=None),
    manufacturer_id: Optional[int] = Query(default=None),
    fuel_type: Optional[str] = Query(default=None),
    transmission: Optional[str] = Query(default=None),
    active: Optional[bool] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    repo = VehicleRepository(db)
    items, _ = await repo.get_variants(
        page=1,
        page_size=200,
        model_id=model_id,
        manufacturer_id=manufacturer_id,
        fuel_type=fuel_type,
        transmission=transmission,
        active=active,
        search=search,
    )
    return BaseResponse(data=items)
