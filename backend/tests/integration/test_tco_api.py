from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed import seed_database
from app.models.location import State
from app.models.vehicle import Variant


@pytest.mark.asyncio
async def test_get_tco_assumptions_api(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """GET /api/v1/tco/assumptions returns configured fuel, maintenance, insurance, and depreciation benchmarks."""
    resp = await async_client.get("/api/v1/tco/assumptions")
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["success"] is True
    data = json_data["data"]
    assert "fuel_prices" in data
    assert "PETROL" in data["fuel_prices"]
    assert "ELECTRIC" in data["fuel_prices"]
    assert "maintenance_rates" in data
    assert "insurance_renewal" in data
    assert "depreciation" in data
    assert data["data_status"] == "DEMO"


@pytest.mark.asyncio
async def test_calculate_tco_api_flow(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """POST /api/v1/tco/calculate executes full multi-term ownership calculation."""
    await seed_database(db_session)
    state = (await db_session.execute(select(State).limit(1))).scalars().first()
    variant = (await db_session.execute(select(Variant).limit(1))).scalars().first()

    payload = {
        "variant_id": variant.id,
        "state_id": state.id,
        "annual_driving_distance_km": 15000,
        "down_payment": 250000,
        "credit_score": 780,
        "preferred_loan_tenure_months": 60,
        "is_financed": True,
    }
    resp = await async_client.post("/api/v1/tco/calculate", json=payload)
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["success"] is True
    data = json_data["data"]

    assert data["vehicle"]["variant_id"] == variant.id
    assert data["location"]["state_id"] == state.id
    assert float(data["initial_cost"]["total_on_road_price"]) > 0
    assert float(data["driving_profile"]["annual_distance_km"]) == 15000.0
    assert "1_year" in data["periods"]
    assert "3_years" in data["periods"]
    assert "5_years" in data["periods"]
    assert data["data_status"] == "DEMO"


@pytest.mark.asyncio
async def test_vehicle_tco_endpoint(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """POST /api/v1/tco/vehicle calculates vehicle-specific TCO."""
    await seed_database(db_session)
    state = (await db_session.execute(select(State).limit(1))).scalars().first()
    variant = (await db_session.execute(select(Variant).limit(1))).scalars().first()

    payload = {
        "variant_id": variant.id,
        "state_id": state.id,
        "monthly_driving_distance_km": 1000,
        "down_payment": 150000,
        "credit_score": 750,
        "preferred_loan_tenure_months": 48,
    }
    resp = await async_client.post("/api/v1/tco/vehicle", json=payload)
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["success"] is True
    assert json_data["data"]["periods"]["5_years"]["period_months"] == 60


@pytest.mark.asyncio
async def test_compare_tco_endpoint(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """POST /api/v1/tco/compare ranks multiple vehicle variants on 5-year TCO."""
    await seed_database(db_session)
    state = (await db_session.execute(select(State).limit(1))).scalars().first()
    variants = (await db_session.execute(select(Variant).limit(2))).scalars().all()

    payload = {
        "variant_ids": [v.id for v in variants],
        "state_id": state.id,
        "annual_driving_distance_km": 12000,
        "down_payment": 200000,
    }
    resp = await async_client.post("/api/v1/tco/compare", json=payload)
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["success"] is True
    assert len(json_data["data"]["compared_vehicles"]) == len(variants)
