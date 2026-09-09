from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed import seed_database
from app.models.location import State
from app.models.vehicle import Variant


@pytest.mark.asyncio
async def test_get_scoring_config_api(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """GET /api/v1/recommendations/scoring-config returns weights and category definitions."""
    resp = await async_client.get("/api/v1/recommendations/scoring-config")
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["success"] is True
    data = json_data["data"]
    assert "weights" in data
    assert "affordability_weight" in data["weights"]
    assert "tco_weight" in data["weights"]
    assert "categories" in data
    assert "BEST_OVERALL" in data["categories"]
    assert data["data_status"] == "DEMO"


@pytest.mark.asyncio
async def test_main_recommendations_api_flow(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """POST /api/v1/recommendations executes end-to-end filtering, pricing, affordability, TCO, and ranking."""
    await seed_database(db_session)
    state = (await db_session.execute(select(State).limit(1))).scalars().first()

    payload = {
        "monthly_take_home_income": 120000,
        "existing_monthly_emi": 15000,
        "available_down_payment": 250000,
        "state_id": state.id,
        "credit_score": 750,
        "preferred_loan_tenure_months": 60,
        "affordability_profile": "BALANCED",
        "annual_driving_distance_km": 15000,
        "fuel_preference": "Petrol",
        "limit": 5,
    }
    resp = await async_client.post("/api/v1/recommendations", json=payload)
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["success"] is True
    data = json_data["data"]

    assert len(data["recommendations"]) > 0
    assert len(data["recommendations"]) <= 5
    first_rec = data["recommendations"][0]
    assert first_rec["rank"] == 1
    assert float(first_rec["score"]) > 0
    assert "reasons" in first_rec
    assert len(first_rec["reasons"]) > 0
    assert "vehicle" in first_rec
    assert "affordability" in first_rec
    assert "tco" in first_rec
    assert data["data_status"] == "DEMO"


@pytest.mark.asyncio
async def test_quick_recommendations_api(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """POST /api/v1/recommendations/quick returns recommendations with minimal input."""
    await seed_database(db_session)
    state = (await db_session.execute(select(State).limit(1))).scalars().first()

    payload = {
        "monthly_take_home_income": 100000,
        "existing_monthly_emi": 10000,
        "available_down_payment": 200000,
        "state_id": state.id,
        "credit_score": 750,
    }
    resp = await async_client.post("/api/v1/recommendations/quick", json=payload)
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["success"] is True
    assert len(json_data["data"]["recommendations"]) > 0


@pytest.mark.asyncio
async def test_compare_recommendations_api(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """POST /api/v1/recommendations/compare ranks explicit variants."""
    await seed_database(db_session)
    state = (await db_session.execute(select(State).limit(1))).scalars().first()
    variants = (await db_session.execute(select(Variant).limit(2))).scalars().all()

    payload = {
        "variant_ids": [v.id for v in variants],
        "monthly_take_home_income": 150000,
        "existing_monthly_emi": 10000,
        "available_down_payment": 250000,
        "state_id": state.id,
    }
    resp = await async_client.post("/api/v1/recommendations/compare", json=payload)
    assert resp.status_code == 200
    json_data = resp.json()
    assert json_data["success"] is True
    assert len(json_data["data"]["ranked_vehicles"]) == len(variants)
