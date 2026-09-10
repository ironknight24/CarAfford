from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.repositories.location_repo import LocationRepository
from app.schemas.common import BaseResponse, PaginatedResponse
from app.schemas.location import (
    CityDetailRead,
    CityRead,
    CountryDetailRead,
    CountryRead,
    LocationSearchItem,
    RtoOfficeRead,
    StateDetailRead,
    StateRead,
)

# Dedicated routers for modular mounting
countries_router = APIRouter(prefix="/countries", tags=["Countries"])
states_router = APIRouter(prefix="/states", tags=["States"])
cities_router = APIRouter(prefix="/cities", tags=["Cities"])
rtos_router = APIRouter(prefix="/rtos", tags=["RTOs"])
locations_router = APIRouter(prefix="/locations", tags=["Locations"])


# ==============================================================================
# COUNTRIES ENDPOINTS
# ==============================================================================
@countries_router.get(
    "",
    response_model=PaginatedResponse[CountryRead],
    summary="List Countries",
    description="Retrieve a paginated list of supported countries.",
)
async def get_countries(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(
        default=None, description="Search by country name, ISO, or ISO3 code"
    ),
    db: AsyncSession = Depends(get_db),
):
    repo = LocationRepository(db)
    items, total = await repo.get_countries(
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


@countries_router.get(
    "/{country_id}",
    response_model=BaseResponse[CountryDetailRead],
    summary="Get Country Details",
    description="Retrieve detailed country metadata including registered states.",
)
async def get_country_by_id(
    country_id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = LocationRepository(db)
    country = await repo.get_country_by_id(country_id)
    if not country:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Country with ID {country_id} not found.",
        )
    detail = CountryDetailRead(
        id=country.id,
        name=country.name,
        iso_code=country.iso_code,
        iso3_code=country.iso3_code,
        active=country.active,
        created_at=country.created_at,
        updated_at=country.updated_at,
        states_count=len(country.states),
        states=country.states,
    )
    return BaseResponse(data=detail)


# ==============================================================================
# STATES / ADMINISTRATIVE REGIONS ENDPOINTS
# ==============================================================================
@states_router.get(
    "",
    response_model=PaginatedResponse[StateRead],
    summary="List States and Union Territories",
    description="Retrieve a paginated list of states and administrative regions.",
)
async def get_states(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    country_id: Optional[int] = Query(default=None, description="Filter by country ID"),
    region_type: Optional[str] = Query(
        default=None, description="Filter by region type (STATE, UNION_TERRITORY)"
    ),
    active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(default=None, description="Search by state name or code"),
    db: AsyncSession = Depends(get_db),
):
    repo = LocationRepository(db)
    items, total = await repo.get_states(
        page=page,
        page_size=page_size,
        country_id=country_id,
        region_type=region_type,
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


@states_router.get(
    "/{state_id}",
    response_model=BaseResponse[StateDetailRead],
    summary="Get State Details",
    description="Retrieve detailed state information including associated cities and RTO offices.",
)
async def get_state_by_id(
    state_id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = LocationRepository(db)
    state = await repo.get_state_by_id(state_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"State with ID {state_id} not found.",
        )
    detail = StateDetailRead(
        id=state.id,
        country_id=state.country_id,
        name=state.name,
        code=state.code,
        region_type=state.region_type,
        active=state.active,
        is_ut=state.is_ut,
        created_at=state.created_at,
        updated_at=state.updated_at,
        country=state.country,
        cities_count=len(state.cities),
        rtos_count=len(state.rtos),
        cities=state.cities,
        rtos=state.rtos,
    )
    return BaseResponse(data=detail)


@states_router.get(
    "/{state_id}/cities",
    response_model=BaseResponse[List[CityRead]],
    summary="Get Cities by State",
    description="Retrieve all municipal cities registered under a specific state.",
)
async def get_cities_by_state(
    state_id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = LocationRepository(db)
    state = await repo.get_state_by_id(state_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"State with ID {state_id} not found.",
        )
    cities = await repo.get_cities_by_state(state_id)
    return BaseResponse(data=cities)


@states_router.get(
    "/{state_id}/rtos",
    response_model=BaseResponse[List[RtoOfficeRead]],
    summary="Get RTO Offices by State",
    description="Retrieve all Regional Transport Offices (RTOs) registered under a specific state.",
)
async def get_rtos_by_state(
    state_id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = LocationRepository(db)
    state = await repo.get_state_by_id(state_id)
    if not state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"State with ID {state_id} not found.",
        )
    rtos = await repo.get_rtos_by_state(state_id)
    return BaseResponse(data=rtos)


# ==============================================================================
# CITIES ENDPOINTS
# ==============================================================================
@cities_router.get(
    "",
    response_model=PaginatedResponse[CityRead],
    summary="List Cities",
    description="Retrieve a paginated list of cities with optional filters for state, tier, and search.",
)
async def get_cities(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    state_id: Optional[int] = Query(default=None, description="Filter by state ID"),
    tier: Optional[str] = Query(
        default=None, description="Filter by city tier (e.g., Tier 1, Tier 2)"
    ),
    active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(default=None, description="Search by city name or slug"),
    db: AsyncSession = Depends(get_db),
):
    repo = LocationRepository(db)
    items, total = await repo.get_cities(
        page=page,
        page_size=page_size,
        state_id=state_id,
        tier=tier,
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


@cities_router.get(
    "/{city_id}",
    response_model=BaseResponse[CityDetailRead],
    summary="Get City Details",
    description="Retrieve city metadata including RTO jurisdictions associated with the city.",
)
async def get_city_by_id(
    city_id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = LocationRepository(db)
    city = await repo.get_city_by_id(city_id)
    if not city:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"City with ID {city_id} not found.",
        )
    detail = CityDetailRead(
        id=city.id,
        state_id=city.state_id,
        name=city.name,
        slug=city.slug,
        tier=city.tier,
        active=city.active,
        created_at=city.created_at,
        updated_at=city.updated_at,
        state=city.state,
        rtos=city.rtos,
    )
    return BaseResponse(data=detail)


@cities_router.get(
    "/{city_id}/rtos",
    response_model=BaseResponse[List[RtoOfficeRead]],
    summary="Get RTO Offices by City",
    description="Retrieve all Regional Transport Offices (RTOs) associated with a specific city.",
)
async def get_rtos_by_city(
    city_id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = LocationRepository(db)
    city = await repo.get_city_by_id(city_id)
    if not city:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"City with ID {city_id} not found.",
        )
    rtos = await repo.get_rtos_by_city(city_id)
    return BaseResponse(data=rtos)


# ==============================================================================
# RTO (REGIONAL TRANSPORT OFFICE) ENDPOINTS
# ==============================================================================
@rtos_router.get(
    "",
    response_model=PaginatedResponse[RtoOfficeRead],
    summary="List RTO Offices",
    description="Retrieve a paginated list of Regional Transport Offices (RTOs).",
)
async def get_rtos(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page"),
    state_id: Optional[int] = Query(default=None, description="Filter by state ID"),
    city_id: Optional[int] = Query(default=None, description="Filter by city ID"),
    active: Optional[bool] = Query(default=None, description="Filter by active status"),
    search: Optional[str] = Query(
        default=None, description="Search by RTO code, name, or jurisdiction"
    ),
    db: AsyncSession = Depends(get_db),
):
    repo = LocationRepository(db)
    items, total = await repo.get_rtos(
        page=page,
        page_size=page_size,
        state_id=state_id,
        city_id=city_id,
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


@rtos_router.get(
    "/{rto_id}",
    response_model=BaseResponse[RtoOfficeRead],
    summary="Get RTO Office Details",
    description="Retrieve full metadata for an RTO office including state, city, and jurisdiction.",
)
async def get_rto_by_id(
    rto_id: int,
    db: AsyncSession = Depends(get_db),
):
    repo = LocationRepository(db)
    rto = await repo.get_rto_by_id(rto_id)
    if not rto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RTO Office with ID {rto_id} not found.",
        )
    return BaseResponse(data=rto)


# ==============================================================================
# LOCATION SEARCH & LEGACY COMPATIBILITY ROUTER
# ==============================================================================
@locations_router.get(
    "/search",
    response_model=BaseResponse[List[LocationSearchItem]],
    summary="Search Locations Across Hierarchy",
    description="Hierarchical case-insensitive search matching Countries, States, Cities, and RTOs (codes, names, jurisdictions).",
)
async def search_locations(
    q: Optional[str] = Query(
        default=None,
        alias="q",
        description="Search query string (e.g. Bengaluru, KA, Delhi, MH-01)",
    ),
    search: Optional[str] = Query(default=None, description="Alternative search parameter"),
    country_id: Optional[int] = Query(default=None, description="Optional filter by Country ID"),
    state_id: Optional[int] = Query(default=None, description="Optional filter by State ID"),
    city_id: Optional[int] = Query(default=None, description="Optional filter by City ID"),
    active: Optional[bool] = Query(default=True, description="Filter by active status"),
    limit: int = Query(default=50, ge=1, le=100, description="Max results to return"),
    db: AsyncSession = Depends(get_db),
):
    query_str = q or search
    if not query_str or not query_str.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Search query parameter 'q' or 'search' must be provided and non-empty.",
        )

    repo = LocationRepository(db)
    results = await repo.search_locations(
        query=query_str.strip(),
        country_id=country_id,
        state_id=state_id,
        city_id=city_id,
        active=active,
        limit=limit,
    )
    return BaseResponse(data=results)


# Legacy compatibility mounts under /locations
@locations_router.get(
    "/states",
    response_model=BaseResponse[List[StateRead]],
    summary="Get all States/UTs (Legacy Alias)",
    include_in_schema=False,
)
async def get_states_legacy(db: AsyncSession = Depends(get_db)):
    repo = LocationRepository(db)
    states = await repo.get_all_states()
    return BaseResponse(data=states)


@locations_router.get(
    "/states/{state_id}/cities",
    response_model=BaseResponse[List[CityRead]],
    summary="Get Cities by State (Legacy Alias)",
    include_in_schema=False,
)
async def get_cities_by_state_legacy(state_id: int, db: AsyncSession = Depends(get_db)):
    repo = LocationRepository(db)
    cities = await repo.get_cities_by_state(state_id)
    return BaseResponse(data=cities)


@locations_router.get(
    "/states/{state_id}/rtos",
    response_model=BaseResponse[List[RtoOfficeRead]],
    summary="Get RTO offices by State (Legacy Alias)",
    include_in_schema=False,
)
async def get_rtos_by_state_legacy(state_id: int, db: AsyncSession = Depends(get_db)):
    repo = LocationRepository(db)
    rtos = await repo.get_rtos_by_state(state_id)
    return BaseResponse(data=rtos)


# Default router export for backward compatibility
router = locations_router
