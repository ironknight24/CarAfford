from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import Country, State, City
from app.models.tco import FuelPrice, ElectricityTariff, MaintenanceCostBenchmark
from app.models.vehicle import Manufacturer, CarModel, Variant
from app.models.pricing import VehiclePrice


@pytest.mark.asyncio
async def test_tco_ingestion_api_sources(async_client: AsyncClient):
    # Ingest all 5 TCO sources via API
    tco_sources = [
        "fuel_prices",
        "electricity_tariffs",
        "maintenance_costs",
        "insurance_data",
        "depreciation_data",
    ]
    for src in tco_sources:
        response = await async_client.post(
            "/api/v1/ingestion/runs",
            json={"dataset_name": src, "notes": f"API Test Run for {src}"},
        )
        assert response.status_code == 201, f"Failed for source {src}: {response.text}"
        data = response.json()["data"]
        assert data["status"] == "COMPLETED", f"Source {src} run failed: {data}"
        assert data["records_seen"] > 0
        assert data["error_count"] == 0


@pytest.mark.asyncio
async def test_tco_assumptions_api(async_client: AsyncClient):
    response = await async_client.get("/api/v1/tco/assumptions")
    assert response.status_code == 200
    res_data = response.json()["data"]
    assert "fuel_prices" in res_data
    assert "maintenance_rates" in res_data
    assert "insurance_renewal" in res_data
    assert "depreciation" in res_data
    assert "PETROL" in res_data["fuel_prices"]
    assert "ELECTRIC" in res_data["fuel_prices"]


@pytest.mark.asyncio
async def test_tco_location_specificity_and_economic_cost(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    # Ingest fuel prices first
    await async_client.post("/api/v1/ingestion/runs", json={"dataset_name": "fuel_prices"})

    # Setup Country and States
    c_res = await db_session.execute(select(Country).where(Country.iso_code == "IN"))
    country = c_res.scalars().first()
    if not country:
        country = Country(name="India", iso_code="IN", iso3_code="IND", active=True)
        db_session.add(country)
        await db_session.flush()

    # Karnataka
    ka_res = await db_session.execute(select(State).where(State.code == "KA"))
    ka_state = ka_res.scalars().first()
    if not ka_state:
        ka_state = State(name="Karnataka", code="KA", country_id=country.id, active=True)
        db_session.add(ka_state)
        await db_session.flush()

    blr_res = await db_session.execute(
        select(City).where(City.name == "Bengaluru", City.state_id == ka_state.id)
    )
    blr_city = blr_res.scalars().first()
    if not blr_city:
        blr_city = City(name="Bengaluru", slug="bengaluru", state_id=ka_state.id, active=True)
        db_session.add(blr_city)
        await db_session.flush()

    # Delhi
    dl_res = await db_session.execute(select(State).where(State.code == "DL"))
    dl_state = dl_res.scalars().first()
    if not dl_state:
        dl_state = State(name="Delhi", code="DL", country_id=country.id, active=True)
        db_session.add(dl_state)
        await db_session.flush()

    del_res = await db_session.execute(
        select(City).where(City.name == "Delhi", City.state_id == dl_state.id)
    )
    del_city = del_res.scalars().first()
    if not del_city:
        del_city = City(name="Delhi", slug="delhi", state_id=dl_state.id, active=True)
        db_session.add(del_city)
        await db_session.flush()

    await db_session.commit()

    # Calculate TCO for Bengaluru (KA)
    res_blr = await async_client.post(
        "/api/v1/tco/calculate",
        json={
            "state_id": ka_state.id,
            "city_id": blr_city.id,
            "fuel_type": "Petrol",
            "mileage_kmpl": 18.0,
            "annual_driving_distance_km": 12000,
            "custom_ex_showroom_price": 1000000.00,
            "custom_on_road_price": 1150000.00,
            "is_financed": True,
        },
    )
    assert res_blr.status_code == 200, res_blr.text
    blr_data = res_blr.json()["data"]
    assert Decimal(str(blr_data["driving_profile"]["fuel_price_per_unit"])) == Decimal("102.86")
    assert blr_data["driving_profile"]["location_match_level"] == "CITY"

    # Verify 1-year economic cost is strictly positive and non-negative
    pb_1yr = blr_data["periods"]["1_year"]
    assert Decimal(str(pb_1yr["estimated_economic_cost"])) > Decimal("0.00")
    assert Decimal(str(pb_1yr["estimated_economic_cost"])) < Decimal(
        str(pb_1yr["total_cash_outflow"])
    )

    # Calculate TCO for Delhi (DL)
    res_dl = await async_client.post(
        "/api/v1/tco/calculate",
        json={
            "state_id": dl_state.id,
            "city_id": del_city.id,
            "fuel_type": "Petrol",
            "mileage_kmpl": 18.0,
            "annual_driving_distance_km": 12000,
            "custom_ex_showroom_price": 1000000.00,
            "custom_on_road_price": 1150000.00,
            "is_financed": True,
        },
    )
    assert res_dl.status_code == 200, res_dl.text
    dl_data = res_dl.json()["data"]
    assert Decimal(str(dl_data["driving_profile"]["fuel_price_per_unit"])) == Decimal("94.72")
    assert dl_data["driving_profile"]["location_match_level"] == "CITY"

    # Bengaluru annual fuel cost should be higher than Delhi due to tax/fuel price difference
    assert Decimal(str(blr_data["operating_costs"]["annual_fuel_cost"])) > Decimal(
        str(dl_data["operating_costs"]["annual_fuel_cost"])
    )


@pytest.mark.asyncio
async def test_historical_fuel_prices_retention(
    async_client: AsyncClient,
    db_session: AsyncSession,
):
    # Ingest fuel prices
    await async_client.post("/api/v1/ingestion/runs", json={"dataset_name": "fuel_prices"})

    # Check that Bengaluru petrol has both 2026 and 2025 records preserved
    res = await db_session.execute(
        select(FuelPrice)
        .where(
            FuelPrice.fuel_type == "PETROL",
            FuelPrice.city_name == "Bengaluru",
        )
        .order_by(FuelPrice.observed_date.desc())
    )
    records = list(res.scalars().all())
    assert len(records) >= 2
    # Verify latest active is 102.86 and previous is 101.94
    assert records[0].price_per_unit == Decimal("102.86")
    assert records[0].is_active is True
    assert records[1].price_per_unit == Decimal("101.94")
