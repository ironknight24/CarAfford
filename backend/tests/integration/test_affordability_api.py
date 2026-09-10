import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.seed import seed_database
from app.models.location import State, City
from app.models.vehicle import Variant


@pytest.mark.asyncio
async def test_affordability_api_complete_flows(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    # 1. Ensure seed data
    await seed_database(db_session)

    # Resolve active state and variant from database dynamically
    state = (await db_session.execute(select(State).where(State.code == "KA"))).scalars().first()
    assert state is not None

    city = (
        (await db_session.execute(select(City).where(City.state_id == state.id))).scalars().first()
    )
    variant = (
        (await db_session.execute(select(Variant).where(Variant.active == True))).scalars().first()
    )
    assert variant is not None

    # 2. Test GET /api/v1/affordability/profiles
    profiles_resp = await async_client.get("/api/v1/affordability/profiles")
    assert profiles_resp.status_code == 200
    profiles = profiles_resp.json()["data"]
    assert len(profiles) == 3
    profile_codes = [p["code"] for p in profiles]
    assert "CONSERVATIVE" in profile_codes
    assert "BALANCED" in profile_codes
    assert "STRETCH" in profile_codes

    # 3. Test POST /api/v1/affordability/calculate
    calc_payload = {
        "monthly_take_home_income": 100000,
        "existing_monthly_emi": 10000,
        "available_down_payment": 200000,
        "state_id": state.id,
        "city_id": city.id if city else None,
        "credit_score": 750,
        "preferred_loan_tenure_months": 60,
        "affordability_profile": "BALANCED",
    }
    calc_resp = await async_client.post("/api/v1/affordability/calculate", json=calc_payload)
    assert calc_resp.status_code == 200
    calc_data = calc_resp.json()["data"]

    assert float(calc_data["monthly_take_home_income"]) == 100000.0
    assert float(calc_data["existing_monthly_emi"]) == 10000.0
    assert float(calc_data["maximum_total_emi"]) == 35000.0
    assert float(calc_data["available_car_emi"]) == 25000.0
    assert float(calc_data["available_down_payment"]) == 200000.0
    assert float(calc_data["maximum_affordable_loan"]) > 1000000.0
    assert (
        float(calc_data["maximum_affordable_on_road_price"])
        == float(calc_data["maximum_affordable_loan"]) + 200000.0
    )
    assert calc_data["data_status"] == "DEMO"
    assert "disclaimer" in calc_data
    assert calc_data["limiting_factor"] in ["EMI_CAP", "LOAN_MAXIMUM"]

    # 4. Test POST /api/v1/affordability/vehicle
    veh_payload = {
        "variant_id": variant.id,
        "monthly_take_home_income": 120000,
        "existing_monthly_emi": 5000,
        "available_down_payment": 250000,
        "state_id": state.id,
        "city_id": city.id if city else None,
        "credit_score": 780,
        "preferred_loan_tenure_months": 60,
        "affordability_profile": "BALANCED",
    }
    veh_resp = await async_client.post("/api/v1/affordability/vehicle", json=veh_payload)
    assert veh_resp.status_code == 200
    veh_data = veh_resp.json()["data"]

    assert veh_data["variant_id"] == variant.id
    assert float(veh_data["on_road_price"]) > 0
    assert float(veh_data["down_payment"]) == 250000.0
    assert float(veh_data["estimated_emi"]) > 0
    assert veh_data["affordability_status"] in [
        "COMFORTABLE",
        "AFFORDABLE",
        "STRETCH",
        "NOT_AFFORDABLE",
    ]
    assert "data_status" in veh_data
    assert veh_data["data_status"] == "DEMO"

    # 5. Test POST /api/v1/affordability/vehicles (batch evaluation)
    variants_all = (
        (await db_session.execute(select(Variant).where(Variant.active == True))).scalars().all()
    )
    variant_ids = [v.id for v in variants_all[:3]]
    batch_payload = {
        "variant_ids": variant_ids,
        "monthly_take_home_income": 120000,
        "existing_monthly_emi": 5000,
        "available_down_payment": 200000,
        "state_id": state.id,
        "credit_score": 750,
        "preferred_loan_tenure_months": 60,
        "affordability_profile": "BALANCED",
    }
    batch_resp = await async_client.post("/api/v1/affordability/vehicles", json=batch_payload)
    assert batch_resp.status_code == 200
    batch_data = batch_resp.json()["data"]
    assert batch_data["total_evaluated"] == len(variant_ids)
    assert len(batch_data["results"]) == len(variant_ids)

    # 6. Test POST /api/v1/affordability/compare
    compare_payload = {
        "variant_ids": variant_ids[:2],
        "monthly_take_home_income": 150000,
        "existing_monthly_emi": 10000,
        "available_down_payment": 300000,
        "state_id": state.id,
        "credit_score": 750,
        "preferred_loan_tenure_months": 60,
        "affordability_profile": "BALANCED",
    }
    compare_resp = await async_client.post("/api/v1/affordability/compare", json=compare_payload)
    assert compare_resp.status_code == 200
    compare_data = compare_resp.json()["data"]
    assert len(compare_data["vehicles"]) == 2
    assert len(compare_data["comparison_notes"]) > 0

    # 7. Error cases
    # Invalid State ID -> 404
    err_state = {**calc_payload, "state_id": 999999}
    err_resp1 = await async_client.post("/api/v1/affordability/calculate", json=err_state)
    assert err_resp1.status_code == 404

    # Invalid Variant ID -> 404
    err_variant = {**veh_payload, "variant_id": 999999}
    err_resp2 = await async_client.post("/api/v1/affordability/vehicle", json=err_variant)
    assert err_resp2.status_code == 404

    # Negative income -> 422
    err_inc = {**calc_payload, "monthly_take_home_income": -50000}
    err_resp3 = await async_client.post("/api/v1/affordability/calculate", json=err_inc)
    assert err_resp3.status_code == 422
