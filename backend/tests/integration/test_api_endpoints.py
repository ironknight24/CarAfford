from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.seed import seed_database


@pytest.mark.asyncio
async def test_health_endpoint(async_client: AsyncClient):
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["app_name"] == "CarAfford"
    assert data["status"] in ["healthy", "degraded"]


@pytest.mark.asyncio
async def test_calculate_emi_endpoint(async_client: AsyncClient):
    payload = {
        "principal_amount": "1000000.00",
        "annual_interest_rate": "8.75",
        "tenure_months": 60,
    }
    response = await async_client.post(
        "/api/v1/finance/calculate-emi?generate_schedule=true", json=payload
    )
    assert response.status_code == 200
    res = response.json()
    assert res["success"] is True
    data = res["data"]
    assert Decimal(str(data["monthly_emi"])) == Decimal("20637.23")
    assert len(data["amortization_schedule"]) == 60


@pytest.mark.asyncio
async def test_loan_eligibility_endpoint(async_client: AsyncClient):
    payload = {
        "monthly_take_home_income": "120000.00",
        "existing_monthly_emis": "15000.00",
        "tenure_months": 60,
        "cibil_score": 780,
    }
    response = await async_client.post("/api/v1/finance/loan-eligibility", json=payload)
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["eligibility_status"] == "Eligible"
    assert Decimal(str(data["available_car_emi_budget"])) == Decimal("33000.00")


@pytest.mark.asyncio
async def test_full_seed_and_recommendations_flow(
    db_session: AsyncSession, async_client: AsyncClient
):
    # Seed data using in-memory test database session
    await seed_database(db_session)

    # 1. Fetch states
    states_resp = await async_client.get("/api/v1/locations/states")
    assert states_resp.status_code == 200
    states = states_resp.json()["data"]
    assert len(states) > 0
    delhi = next(s for s in states if s["code"] == "DL")

    # 2. Fetch vehicles
    veh_resp = await async_client.get("/api/v1/vehicles/variants")
    assert veh_resp.status_code == 200
    variants = veh_resp.json()["data"]
    assert len(variants) > 0

    # 3. Test on-road price calculation endpoint
    nexon_variant = variants[0]
    on_road_req = {
        "variant_id": nexon_variant["id"],
        "state_id": delhi["id"],
        "is_bh_series": False,
        "include_zero_dep_insurance": True,
        "is_financed": True,
    }
    on_road_resp = await async_client.post("/api/v1/pricing/on-road-breakdown", json=on_road_req)
    assert on_road_resp.status_code == 200
    on_road_data = on_road_resp.json()["data"]
    assert Decimal(str(on_road_data["on_road_price"])) > Decimal(
        str(on_road_data["ex_showroom_price"])
    )

    # 4. Test Car Recommendations Endpoint
    afford_req = {
        "monthly_take_home_income": "90000.00",
        "existing_monthly_emis": "5000.00",
        "available_down_payment": "200000.00",
        "state_id": delhi["id"],
        "desired_tenure_months": 60,
        "cibil_score": 760,
        "monthly_commute_km": 800,
    }
    rec_resp = await async_client.post("/api/v1/recommendations", json=afford_req)
    assert rec_resp.status_code == 200
    rec_data = rec_resp.json()["data"]
    assert len(rec_data["recommended_vehicles"]) > 0
    assert Decimal(str(rec_data["user_budget_summary"]["max_affordable_loan"])) > 0
    first_car = rec_data["recommended_vehicles"][0]
    assert first_car["affordability_score"] > 0
    assert Decimal(str(first_car["ownership_cost"]["total_monthly_tco"])) > 0
