from decimal import Decimal
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.location import City, RtoOffice, State, TaxSlab


class LocationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_all_states(self) -> List[State]:
        stmt = select(State).order_by(State.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_state_by_id(self, state_id: int) -> Optional[State]:
        return await self.session.get(State, state_id)

    async def get_state_by_code(self, code: str) -> Optional[State]:
        stmt = select(State).where(State.code == code.upper())
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_cities_by_state(self, state_id: int) -> List[City]:
        stmt = select(City).where(City.state_id == state_id).order_by(City.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_city_by_id(self, city_id: int) -> Optional[City]:
        return await self.session.get(City, city_id)

    async def get_rtos_by_state(self, state_id: int) -> List[RtoOffice]:
        stmt = select(RtoOffice).where(RtoOffice.state_id == state_id).order_by(RtoOffice.code)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_tax_slab_for_vehicle(
        self,
        state_id: int,
        fuel_type: str,
        ex_showroom_price: Decimal,
        is_bh_series: bool = False,
    ) -> Optional[TaxSlab]:
        stmt = (
            select(TaxSlab)
            .where(
                TaxSlab.state_id == state_id,
                TaxSlab.fuel_type.ilike(f"%{fuel_type}%"),
                TaxSlab.is_bh_series == is_bh_series,
                TaxSlab.min_ex_showroom <= ex_showroom_price,
            )
            .order_by(TaxSlab.min_ex_showroom.desc())
        )
        result = await self.session.execute(stmt)
        slabs = list(result.scalars().all())
        for slab in slabs:
            if slab.max_ex_showroom is None or ex_showroom_price <= slab.max_ex_showroom:
                return slab
        return slabs[0] if slabs else None
