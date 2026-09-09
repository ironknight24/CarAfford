"""
Integration tests for Tax & Registration Rules Domain REST APIs:
- GET /api/v1/tax-rules (listing and filters)
- GET /api/v1/tax-rules/{id} (detail)
- GET /api/v1/tax-rules/resolve (deterministic rule resolution across states, fuels, vehicles, dates)
- POST /api/v1/tax-rules/validate (rule validation checks)
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed import seed_database


@pytest.mark.asyncio
async def test_tax_rules_api_flow(db_session: AsyncSession, async_client: AsyncClient):
    # 1. Seed complete catalogue, location, and statutory tax rules
    await seed_database(db_session)

    # 2. GET /api/v1/tax-rules
    list_resp = await async_client.get("/api/v1/tax-rules?skip=0&limit=50")
    assert list_resp.status_code == 200
    list_body = list_resp.json()
    assert list_body["total"] >= 20
    assert len(list_body["items"]) >= 20

    first_rule = list_body["items"][0]
    assert "id" in first_rule
    assert "name" in first_rule
    assert "tax_type" in first_rule

    # 3. GET /api/v1/tax-rules/{id}
    detail_resp = await async_client.get(f"/api/v1/tax-rules/{first_rule['id']}")
    assert detail_resp.status_code == 200
    detail_body = detail_resp.json()
    assert detail_body["id"] == first_rule["id"]
    assert "state" in detail_body

    # 4. Resolve rules for Karnataka - Petrol Vehicle (e.g. ₹12,50,000 ex-showroom)
    states_resp = await async_client.get("/api/v1/states")
    states = states_resp.json()["items"]
    ka_state = next(s for s in states if s["code"] == "KA")
    dl_state = next(s for s in states if s["code"] == "DL")
    mh_state = next(s for s in states if s["code"] == "MH")

    # Fetch Bangalore city and KA-01 RTO
    cities_resp = await async_client.get(f"/api/v1/states/{ka_state['id']}/cities")
    cities = cities_resp.json()["data"]
    blr_city = next(c for c in cities if c["slug"] == "bengaluru")

    rtos_resp = await async_client.get(f"/api/v1/cities/{blr_city['id']}/rtos")
    rtos = rtos_resp.json()["data"]
    ka01_rto = next(r for r in rtos if r["code"] == "KA-01")

    # 5. Resolve endpoint for Bengaluru, KA-01, Petrol ₹12,50,000
    resolve_resp = await async_client.get(
        f"/api/v1/tax-rules/resolve?state_id={ka_state['id']}&city_id={blr_city['id']}&rto_id={ka01_rto['id']}"
        f"&fuel_type=Petrol&ex_showroom_price=1250000.00&is_ev=false&is_financed=true"
    )
    assert resolve_resp.status_code == 200
    resolve_data = resolve_resp.json()
    assert resolve_data["location"]["state_code"] == "KA"
    assert resolve_data["location"]["city_name"] == "Bengaluru"
    assert resolve_data["location"]["rto_code"] == "KA-01"
    assert resolve_data["vehicle"]["fuel_type"] == "Petrol"
    assert Decimal(str(resolve_data["vehicle"]["ex_showroom_price"])) == Decimal("1250000.00")

    rule_tax_types = {r["tax_type"]: r for r in resolve_data["rules"]}
    assert "ROAD_TAX" in rule_tax_types
    assert "CESS" in rule_tax_types
    assert "REGISTRATION_FEE" in rule_tax_types
    assert "SMART_CARD_FEE" in rule_tax_types
    assert "HYPOTHECATION_FEE" in rule_tax_types
    assert "FASTAG_FEE" in rule_tax_types

    # Karnataka bracketed road tax has 4 brackets
    road_tax_rule = rule_tax_types["ROAD_TAX"]
    assert road_tax_rule["calculation_method"] == "BRACKETED"
    assert len(road_tax_rule["brackets"]) == 4

    # 6. Resolve endpoint for Karnataka - Electric Vehicle (EV)
    ev_resolve_resp = await async_client.get(
        f"/api/v1/tax-rules/resolve?state_id={ka_state['id']}&city_id={blr_city['id']}&rto_id={ka01_rto['id']}"
        f"&fuel_type=Electric&ex_showroom_price=1500000.00&is_ev=true&is_financed=false"
    )
    assert ev_resolve_resp.status_code == 200
    ev_resolve_data = ev_resolve_resp.json()
    ev_tax_types = {r["tax_type"]: r for r in ev_resolve_data["rules"]}
    assert "ROAD_TAX" in ev_tax_types
    assert Decimal(str(ev_tax_types["ROAD_TAX"]["fixed_amount"])) == Decimal("0.00")
    # Hypothecation fee should NOT be present when is_financed=false
    assert "HYPOTHECATION_FEE" not in ev_tax_types

    # 7. Resolve endpoint for Delhi - Diesel
    dl_resolve_resp = await async_client.get(
        f"/api/v1/tax-rules/resolve?state_id={dl_state['id']}&fuel_type=Diesel&ex_showroom_price=1500000.00&is_ev=false"
    )
    assert dl_resolve_resp.status_code == 200
    dl_data = dl_resolve_resp.json()
    dl_road_tax = next(r for r in dl_data["rules"] if r["tax_type"] == "ROAD_TAX")
    assert dl_road_tax["calculation_method"] == "BRACKETED"

    # 8. POST /api/v1/tax-rules/validate endpoint
    val_resp = await async_client.post(
        "/api/v1/tax-rules/validate",
        json={
            "name": "Test Valid Rule",
            "state_id": ka_state["id"],
            "tax_type": "ROAD_TAX",
            "calculation_method": "PERCENTAGE",
            "rate": 10.0,
            "effective_from": "2026-01-01T00:00:00Z",
        },
    )
    assert val_resp.status_code == 200
    val_data = val_resp.json()
    assert val_data["is_valid"] is True

    # 9. Error handling: invalid state_id
    err_resp = await async_client.get("/api/v1/tax-rules/resolve?state_id=999999")
    assert err_resp.status_code == 422
