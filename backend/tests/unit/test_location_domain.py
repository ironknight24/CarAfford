"""
Unit tests for India Location, State, City, and RTO Domain.
Tests cover:
- Country creation and ISO uniqueness
- State creation and (country, code) uniqueness
- City creation and (state, slug) uniqueness
- RTO creation and (state, code) uniqueness
- Flexible relationships (Country -> State -> City -> RTO)
- Optional City -> RTO mapping (city with multiple RTOs, RTO without city)
- Hierarchical multi-level location search
- Inactive filtering
- Data source provenance tracking
"""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_source import DataSource
from app.models.location import City, Country, RtoOffice, State
from app.repositories.location_repo import LocationRepository
from app.schemas.location import CityCreate, CountryCreate, RtoOfficeCreate, StateCreate


@pytest.mark.asyncio
async def test_country_creation_and_retrieval(db_session: AsyncSession):
    repo = LocationRepository(db_session)
    c_in = CountryCreate(name="India", iso_code="IN", iso3_code="IND", active=True)
    country = await repo.create_country(c_in)

    assert country.id is not None
    assert country.name == "India"
    assert country.iso_code == "IN"
    assert country.iso3_code == "IND"
    assert country.active is True

    # Retrieve by ID
    fetched = await repo.get_country_by_id(country.id)
    assert fetched is not None
    assert fetched.id == country.id

    # Retrieve by ISO
    fetched_iso = await repo.get_country_by_iso("IN")
    assert fetched_iso is not None
    assert fetched_iso.name == "India"

    # Retrieve by ISO3
    fetched_iso3 = await repo.get_country_by_iso("IND")
    assert fetched_iso3 is not None
    assert fetched_iso3.name == "India"


@pytest.mark.asyncio
async def test_country_iso_uniqueness(db_session: AsyncSession):
    repo = LocationRepository(db_session)
    await repo.create_country(CountryCreate(name="India", iso_code="IN", iso3_code="IND"))

    # Duplicate ISO code
    dup = Country(name="India Duplicate", iso_code="IN", iso3_code="IN2")
    db_session.add(dup)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_state_country_relationship_and_region_types(db_session: AsyncSession):
    repo = LocationRepository(db_session)
    india = await repo.create_country(CountryCreate(name="India", iso_code="IN", iso3_code="IND"))

    # State
    ka = await repo.create_state(
        StateCreate(
            country_id=india.id, name="Karnataka", code="KA", region_type="STATE", active=True
        )
    )
    assert ka.id is not None
    assert ka.country_id == india.id
    assert ka.region_type == "STATE"
    assert ka.is_ut is False

    # Union Territory
    dl = await repo.create_state(
        StateCreate(
            country_id=india.id, name="Delhi", code="DL", region_type="UNION_TERRITORY", active=True
        )
    )
    assert dl.id is not None
    assert dl.region_type == "UNION_TERRITORY"
    assert dl.is_ut is True

    # Check relation
    fetched_ka = await repo.get_state_by_id(ka.id)
    assert fetched_ka.country.name == "India"


@pytest.mark.asyncio
async def test_state_code_uniqueness_within_country(db_session: AsyncSession):
    repo = LocationRepository(db_session)
    india = await repo.create_country(CountryCreate(name="India", iso_code="IN", iso3_code="IND"))
    await repo.create_state(
        StateCreate(country_id=india.id, name="Maharashtra", code="MH", region_type="STATE")
    )

    # Duplicate state code under same country
    dup_st = State(country_id=india.id, name="Maharashtra Alt", code="MH", region_type="STATE")
    db_session.add(dup_st)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_city_state_relationship_and_slug_uniqueness(db_session: AsyncSession):
    repo = LocationRepository(db_session)
    india = await repo.create_country(CountryCreate(name="India", iso_code="IN", iso3_code="IND"))
    ka = await repo.create_state(
        StateCreate(country_id=india.id, name="Karnataka", code="KA", region_type="STATE")
    )

    blr = await repo.create_city(
        CityCreate(state_id=ka.id, name="Bengaluru", slug="bengaluru", tier="Tier 1", active=True)
    )
    assert blr.id is not None
    assert blr.state_id == ka.id

    fetched_blr = await repo.get_city_by_id(blr.id)
    assert fetched_blr.state.name == "Karnataka"

    # Duplicate city slug under same state
    dup_city = City(state_id=ka.id, name="Bangalore City", slug="bengaluru", tier="Tier 1")
    db_session.add(dup_city)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_rto_city_and_state_relationship(db_session: AsyncSession):
    repo = LocationRepository(db_session)
    india = await repo.create_country(CountryCreate(name="India", iso_code="IN", iso3_code="IND"))
    ka = await repo.create_state(
        StateCreate(country_id=india.id, name="Karnataka", code="KA", region_type="STATE")
    )
    blr = await repo.create_city(
        CityCreate(state_id=ka.id, name="Bengaluru", slug="bengaluru", tier="Tier 1")
    )

    # 1. RTO associated with Bengaluru City
    rto_ka01 = await repo.create_rto(
        RtoOfficeCreate(
            state_id=ka.id,
            city_id=blr.id,
            code="KA-01",
            name="RTO Koramangala",
            jurisdiction="Bengaluru South (Koramangala, HSR)",
            active=True,
        )
    )
    assert rto_ka01.id is not None
    assert rto_ka01.state_id == ka.id
    assert rto_ka01.city_id == blr.id

    # 2. RTO belonging to Karnataka State without specific city
    rto_rural = await repo.create_rto(
        RtoOfficeCreate(
            state_id=ka.id,
            city_id=None,
            code="KA-50",
            name="RTO Yelahanka Rural",
            jurisdiction="Rural North Bangalore Suburbs",
            active=True,
        )
    )
    assert rto_rural.id is not None
    assert rto_rural.city_id is None

    # Test City -> multiple RTOs
    rto_ka02 = await repo.create_rto(
        RtoOfficeCreate(
            state_id=ka.id,
            city_id=blr.id,
            code="KA-02",
            name="RTO Rajajinagar",
            jurisdiction="Bengaluru West",
            active=True,
        )
    )
    assert rto_ka02.id is not None

    blr_detail = await repo.get_city_by_id(blr.id)
    assert len(blr_detail.rtos) == 2
    rto_codes = [r.code for r in blr_detail.rtos]
    assert "KA-01" in rto_codes
    assert "KA-02" in rto_codes


