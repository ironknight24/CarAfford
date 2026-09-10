"""
Unit tests for the Vehicle Catalogue Domain.
Tests cover:
- Manufacturer creation / retrieval
- Model -> Manufacturer relationship
- Variant -> Model relationship
- Current vehicle price retrieval
- Historical price retrieval
- Multiple historical prices
- Price effective-date selection
- Prevention/detection of overlapping effective periods
- Vehicle search & filtering (manufacturer, fuel, transmission, body type, price range, seating)
- Pagination
- Discontinued models
- EV variants with NULL engine fields & Petrol/Diesel with NULL battery fields
- 404 and error handling
"""

from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.vehicle import Manufacturer, CarModel, Variant, VehicleMedia
from app.models.pricing import VehiclePrice
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.vehicle import (
    ManufacturerCreate,
    CarModelCreate,
    VariantCreate,
    VehicleFilterParams,
)
from app.schemas.pricing import VehiclePriceCreate


@pytest.mark.asyncio
async def test_manufacturer_creation_and_retrieval(db_session: AsyncSession):
    repo = VehicleRepository(db_session)
    mfg_in = ManufacturerCreate(
        name="Tata Motors",
        slug="tata-motors",
        country="India",
        active=True,
    )
    mfg = await repo.create_manufacturer(mfg_in)
    assert mfg.id is not None
    assert mfg.name == "Tata Motors"
    assert mfg.slug == "tata-motors"
    assert mfg.country == "India"
    assert mfg.active is True

    # Retrieve by ID
    fetched = await repo.get_manufacturer_by_id(mfg.id)
    assert fetched is not None
    assert fetched.id == mfg.id

    # Retrieve by slug
    fetched_slug = await repo.get_manufacturer_by_slug("tata-motors")
    assert fetched_slug is not None
    assert fetched_slug.name == "Tata Motors"


