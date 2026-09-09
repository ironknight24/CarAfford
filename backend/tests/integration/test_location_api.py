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
    assert any(item["city_name"] == "Bengaluru" or (item["rto_name"] and "Bengaluru" in item["rto_name"]) for item in search_data)

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