@pytest.mark.asyncio
async def test_rto_code_uniqueness_within_state(db_session: AsyncSession):
    repo = LocationRepository(db_session)
    india = await repo.create_country(CountryCreate(name="India", iso_code="IN", iso3_code="IND"))
    mh = await repo.create_state(
        StateCreate(country_id=india.id, name="Maharashtra", code="MH", region_type="STATE")
    )

    await repo.create_rto(
        RtoOfficeCreate(
            state_id=mh.id, code="MH-01", name="RTO Tardeo", jurisdiction="Mumbai South"
        )
    )

    # Duplicate RTO code in same state
    dup_rto = RtoOffice(state_id=mh.id, code="MH-01", name="Duplicate Tardeo", jurisdiction="South")
    db_session.add(dup_rto)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_location_search_hierarchical(db_session: AsyncSession):
    repo = LocationRepository(db_session)
    india = await repo.create_country(CountryCreate(name="India", iso_code="IN", iso3_code="IND"))
    ka = await repo.create_state(
        StateCreate(country_id=india.id, name="Karnataka", code="KA", region_type="STATE")
    )
    blr = await repo.create_city(
        CityCreate(state_id=ka.id, name="Bengaluru", slug="bengaluru", tier="Tier 1")
    )
    await repo.create_rto(
        RtoOfficeCreate(
            state_id=ka.id,
            city_id=blr.id,
            code="KA-01",
            name="RTO Koramangala",
            jurisdiction="Koramangala, HSR",
        )
    )

    dl = await repo.create_state(
        StateCreate(country_id=india.id, name="Delhi", code="DL", region_type="UNION_TERRITORY")
    )
    nd = await repo.create_city(
        CityCreate(state_id=dl.id, name="New Delhi", slug="new-delhi", tier="Tier 1")
    )
    await repo.create_rto(
        RtoOfficeCreate(
            state_id=dl.id,
            city_id=nd.id,
            code="DL-01",
            name="RTO Mall Road",
            jurisdiction="North Delhi",
        )
    )

    # 1. Search for "Bengaluru" (should find city and RTO with Bengaluru in name/jurisdiction)
    results_blr = await repo.search_locations("Bengaluru")
    assert len(results_blr) >= 1
    assert any(r.city_name == "Bengaluru" for r in results_blr)

    # 2. Search for "KA" (should match Karnataka state and KA-01 RTO)
    results_ka = await repo.search_locations("KA")
    assert len(results_ka) >= 1
    match_types = [r.match_type for r in results_ka]
    assert "state" in match_types or "rto" in match_types

    # 3. Search for "Delhi" (should match Delhi state/UT)
    results_dl = await repo.search_locations("Delhi")
    assert len(results_dl) >= 1
    assert any(r.state_name == "Delhi" for r in results_dl)


@pytest.mark.asyncio
async def test_rto_data_source_provenance(db_session: AsyncSession):
    repo = LocationRepository(db_session)
    src = DataSource(
        name="Parivahan Demo",
        slug="parivahan-demo",
        provider_type="government",
        is_active=True,
    )
    db_session.add(src)
    await db_session.flush()

    india = await repo.create_country(CountryCreate(name="India", iso_code="IN", iso3_code="IND"))
    ts = await repo.create_state(
        StateCreate(country_id=india.id, name="Telangana", code="TS", region_type="STATE")
    )
    hyd = await repo.create_city(CityCreate(state_id=ts.id, name="Hyderabad", slug="hyderabad"))

    rto = await repo.create_rto(
        RtoOffice(
            state_id=ts.id,
            city_id=hyd.id,
            code="TS-07",
            name="RTO Hyderabad Central",
            source_id=src.id,
            source_record_id="PARIVAHAN-TS-07",
        )
    )
    assert rto.source_id == src.id
    assert rto.source_record_id == "PARIVAHAN-TS-07"

    fetched = await repo.get_rto_by_id(rto.id)
    assert fetched.source is not None
    assert fetched.source.name == "Parivahan Demo"