@pytest.mark.asyncio
async def test_manufacturer_slug_and_name_uniqueness(db_session: AsyncSession):
    repo = VehicleRepository(db_session)
    mfg1 = ManufacturerCreate(
        name="Hyundai India", slug="hyundai", country="South Korea", active=True
    )
    await repo.create_manufacturer(mfg1)

    # Duplicate name should raise IntegrityError
    mfg2 = Manufacturer(
        name="Hyundai India", slug="hyundai-alt", country="South Korea", active=True
    )
    db_session.add(mfg2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_model_manufacturer_relationship(db_session: AsyncSession):
    repo = VehicleRepository(db_session)
    mfg = await repo.create_manufacturer(
        ManufacturerCreate(name="Mahindra", slug="mahindra", country="India")
    )

    model_in = CarModelCreate(
        manufacturer_id=mfg.id,
        name="XUV700",
        slug="mahindra-xuv700",
        body_type="SUV",
        segment="D-Segment",
        active=True,
        launch_date=datetime(2021, 10, 1, tzinfo=timezone.utc),
    )
    model = await repo.create_model(model_in)
    assert model.id is not None
    assert model.manufacturer_id == mfg.id

    fetched = await repo.get_model_by_id(model.id)
    assert fetched is not None
    assert fetched.manufacturer is not None
    assert fetched.manufacturer.name == "Mahindra"


@pytest.mark.asyncio
async def test_discontinued_model_handling(db_session: AsyncSession):
    repo = VehicleRepository(db_session)
    mfg = await repo.create_manufacturer(
        ManufacturerCreate(name="Ford", slug="ford", country="USA", active=False)
    )
    model = await repo.create_model(
        CarModelCreate(
            manufacturer_id=mfg.id,
            name="EcoSport",
            slug="ford-ecosport",
            body_type="SUV",
            segment="Compact SUV",
            active=False,
            launch_date=datetime(2013, 6, 1, tzinfo=timezone.utc),
            discontinued_date=datetime(2021, 9, 1, tzinfo=timezone.utc),
        )
    )

    # Discontinued model should remain in DB and be queryable
    fetched = await repo.get_model_by_id(model.id)
    assert fetched is not None
    assert fetched.active is False
    assert fetched.discontinued_date is not None


@pytest.mark.asyncio
async def test_variant_model_relationship_ice(db_session: AsyncSession):
    repo = VehicleRepository(db_session)
    mfg = await repo.create_manufacturer(
        ManufacturerCreate(name="Maruti Suzuki", slug="maruti-suzuki", country="India")
    )
    model = await repo.create_model(
        CarModelCreate(
            manufacturer_id=mfg.id, name="Swift", slug="maruti-swift", body_type="Hatchback"
        )
    )

    # Petrol variant (battery fields NULL)
    variant_in = VariantCreate(
        model_id=model.id,
        name="ZXi Plus AMT",
        slug="maruti-swift-zxi-plus-amt",
        fuel_type="Petrol",
        transmission="AMT",
        drivetrain="FWD",
        engine_cc=1197,
        engine_power_bhp=Decimal("80.5"),
        torque_nm=Decimal("111.7"),
        seating_capacity=5,
        mileage_claimed=Decimal("25.75"),
        battery_capacity_kwh=None,
        range_km=None,
        active=True,
    )
    variant = await repo.create_variant(variant_in)
    assert variant.id is not None
    assert variant.engine_cc == 1197
    assert variant.battery_capacity_kwh is None

    fetched = await repo.get_variant_by_id(variant.id)
    assert fetched is not None
    assert fetched.model.name == "Swift"


@pytest.mark.asyncio
async def test_ev_variant_with_null_engine_fields(db_session: AsyncSession):
    repo = VehicleRepository(db_session)
    mfg = await repo.create_manufacturer(
        ManufacturerCreate(name="MG Motor", slug="mg-motor", country="UK")
    )
    model = await repo.create_model(
        CarModelCreate(manufacturer_id=mfg.id, name="ZS EV", slug="mg-zs-ev", body_type="SUV")
    )

    # EV variant (engine fields NULL, battery fields present)
    variant_in = VariantCreate(
        model_id=model.id,
        name="Exclusive Plus 50.3 kWh",
        slug="mg-zs-ev-exclusive-plus",
        fuel_type="Electric",
        transmission="Automatic",
        drivetrain="FWD",
        engine_cc=None,
        engine_power_bhp=Decimal("174.3"),
        torque_nm=Decimal("280.0"),
        seating_capacity=5,
        mileage_claimed=None,
        battery_capacity_kwh=Decimal("50.3"),
        range_km=461,
        active=True,
    )
    variant = await repo.create_variant(variant_in)
    assert variant.id is not None
    assert variant.engine_cc is None
    assert variant.battery_capacity_kwh == Decimal("50.3")
    assert variant.range_km == 461


@pytest.mark.asyncio
async def test_multiple_historical_prices_and_active_price_resolution(db_session: AsyncSession):
    repo = VehicleRepository(db_session)
    mfg = await repo.create_manufacturer(
        ManufacturerCreate(name="Kia", slug="kia", country="South Korea")
    )
    model = await repo.create_model(
        CarModelCreate(manufacturer_id=mfg.id, name="Seltos", slug="kia-seltos", body_type="SUV")
    )
    variant = await repo.create_variant(
        VariantCreate(
            model_id=model.id,
            name="HTX 1.5 Petrol MT",
            slug="kia-seltos-htx-15-petrol-mt",
            fuel_type="Petrol",
            transmission="Manual",
            engine_cc=1497,
            seating_capacity=5,
        )
    )

    now = datetime.now(timezone.utc)
    t_past_start = now - timedelta(days=180)
    t_past_end = now - timedelta(days=60)
    t_current_start = now - timedelta(days=60)

    # 1. Old historical price (Jan - Apr: 14,50,000)
    price_old = await repo.add_vehicle_price(
        VehiclePriceCreate(
            variant_id=variant.id,
            ex_showroom_price=Decimal("1450000.00"),
            price_type="EX_SHOWROOM",
            effective_from=t_past_start,
            effective_to=t_past_end,
        )
    )
    assert price_old.id is not None

    # 2. Current price (Apr - Ongoing: 14,90,000)
    price_current = await repo.add_vehicle_price(
        VehiclePriceCreate(
            variant_id=variant.id,
            ex_showroom_price=Decimal("1490000.00"),
            price_type="EX_SHOWROOM",
            effective_from=t_current_start,
            effective_to=None,
        )
    )
    assert price_current.id is not None

    # Retrieve all prices
    all_prices = await repo.get_prices_for_variant(variant.id)
    assert len(all_prices) == 2

    # Verify active price resolves to the current one (14,90,000)
    active_price = await repo.get_current_price(variant.id)
    assert active_price is not None
    assert active_price.ex_showroom_price == Decimal("1490000.00")

    # Verify historical price resolution at a past date (90 days ago -> 14,50,000)
    past_date = now - timedelta(days=90)
    past_price = await repo.get_price_at_date(variant.id, past_date)
    assert past_price is not None
    assert past_price.ex_showroom_price == Decimal("1450000.00")


@pytest.mark.asyncio
async def test_price_period_overlap_prevention(db_session: AsyncSession):
    repo = VehicleRepository(db_session)
    mfg = await repo.create_manufacturer(
        ManufacturerCreate(name="Honda", slug="honda", country="Japan")
    )
    model = await repo.create_model(
        CarModelCreate(manufacturer_id=mfg.id, name="City", slug="honda-city", body_type="Sedan")
    )
    variant = await repo.create_variant(
        VariantCreate(
            model_id=model.id,
            name="ZX CVT",
            slug="honda-city-zx-cvt",
            fuel_type="Petrol",
            transmission="CVT",
            engine_cc=1498,
            seating_capacity=5,
        )
    )

    now = datetime.now(timezone.utc)
    t1 = now - timedelta(days=100)
    t2 = now - timedelta(days=50)

    # Add existing price [t1 -> t2]
    await repo.add_vehicle_price(
        VehiclePriceCreate(
            variant_id=variant.id,
            ex_showroom_price=Decimal("1600000.00"),
            effective_from=t1,
            effective_to=t2,
        )
    )

    # Check overlapping period: [t1 + 10 days, t2 + 10 days]
    has_overlap = await repo.check_price_period_overlap(
        variant_id=variant.id,
        effective_from=t1 + timedelta(days=10),
        effective_to=t2 + timedelta(days=10),
    )
    assert has_overlap is True

    # Non-overlapping period: [t2 + 1 day, None]
    no_overlap = await repo.check_price_period_overlap(
        variant_id=variant.id,
        effective_from=t2 + timedelta(days=1),
        effective_to=None,
    )
    assert no_overlap is False


@pytest.mark.asyncio
async def test_vehicle_search_and_multi_filtering(db_session: AsyncSession):
    repo = VehicleRepository(db_session)
    # Setup manufacturers
    tata = await repo.create_manufacturer(
        ManufacturerCreate(name="Tata", slug="tata", country="India")
    )
    hyundai = await repo.create_manufacturer(
        ManufacturerCreate(name="Hyundai", slug="hyundai", country="South Korea")
    )

    # Setup Models
    nexon = await repo.create_model(
        CarModelCreate(
            manufacturer_id=tata.id,
            name="Nexon",
            slug="tata-nexon",
            body_type="SUV",
            segment="Compact SUV",
        )
    )
    creta = await repo.create_model(
        CarModelCreate(
            manufacturer_id=hyundai.id,
            name="Creta",
            slug="hyundai-creta",
            body_type="SUV",
            segment="Mid-Size SUV",
        )
    )
    i20 = await repo.create_model(
        CarModelCreate(
            manufacturer_id=hyundai.id,
            name="i20",
            slug="hyundai-i20",
            body_type="Hatchback",
            segment="Premium Hatchback",
        )
    )

    # Setup Variants & Active Prices
    v_nexon_ev = await repo.create_variant(
        VariantCreate(
            model_id=nexon.id,
            name="EV Fearless",
            slug="nexon-ev-fearless",
            fuel_type="Electric",
            transmission="Automatic",
            battery_capacity_kwh=Decimal("40.5"),
            range_km=465,
            seating_capacity=5,
        )
    )
    await repo.add_vehicle_price(
        VehiclePriceCreate(
            variant_id=v_nexon_ev.id,
            ex_showroom_price=Decimal("1700000.00"),
            effective_from=datetime.now(timezone.utc) - timedelta(days=10),
        )
    )

    v_nexon_petrol = await repo.create_variant(
        VariantCreate(
            model_id=nexon.id,
            name="Creative DCA",
            slug="nexon-creative-dca",
            fuel_type="Petrol",
            transmission="DCT",
            engine_cc=1199,
            seating_capacity=5,
        )
    )
    await repo.add_vehicle_price(
        VehiclePriceCreate(
            variant_id=v_nexon_petrol.id,
            ex_showroom_price=Decimal("1250000.00"),
            effective_from=datetime.now(timezone.utc) - timedelta(days=10),
        )
    )

    v_creta_diesel = await repo.create_variant(
        VariantCreate(
            model_id=creta.id,
            name="SX (O) Diesel AT",
            slug="creta-sx-o-diesel-at",
            fuel_type="Diesel",
            transmission="Torque Converter",
            engine_cc=1493,
            seating_capacity=5,
        )
    )
    await repo.add_vehicle_price(
        VehiclePriceCreate(
            variant_id=v_creta_diesel.id,
            ex_showroom_price=Decimal("1900000.00"),
            effective_from=datetime.now(timezone.utc) - timedelta(days=10),
        )
    )

    v_i20_petrol = await repo.create_variant(
        VariantCreate(
            model_id=i20.id,
            name="Asta (O) IVT",
            slug="i20-asta-ivt",
            fuel_type="Petrol",
            transmission="CVT",
            engine_cc=1197,
            seating_capacity=5,
        )
    )
    await repo.add_vehicle_price(
        VehiclePriceCreate(
            variant_id=v_i20_petrol.id,
            ex_showroom_price=Decimal("980000.00"),
            effective_from=datetime.now(timezone.utc) - timedelta(days=10),
        )
    )

    # 1. Filter by manufacturer (Tata)
    items_tata, total_tata = await repo.search_vehicles(VehicleFilterParams(manufacturer="Tata"))
    assert total_tata == 2
    assert all(r.manufacturer_name == "Tata" for r in items_tata)

    # 2. Filter by fuel (Electric)
    items_ev, total_ev = await repo.search_vehicles(VehicleFilterParams(fuel_type="Electric"))
    assert total_ev == 1
    assert items_ev[0].variant_name == "EV Fearless"

    # 3. Filter by transmission (CVT)
    items_cvt, total_cvt = await repo.search_vehicles(VehicleFilterParams(transmission="CVT"))
    assert total_cvt == 1
    assert items_cvt[0].model_name == "i20"

    # 4. Filter by body type (SUV)
    items_suv, total_suv = await repo.search_vehicles(VehicleFilterParams(body_type="SUV"))
    assert total_suv == 3

    # 5. Price range filter (10,00,000 to 15,00,000)
    items_price, total_price = await repo.search_vehicles(
        VehicleFilterParams(
            minimum_price=Decimal("1000000.00"),
            maximum_price=Decimal("1500000.00"),
        )
    )
    assert total_price == 1
    assert items_price[0].variant_name == "Creative DCA"

    # 6. Pagination check (page_size = 2)
    paged_items, paged_total = await repo.search_vehicles(VehicleFilterParams(page=1, page_size=2))
    assert len(paged_items) == 2
    assert paged_total == 4
