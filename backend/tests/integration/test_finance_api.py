"""
Integration tests for Bank and Car Loan Financing REST API endpoints:
- GET /api/v1/finance/banks
- GET /api/v1/finance/banks/{id}
- GET /api/v1/finance/loan-products
- GET /api/v1/finance/loan-products/{id}
- GET /api/v1/finance/rates
- POST /api/v1/finance/emi
- POST /api/v1/finance/max-loan
- POST /api/v1/finance/amortization
- POST /api/v1/finance/calculate
- POST /api/v1/finance/compare
"""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed import seed_database


@pytest.mark.asyncio
async def test_finance_api_flows(db_session: AsyncSession, async_client: AsyncClient):
    # 1. Seed database with vehicles, locations, taxes, and banks
    await seed_database(db_session)

    # 2. Test GET /api/v1/finance/banks
    banks_resp = await async_client.get("/api/v1/finance/banks")
    assert banks_resp.status_code == 200
    banks = banks_resp.json()["items"]
    assert len(banks) >= 6
    sbi = next(b for b in banks if b["slug"] == "sbi")
    assert sbi["name"] == "State Bank of India (SBI)"

    # Test GET /api/v1/finance/banks/{id}
    bank_detail_resp = await async_client.get(f"/api/v1/finance/banks/{sbi['id']}")
    assert bank_detail_resp.status_code == 200
    assert bank_detail_resp.json()["data"]["slug"] == "sbi"

    # 3. Test GET /api/v1/finance/loan-products
    products_resp = await async_client.get("/api/v1/finance/loan-products")
    assert products_resp.status_code == 200
    products = products_resp.json()["items"]
    assert len(products) >= 6
    sbi_product = next(p for p in products if p["slug"] == "sbi-regular-auto-loan")

    product_detail_resp = await async_client.get(
        f"/api/v1/finance/loan-products/{sbi_product['id']}"
    )
    assert product_detail_resp.status_code == 200
    assert product_detail_resp.json()["data"]["slug"] == "sbi-regular-auto-loan"

    # 4. Test GET /api/v1/finance/rates
    rates_resp = await async_client.get(
        f"/api/v1/finance/rates?loan_product_id={sbi_product['id']}"
    )
    assert rates_resp.status_code == 200
    assert len(rates_resp.json()["items"]) > 0

    # 5. Test Math Endpoints
    # POST /api/v1/finance/emi
    emi_resp = await async_client.post(
        "/api/v1/finance/emi",
        json={
            "loan_amount": "1000000.00",
            "annual_interest_rate": "8.50",
            "tenure_months": 60,
        },
    )
    assert emi_resp.status_code == 200
    emi_data = emi_resp.json()["data"]
    assert emi_data["monthly_emi"] == "20516.53"
    assert emi_data["total_payment"] == "1230991.80"

    # POST /api/v1/finance/max-loan
    max_loan_resp = await async_client.post(
        "/api/v1/finance/max-loan",
        json={
            "desired_monthly_emi": "20516.53",
            "annual_interest_rate": "8.50",
            "tenure_months": 60,
        },
    )
    assert max_loan_resp.status_code == 200
    max_loan_data = max_loan_resp.json()["data"]
    assert float(max_loan_data["maximum_loan_amount"]) > 999900

    # POST /api/v1/finance/amortization
    amort_resp = await async_client.post(
        "/api/v1/finance/amortization",
        json={
            "loan_amount": "500000.00",
            "annual_interest_rate": "9.00",
            "tenure_months": 36,
        },
    )
    assert amort_resp.status_code == 200
    schedule = amort_resp.json()["data"]["schedule"]
    assert len(schedule) == 36
    assert schedule[-1]["closing_balance"] == "0.00"

    # 6. Test Single Loan Calculation POST /api/v1/finance/calculate
    calc_payload = {
        "loan_product_id": sbi_product["id"],
        "on_road_price": "1000000.00",
        "down_payment": "200000.00",
        "tenure_months": 60,
        "credit_score": 780,
        "monthly_income": "75000.00",
        "applicant_age": 32,
        "include_amortization": True,
    }
    calc_resp = await async_client.post("/api/v1/finance/calculate", json=calc_payload)
    assert calc_resp.status_code == 200
    calc_data = calc_resp.json()["data"]
    assert "State Bank of India" in calc_data["bank_name"]
    assert (
        calc_data["applied_interest_rate"] == "8.75" or calc_data["applied_interest_rate"] == "8.65"
    )
    assert calc_data["eligibility"]["status"] == "ESTIMATED_ELIGIBLE"
    assert len(calc_data["amortization_schedule"]) == 60

    # 7. Test Multi-Bank Comparison POST /api/v1/finance/compare with Vehicle Variant & Location
    # Fetch a variant and a state
    states_resp = await async_client.get("/api/v1/states")
    ka_state = next(s for s in states_resp.json()["items"] if s["code"] == "KA")

    variants_resp = await async_client.get("/api/v1/variants?limit=5")
    test_variant = variants_resp.json()["items"][0]

    compare_payload = {
        "vehicle_variant_id": test_variant["id"],
        "state_id": ka_state["id"],
        "down_payment": "200000.00",
        "tenure_months": 60,
        "credit_score": 760,
        "monthly_income": "80000.00",
        "applicant_age": 30,
    }
    compare_resp = await async_client.post("/api/v1/finance/compare", json=compare_payload)
    assert compare_resp.status_code == 200, compare_resp.text
    compare_data = compare_resp.json()["data"]
    assert compare_data["variant_id"] == test_variant["id"]
    assert float(compare_data["on_road_price"]) > 0
    assert len(compare_data["offers"]) >= 5

    # Check that offers are ranked by monthly_emi ascending
    offers = compare_data["offers"]
    for i in range(len(offers) - 1):
        assert float(offers[i]["monthly_emi"]) <= float(offers[i + 1]["monthly_emi"])
    assert compare_data["offers"][0]["is_recommended"] is True
