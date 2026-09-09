"""
Integration tests for Vehicle Catalogue REST APIs:
- GET /api/v1/manufacturers
- GET /api/v1/manufacturers/{id}
- GET /api/v1/models
- GET /api/v1/models/{id}
- GET /api/v1/variants
- GET /api/v1/variants/{id}
- GET /api/v1/vehicles/search (with filtering, pagination, sorting)
- 404 handling for non-existent entities
- 422 validation handling
"""

from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.seed import seed_database


@pytest.mark.asyncio
async def test_vehicle_catalogue_api_flow(db_session: AsyncSession, async_client: AsyncClient):
    # Seed the complete catalogue
    await seed_database(db_session)

    # 1. GET /api/v1/manufacturers
    mfg_resp = await async_client.get("/api/v1/manufacturers?page=1&page_size=20")
    assert mfg_resp.status_code == 200
    mfg_body = mfg_resp.json()
    mfgs = mfg_body["items"]
    assert len(mfgs) >= 10
    tata = next(m for m in mfgs if m["name"] == "Tata Motors")
    assert tata["slug"] == "tata-motors"
    assert tata["country"] == "India"
    assert tata["active"] is True

    # 2. GET /api/v1/manufacturers/{id}
    mfg_detail_resp = await async_client.get(f"/api/v1/manufacturers/{tata['id']}")
    assert mfg_detail_resp.status_code == 200
    mfg_detail = mfg_detail_resp.json()["data"]
    assert mfg_detail["id"] == tata["id"]
    assert mfg_detail["name"] == "Tata Motors"

    # 3. GET /api/v1/models (filter by manufacturer_id)
    models_resp = await async_client.get(f"/api/v1/models?manufacturer_id={tata['id']}")
    assert models_resp.status_code == 200
    models = models_resp.json()["items"]
    assert len(models) >= 2
    nexon = next(m for m in models if m["name"] == "Nexon")
    assert nexon["body_type"] == "SUV"
    assert nexon["segment"] == "Compact SUV"
    assert nexon["manufacturer_id"] == tata["id"]

    # 4. GET /api/v1/models/{id}
    model_detail_resp = await async_client.get(f"/api/v1/models/{nexon['id']}")
    assert model_detail_resp.status_code == 200
    model_detail = model_detail_resp.json()["data"]
    assert model_detail["id"] == nexon["id"]
    assert model_detail["manufacturer"]["name"] == "Tata Motors"

    # 5. GET /api/v1/variants (filter by model_id)
    variants_resp = await async_client.get(f"/api/v1/variants?model_id={nexon['id']}")
    assert variants_resp.status_code == 200
    variants = variants_resp.json()["items"]
    assert len(variants) >= 3
    nexon_ev = next(v for v in variants if v["fuel_type"] == "Electric")
    assert nexon_ev["battery_capacity_kwh"] is not None
    assert nexon_ev["engine_cc"] is None

    # 6. GET /api/v1/variants/{id}
    variant_detail_resp = await async_client.get(f"/api/v1/variants/{nexon_ev['id']}")
    assert variant_detail_resp.status_code == 200
    v_detail = variant_detail_resp.json()["data"]
    assert v_detail["id"] == nexon_ev["id"]
    assert v_detail["current_price"] is not None
    assert Decimal(str(v_detail["current_price"]["ex_showroom_price"])) > 0
    assert v_detail["model"]["name"] == "Nexon"

    # 7. GET /api/v1/vehicles/search with multiple query parameters
    search_resp = await async_client.get(
        "/api/v1/vehicles/search"
        "?manufacturer=Tata"
        "&fuel_type=Electric"
        "&minimum_price=1000000"
        "&maximum_price=2500000"
        "&page=1"
        "&page_size=10"
    )
    assert search_resp.status_code == 200
    search_data = search_resp.json()
    assert search_data["total"] >= 1
    for item in search_data["items"]:
        assert "Tata" in item["manufacturer_name"]
        assert item["fuel_type"] == "Electric"
        assert item["current_ex_showroom_price"] is not None
        assert Decimal("1000000") <= Decimal(str(item["current_ex_showroom_price"])) <= Decimal("2500000")

    # 8. Test 404 handling
    resp_404_mfg = await async_client.get("/api/v1/manufacturers/999999")
    assert resp_404_mfg.status_code == 404

    resp_404_model = await async_client.get("/api/v1/models/999999")
    assert resp_404_model.status_code == 404

    resp_404_variant = await async_client.get("/api/v1/variants/999999")
    assert resp_404_variant.status_code == 404

    # 9. Test 422 validation on invalid query params
    resp_422 = await async_client.get("/api/v1/vehicles/search?page=0")
    assert resp_422.status_code == 422
