from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.location import City, Country, RtoOffice, State, TaxSlab
from app.schemas.location import (
    CityCreate,
    CountryCreate,
    LocationSearchItem,
    RtoOfficeCreate,
    StateCreate,
)


class LocationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ==========================================
    # Countries
    # ==========================================
    async def get_countries(
        self,
        page: int = 1,
        page_size: int = 20,
        active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Country], int]:
        stmt = select(Country)
        count_stmt = select(func.count(Country.id))

        if active is not None:
            stmt = stmt.where(Country.active == active)
            count_stmt = count_stmt.where(Country.active == active)

        if search:
            search_term = f"%{search}%"
            filter_expr = or_(
                Country.name.ilike(search_term),
                Country.iso_code.ilike(search_term),
                Country.iso3_code.ilike(search_term),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(Country.name).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_country_by_id(self, country_id: int) -> Optional[Country]:
        stmt = select(Country).options(selectinload(Country.states)).where(Country.id == country_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_country_by_iso(self, iso_code: str) -> Optional[Country]:
        stmt = (
            select(Country)
            .options(selectinload(Country.states))
            .where(
                or_(
                    Country.iso_code == iso_code.upper(),
                    Country.iso3_code == iso_code.upper(),
                )
            )
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_country(self, country: Country | CountryCreate | dict) -> Country:
        if isinstance(country, dict):
            obj = Country(**country)
        elif not isinstance(country, Country):
            obj = Country(**country.model_dump(exclude_unset=True))
        else:
            obj = country
        self.session.add(obj)
        await self.session.flush()
        return obj

    # ==========================================
    # States / Administrative Regions
    # ==========================================
    async def get_states(
        self,
        page: int = 1,
        page_size: int = 50,
        country_id: Optional[int] = None,
        region_type: Optional[str] = None,
        active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[State], int]:
        stmt = select(State).options(selectinload(State.country))
        count_stmt = select(func.count(State.id))

        if country_id is not None:
            stmt = stmt.where(State.country_id == country_id)
            count_stmt = count_stmt.where(State.country_id == country_id)

        if region_type is not None:
            stmt = stmt.where(State.region_type == region_type.upper())
            count_stmt = count_stmt.where(State.region_type == region_type.upper())

        if active is not None:
            stmt = stmt.where(State.active == active)
            count_stmt = count_stmt.where(State.active == active)

        if search:
            search_term = f"%{search}%"
            filter_expr = or_(
                State.name.ilike(search_term),
                State.code.ilike(search_term),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(State.name).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_all_states(self) -> List[State]:
        stmt = select(State).options(selectinload(State.country)).order_by(State.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_state_by_id(self, state_id: int) -> Optional[State]:
        stmt = (
            select(State)
            .options(
                selectinload(State.country),
                selectinload(State.cities),
                selectinload(State.rtos),
            )
            .where(State.id == state_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_state_by_code(
        self, code: str, country_id: Optional[int] = None
    ) -> Optional[State]:
        stmt = select(State).options(selectinload(State.country)).where(State.code == code.upper())
        if country_id is not None:
            stmt = stmt.where(State.country_id == country_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_state(self, state: State | StateCreate | dict) -> State:
        if isinstance(state, dict):
            obj = State(**state)
        elif not isinstance(state, State):
            obj = State(**state.model_dump(exclude_unset=True))
        else:
            obj = state
        self.session.add(obj)
        await self.session.flush()
        return obj

    # ==========================================
    # Cities
    # ==========================================
    async def get_cities(
        self,
        page: int = 1,
        page_size: int = 50,
        state_id: Optional[int] = None,
        tier: Optional[str] = None,
        active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[City], int]:
        stmt = select(City).options(selectinload(City.state))
        count_stmt = select(func.count(City.id))

        if state_id is not None:
            stmt = stmt.where(City.state_id == state_id)
            count_stmt = count_stmt.where(City.state_id == state_id)

        if tier is not None:
            stmt = stmt.where(City.tier.ilike(f"%{tier}%"))
            count_stmt = count_stmt.where(City.tier.ilike(f"%{tier}%"))

        if active is not None:
            stmt = stmt.where(City.active == active)
            count_stmt = count_stmt.where(City.active == active)

        if search:
            search_term = f"%{search}%"
            filter_expr = or_(
                City.name.ilike(search_term),
                City.slug.ilike(search_term),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(City.name).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_cities_by_state(self, state_id: int) -> List[City]:
        stmt = (
            select(City)
            .options(selectinload(City.state))
            .where(City.state_id == state_id)
            .order_by(City.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_city_by_id(self, city_id: int) -> Optional[City]:
        stmt = (
            select(City)
            .options(
                selectinload(City.state),
                selectinload(City.rtos),
            )
            .where(City.id == city_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_city_by_slug(self, slug: str, state_id: Optional[int] = None) -> Optional[City]:
        stmt = select(City).options(selectinload(City.state)).where(City.slug == slug.lower())
        if state_id is not None:
            stmt = stmt.where(City.state_id == state_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_city(self, city: City | CityCreate | dict) -> City:
        if isinstance(city, dict):
            obj = City(**city)
        elif not isinstance(city, City):
            obj = City(**city.model_dump(exclude_unset=True))
        else:
            obj = city
        self.session.add(obj)
        await self.session.flush()
        return obj

    # ==========================================
    # RTO Offices
    # ==========================================
    async def get_rtos(
        self,
        page: int = 1,
        page_size: int = 50,
        state_id: Optional[int] = None,
        city_id: Optional[int] = None,
        active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[RtoOffice], int]:
        stmt = select(RtoOffice).options(
            selectinload(RtoOffice.state),
            selectinload(RtoOffice.city),
        )
        count_stmt = select(func.count(RtoOffice.id))

        if state_id is not None:
            stmt = stmt.where(RtoOffice.state_id == state_id)
            count_stmt = count_stmt.where(RtoOffice.state_id == state_id)

        if city_id is not None:
            stmt = stmt.where(RtoOffice.city_id == city_id)
            count_stmt = count_stmt.where(RtoOffice.city_id == city_id)

        if active is not None:
            stmt = stmt.where(RtoOffice.active == active)
            count_stmt = count_stmt.where(RtoOffice.active == active)

        if search:
            search_term = f"%{search}%"
            filter_expr = or_(
                RtoOffice.code.ilike(search_term),
                RtoOffice.name.ilike(search_term),
                RtoOffice.jurisdiction.ilike(search_term),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(RtoOffice.code).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_rtos_by_state(self, state_id: int) -> List[RtoOffice]:
        stmt = (
            select(RtoOffice)
            .options(
                selectinload(RtoOffice.state),
                selectinload(RtoOffice.city),
            )
            .where(RtoOffice.state_id == state_id)
            .order_by(RtoOffice.code)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_rtos_by_city(self, city_id: int) -> List[RtoOffice]:
        stmt = (
            select(RtoOffice)
            .options(
                selectinload(RtoOffice.state),
                selectinload(RtoOffice.city),
            )
            .where(RtoOffice.city_id == city_id)
            .order_by(RtoOffice.code)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_rto_by_id(self, rto_id: int) -> Optional[RtoOffice]:
        stmt = (
            select(RtoOffice)
            .options(
                selectinload(RtoOffice.state),
                selectinload(RtoOffice.city),
                selectinload(RtoOffice.source),
            )
            .where(RtoOffice.id == rto_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_rto_by_code(
        self, code: str, state_id: Optional[int] = None
    ) -> Optional[RtoOffice]:
        stmt = (
            select(RtoOffice)
            .options(
                selectinload(RtoOffice.state),
                selectinload(RtoOffice.city),
            )
            .where(RtoOffice.code == code.upper())
        )
        if state_id is not None:
            stmt = stmt.where(RtoOffice.state_id == state_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_rto(self, rto: RtoOffice | RtoOfficeCreate | dict) -> RtoOffice:
        if isinstance(rto, dict):
            obj = RtoOffice(**rto)
        elif not isinstance(rto, RtoOffice):
            obj = RtoOffice(**rto.model_dump(exclude_unset=True))
        else:
            obj = rto
        self.session.add(obj)
        await self.session.flush()
        return obj

    # ==========================================
    # Location Search (Hierarchical Multi-Level)
    # ==========================================
    async def search_locations(
        self,
        query: str,
        country_id: Optional[int] = None,
        state_id: Optional[int] = None,
        city_id: Optional[int] = None,
        active: Optional[bool] = True,
        limit: int = 50,
    ) -> List[LocationSearchItem]:
        """Case-insensitive multi-level search finding matching RTOs, cities, states, and countries."""
        s_term = f"%{query}%"
        results: List[LocationSearchItem] = []

        # 1. Search RTOs
        rto_stmt = (
            select(RtoOffice, State, Country, City)
            .join(State, RtoOffice.state_id == State.id)
            .join(Country, State.country_id == Country.id)
            .outerjoin(City, RtoOffice.city_id == City.id)
            .where(
                or_(
                    RtoOffice.code.ilike(s_term),
                    RtoOffice.name.ilike(s_term),
                    RtoOffice.jurisdiction.ilike(s_term),
                )
            )
        )
        if country_id:
            rto_stmt = rto_stmt.where(Country.id == country_id)
        if state_id:
            rto_stmt = rto_stmt.where(State.id == state_id)
        if city_id:
            rto_stmt = rto_stmt.where(RtoOffice.city_id == city_id)
        if active is not None:
            rto_stmt = rto_stmt.where(RtoOffice.active == active)

        rto_rows = await self.session.execute(rto_stmt.limit(limit))
        for rto, state, country, city in rto_rows:
            results.append(
                LocationSearchItem(
                    country_id=country.id,
                    country_name=country.name,
                    country_iso=country.iso_code,
                    state_id=state.id,
                    state_name=state.name,
                    state_code=state.code,
                    region_type=state.region_type,
                    city_id=city.id if city else None,
                    city_name=city.name if city else None,
                    city_slug=city.slug if city else None,
                    rto_id=rto.id,
                    rto_code=rto.code,
                    rto_name=rto.name,
                    rto_jurisdiction=rto.jurisdiction,
                    match_type="rto",
                    active=rto.active,
                )
            )

        # 2. Search Cities (if room in limit)
        remaining = limit - len(results)
        if remaining > 0:
            city_stmt = (
                select(City, State, Country)
                .join(State, City.state_id == State.id)
                .join(Country, State.country_id == Country.id)
                .where(
                    or_(
                        City.name.ilike(s_term),
                        City.slug.ilike(s_term),
                    )
                )
            )
            if country_id:
                city_stmt = city_stmt.where(Country.id == country_id)
            if state_id:
                city_stmt = city_stmt.where(State.id == state_id)
            if active is not None:
                city_stmt = city_stmt.where(City.active == active)

            city_rows = await self.session.execute(city_stmt.limit(remaining))
            for city, state, country in city_rows:
                results.append(
                    LocationSearchItem(
                        country_id=country.id,
                        country_name=country.name,
                        country_iso=country.iso_code,
                        state_id=state.id,
                        state_name=state.name,
                        state_code=state.code,
                        region_type=state.region_type,
                        city_id=city.id,
                        city_name=city.name,
                        city_slug=city.slug,
                        rto_id=None,
                        rto_code=None,
                        rto_name=None,
                        rto_jurisdiction=None,
                        match_type="city",
                        active=city.active,
                    )
                )

        # 3. Search States (if room in limit)
        remaining = limit - len(results)
        if remaining > 0:
            state_stmt = (
                select(State, Country)
                .join(Country, State.country_id == Country.id)
                .where(
                    or_(
                        State.name.ilike(s_term),
                        State.code.ilike(s_term),
                    )
                )
            )
            if country_id:
                state_stmt = state_stmt.where(Country.id == country_id)
            if active is not None:
                state_stmt = state_stmt.where(State.active == active)

            state_rows = await self.session.execute(state_stmt.limit(remaining))
            for state, country in state_rows:
                results.append(
                    LocationSearchItem(
                        country_id=country.id,
                        country_name=country.name,
                        country_iso=country.iso_code,
                        state_id=state.id,
                        state_name=state.name,
                        state_code=state.code,
                        region_type=state.region_type,
                        city_id=None,
                        city_name=None,
                        city_slug=None,
                        rto_id=None,
                        rto_code=None,
                        rto_name=None,
                        rto_jurisdiction=None,
                        match_type="state",
                        active=state.active,
                    )
                )

        return results

    # ==========================================
    # Road Tax Slabs
    # ==========================================
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
