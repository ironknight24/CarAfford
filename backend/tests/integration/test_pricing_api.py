"""
Integration tests for On-Road Pricing REST API endpoints:
- POST /api/v1/pricing/on-road
- GET /api/v1/pricing/on-road/{variant_id}
- POST /api/v1/pricing/on-road-breakdown (backward compatibility)
- GET /api/v1/pricing/history/{variant_id}
"""

from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed import seed_database


@pytest.mark.asyncio
async def test_on_road_pricing_api_flows(db_session: AsyncSession, async_client: AsyncClient):
    # 1. Seed full database
    await seed_database(db_session)

    # 2. Get states and variants
    states_resp = await async_client.get("/api/v1/states")
    assert states_resp.status_code == 200
    states = states_resp.json()["items"]
    ka_state = next(s for s in states if s["code"] == "KA")
    dl_state = next(s for s in states if s["code"] == "DL")

    # Fetch Bangalore city and KA-01 RTO
    cities_resp = await async_client.get(f"/api/v1/states/{ka_state['id']}/cities")
    assert cities_resp.status_code == 200
    blr_city = next(c for c in cities_resp.json()["data"] if c["slug"] == "bengaluru")

    rtos_resp = await async_client.get(f"/api/v1/cities/{blr_city['id']}/rtos")
    assert rtos_resp.status_code == 200
    ka01_rto = next(r for r in rtos_resp.json()["data"] if r["code"] == "KA-01")

    # Fetch a variant (e.g. Tata Nexon Fearless Plus)
    variants_resp = await async_client.get("/api/v1/variants?limit=10")
    assert variants_resp.status_code == 200
    variants = variants_resp.json()["items"]
    test_variant = variants[0]
    variant_id = test_variant["id"]

    # 3. Test POST /api/v1/pricing/on-road
    payload = {
        "variant_id": variant_id,
        "state_id": ka_state["id"],
        "city_id": blr_city["id"],
        "rto_id": ka01_rto["id"],
        "insurance_option": "ZERO_DEP",
        "is_bh_series": False,
        "is_financed": True,
    }
    calc_resp = await async_client.post("/api/v1/pricing/on-road", json=payload)
    assert calc_resp.status_code == 200
    data = calc_resp.json()["data"]

    assert data["vehicle"]["variant_id"] == variant_id
    assert data["location"]["state_id"] == ka_state["id"]
    assert data["location"]["city_id"] == blr_city["id"]
    assert data["location"]["rto_id"] == ka01_rto["id"]
    assert Decimal(str(data["totals"]["on_road_price"])) > Decimal(
        str(data["totals"]["ex_showroom_price"])
    )
    assert len(data["breakdown"]) >= 4
    assert data["data_quality"]["data_status"] == "DEMO"

    # 4. Test GET /api/v1/pricing/on-road/{variant_id}
    get_resp = await async_client.get(
        f"/api/v1/pricing/on-road/{variant_id}?state_id={ka_state['id']}&city_id={blr_city['id']}&rto_id={ka01_rto['id']}"
    )
    assert get_resp.status_code == 200
    get_data = get_resp.json()["data"]
    assert get_data["totals"]["on_road_price"] == data["totals"]["on_road_price"]

    # 5. Test Legacy POST /api/v1/pricing/on-road-breakdown
    legacy_payload = {
        "variant_id": variant_id,
        "state_id": ka_state["id"],
        "city_id": blr_city["id"],
        "include_zero_dep_insurance": True,
        "is_bh_series": False,
        "is_financed": True,
    }
    legacy_resp = await async_client.post("/api/v1/pricing/on-road-breakdown", json=legacy_payload)
    assert legacy_resp.status_code == 200
    legacy_data = legacy_resp.json()["data"]
    assert legacy_data["variant_id"] == variant_id
    assert Decimal(str(legacy_data["on_road_price"])) == Decimal(
        str(data["totals"]["on_road_price"])
    )

    # 6. Test GET /api/v1/pricing/history/{variant_id}
    hist_resp = await async_client.get(f"/api/v1/pricing/history/{variant_id}")
    assert hist_resp.status_code == 200
    hist_data = hist_resp.json()["data"]
    assert isinstance(hist_data, list)


@pytest.mark.asyncio
async def test_on_road_pricing_error_cases(db_session: AsyncSession, async_client: AsyncClient):
    await seed_database(db_session)

    states_resp = await async_client.get("/api/v1/states")
    ka_state = next(s for s in states_resp.json()["items"] if s["code"] == "KA")
    dl_state = next(s for s in states_resp.json()["items"] if s["code"] == "DL")

    cities_resp = await async_client.get(f"/api/v1/states/{dl_state['id']}/cities")
    delhi_city = cities_resp.json()["data"][0]

    # Non-existent variant (404)
    resp_404 = await async_client.post(
        "/api/v1/pricing/on-road",
        json={"variant_id": 999999, "state_id": ka_state["id"]},
    )
    assert resp_404.status_code == 404

    # Mismatched location hierarchy (422)
    resp_422 = await async_client.post(
        "/api/v1/pricing/on-road",
        json={"variant_id": 1, "state_id": ka_state["id"], "city_id": delhi_city["id"]},
    )
    assert resp_422.status_code == 422
