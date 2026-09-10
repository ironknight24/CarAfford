"""
Integration tests for Location Domain REST APIs:
- GET /api/v1/countries
- GET /api/v1/countries/{id}
- GET /api/v1/states
- GET /api/v1/states/{id}
- GET /api/v1/states/{state_id}/cities
- GET /api/v1/states/{state_id}/rtos
- GET /api/v1/cities
- GET /api/v1/cities/{id}
- GET /api/v1/cities/{city_id}/rtos
- GET /api/v1/rtos
- GET /api/v1/rtos/{id}
- GET /api/v1/locations/search
- 404 and 422 error handling
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.seed import seed_database


@pytest.mark.asyncio
async def test_location_domain_api_flow(db_session: AsyncSession, async_client: AsyncClient):
    # Seed the complete catalogue and location data
    await seed_database(db_session)

    # 1. GET /api/v1/countries
    countries_resp = await async_client.get("/api/v1/countries?page=1&page_size=10")
    assert countries_resp.status_code == 200
    c_body = countries_resp.json()
    assert len(c_body["items"]) >= 1
    india = next(c for c in c_body["items"] if c["iso_code"] == "IN")
    assert india["name"] == "India"
    assert india["iso3_code"] == "IND"

    # 2. GET /api/v1/countries/{id}
    c_detail_resp = await async_client.get(f"/api/v1/countries/{india['id']}")
    assert c_detail_resp.status_code == 200
    c_detail = c_detail_resp.json()["data"]
    assert c_detail["id"] == india["id"]
    assert c_detail["states_count"] >= 8

    # 3. GET /api/v1/states
    states_resp = await async_client.get("/api/v1/states?page=1&page_size=50")
    assert states_resp.status_code == 200
    states_body = states_resp.json()
    states = states_body["items"]
    assert len(states) >= 10
    karnataka = next(s for s in states if s["code"] == "KA")
    assert karnataka["name"] == "Karnataka"
    assert karnataka["region_type"] == "STATE"
    assert karnataka["is_ut"] is False

    delhi = next(s for s in states if s["code"] == "DL")
    assert delhi["name"] == "Delhi"
    assert delhi["region_type"] == "UNION_TERRITORY"
    assert delhi["is_ut"] is True

    # 4. GET /api/v1/states/{id}
    st_detail_resp = await async_client.get(f"/api/v1/states/{karnataka['id']}")
    assert st_detail_resp.status_code == 200
    st_detail = st_detail_resp.json()["data"]
    assert st_detail["id"] == karnataka["id"]
    assert st_detail["cities_count"] >= 1
    assert st_detail["rtos_count"] >= 1

    # 5. GET /api/v1/states/{state_id}/cities
    ka_cities_resp = await async_client.get(f"/api/v1/states/{karnataka['id']}/cities")
    assert ka_cities_resp.status_code == 200
    ka_cities = ka_cities_resp.json()["data"]
    assert len(ka_cities) >= 1
    bengaluru = next(c for c in ka_cities if c["slug"] == "bengaluru")
    assert bengaluru["name"] == "Bengaluru"
    assert bengaluru["state_id"] == karnataka["id"]

    # 6. GET /api/v1/states/{state_id}/rtos
    ka_rtos_resp = await async_client.get(f"/api/v1/states/{karnataka['id']}/rtos")
    assert ka_rtos_resp.status_code == 200
    ka_rtos = ka_rtos_resp.json()["data"]
    assert len(ka_rtos) >= 5
    ka01 = next(r for r in ka_rtos if r["code"] == "KA-01")
    assert "Koramangala" in ka01["name"]

    # 7. GET /api/v1/cities/{id}
    city_detail_resp = await async_client.get(f"/api/v1/cities/{bengaluru['id']}")
    assert city_detail_resp.status_code == 200
    city_detail = city_detail_resp.json()["data"]
    assert city_detail["id"] == bengaluru["id"]
    assert len(city_detail["rtos"]) >= 5

    # 8. GET /api/v1/cities/{city_id}/rtos
    blr_rtos_resp = await async_client.get(f"/api/v1/cities/{bengaluru['id']}/rtos")
    assert blr_rtos_resp.status_code == 200
    blr_rtos = blr_rtos_resp.json()["data"]
    assert len(blr_rtos) >= 5
    rto_codes = [r["code"] for r in blr_rtos]
    assert "KA-01" in rto_codes
    assert "KA-02" in rto_codes
    assert "KA-03" in rto_codes

    # 9. GET /api/v1/rtos/{id}
    rto_detail_resp = await async_client.get(f"/api/v1/rtos/{ka01['id']}")
    assert rto_detail_resp.status_code == 200
    rto_detail = rto_detail_resp.json()["data"]
    assert rto_detail["id"] == ka01["id"]
    assert rto_detail["code"] == "KA-01"
    assert rto_detail["state"]["name"] == "Karnataka"
    assert rto_detail["city"]["name"] == "Bengaluru"

    # 10. GET /api/v1/locations/search
    search_resp = await async_client.get("/api/v1/locations/search?q=Bengaluru")
    assert search_resp.status_code == 200
    search_data = search_resp.json()["data"]
    assert len(search_data) >= 1
    assert any(
        item["city_name"] == "Bengaluru" or (item["rto_name"] and "Bengaluru" in item["rto_name"])
        for item in search_data
    )

    # Search by state code e.g. "MH"
    search_mh = await async_client.get("/api/v1/locations/search?q=MH")
    assert search_mh.status_code == 200
    assert len(search_mh.json()["data"]) >= 1

    # 11. 404 Error handling
    assert (await async_client.get("/api/v1/countries/999999")).status_code == 404
    assert (await async_client.get("/api/v1/states/999999")).status_code == 404
    assert (await async_client.get("/api/v1/cities/999999")).status_code == 404
    assert (await async_client.get("/api/v1/rtos/999999")).status_code == 404

    # 12. 422 Error handling for empty search query
    assert (await async_client.get("/api/v1/locations/search?q=")).status_code == 422


@pytest.mark.asyncio
async def test_location_selector_cascade_contract(
    db_session: AsyncSession, async_client: AsyncClient
):
    """Verifies that the API supports the frontend State -> City -> RTO selection cascade

    without assuming any hardcoded state ID:
    - Initial state list fetches all states with dynamic IDs.
    - Selecting a real state ID returns its cities and RTOs.
    - Selecting a real city ID returns city-specific RTOs.
    - Invalid or non-existent IDs return 404.
    """
    await seed_database(db_session)

    # 1. Frontend initial load: /locations/states or /states
    states_resp = await async_client.get("/api/v1/locations/states")
    assert states_resp.status_code == 200
    states = states_resp.json()["data"]
    assert len(states) == 36

    # Verify no assumption of state ID 1: dynamic state resolution
    mh_state = next((s for s in states if s["code"] == "MH"), None)
    assert mh_state is not None
    real_state_id = mh_state["id"]

    # 2. State selected -> fetch cities
    cities_resp = await async_client.get(f"/api/v1/states/{real_state_id}/cities")
    assert cities_resp.status_code == 200
    cities = cities_resp.json()["data"]
    assert len(cities) >= 2  # Mumbai, Pune, Nagpur
    mumbai = next((c for c in cities if c["slug"] == "mumbai"), None)
    assert mumbai is not None
    real_city_id = mumbai["id"]

    # 3. State selected -> fetch state-level RTOs
    state_rtos_resp = await async_client.get(f"/api/v1/states/{real_state_id}/rtos")
    assert state_rtos_resp.status_code == 200
    state_rtos = state_rtos_resp.json()["data"]
    assert len(state_rtos) >= 5  # MH-01, MH-02, MH-03, MH-47, MH-12, MH-14

    # 4. City selected -> fetch city-specific RTOs
    city_rtos_resp = await async_client.get(f"/api/v1/cities/{real_city_id}/rtos")
    assert city_rtos_resp.status_code == 200
    city_rtos = city_rtos_resp.json()["data"]
    assert len(city_rtos) == 4  # Mumbai RTOs: MH-01, MH-02, MH-03, MH-47
    mumbai_codes = {r["code"] for r in city_rtos}
    assert "MH-01" in mumbai_codes
    assert "MH-12" not in mumbai_codes  # Pune Central should not be in Mumbai

    # 5. Non-existent state ID returns 404 (e.g. state ID 999999)
    bad_cities = await async_client.get("/api/v1/states/999999/cities")
    assert bad_cities.status_code == 404
    bad_rtos = await async_client.get("/api/v1/states/999999/rtos")
    assert bad_rtos.status_code == 404
