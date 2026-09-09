from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db
from app.repositories.location_repo import LocationRepository
from app.schemas.common import BaseResponse
from app.schemas.location import CityRead, RtoOfficeRead, StateRead, TaxSlabRead

router = APIRouter()


@router.get("/states", response_model=BaseResponse[List[StateRead]], summary="Get all Indian States/UTs")
async def get_states(db: AsyncSession = Depends(get_db)):
    repo = LocationRepository(db)
    states = await repo.get_all_states()
    return BaseResponse(data=states)


@router.get("/states/{state_id}/cities", response_model=BaseResponse[List[CityRead]], summary="Get cities by State")
async def get_cities_by_state(state_id: int, db: AsyncSession = Depends(get_db)):
    repo = LocationRepository(db)
    cities = await repo.get_cities_by_state(state_id)
    return BaseResponse(data=cities)


@router.get("/states/{state_id}/rtos", response_model=BaseResponse[List[RtoOfficeRead]], summary="Get RTO offices by State")
async def get_rtos_by_state(state_id: int, db: AsyncSession = Depends(get_db)):
    repo = LocationRepository(db)
    rtos = await repo.get_rtos_by_state(state_id)
    return BaseResponse(data=rtos)
