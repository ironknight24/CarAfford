import pytest
from datetime import datetime, timezone
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy import select

from app.models.location import State, City, RtoOffice
from app.models.tax_rule import TaxRule
from app.models.vehicle import Variant


@pytest.mark.asyncio
class TestVehicleIngestionApiAndDownstreamFlow:
    """Tests API triggering of OEM vehicle ingestion and backward compatibility with downstream domains."""

    async def test_trigger_oem_vehicle_ingestion_api(self, async_client: AsyncClient):
        # 1. Trigger Tata Motors ingestion run via API
        response = await async_client.post(
            "/api/v1/ingestion/runs",
            json={
                "dataset_name": "tata_vehicles",
                "notes": "API triggered official Tata Motors ingestion",
            },
        )
        assert response.status_code == 201
        data = response.json()["data"]
        assert data["status"] in {"COMPLETED", "PARTIAL"}
        assert data["records_seen"] >= 5
        assert data["records_created"] > 0

        # 2. Trigger Maruti Suzuki ingestion run via API
        maruti_resp = await async_client.post(
            "/api/v1/ingestion/runs",
            json={
                "dataset_name": "maruti_vehicles",
                "notes": "API triggered official Maruti Suzuki ingestion",
            },
        )
        assert maruti_resp.status_code == 201
        m_data = maruti_resp.json()["data"]
        assert m_data["status"] == "COMPLETED"

    async def test_vehicle_api_backward_compatibility_with_authoritative_data(
        self, async_client: AsyncClient
    ):
        # 1. First trigger ingestion
        await async_client.post(
            "/api/v1/ingestion/runs",
            json={"dataset_name": "hyundai_vehicles"},
        )

        # 2. Test /api/v1/manufacturers
        mfg_resp = await async_client.get("/api/v1/manufacturers")
        assert mfg_resp.status_code == 200
        mfg_items = mfg_resp.json()["items"]
        hyundai = next((m for m in mfg_items if m["name"] == "Hyundai"), None)
        assert hyundai is not None

        # 3. Test /api/v1/manufacturers/{id}
        mfg_detail = await async_client.get(f"/api/v1/manufacturers/{hyundai['id']}")
        assert mfg_detail.status_code == 200
        assert mfg_detail.json()["data"]["name"] == "Hyundai"

        # 4. Test /api/v1/models
        models_resp = await async_client.get("/api/v1/models?search=Creta")
        assert models_resp.status_code == 200
        creta_items = models_resp.json()["items"]
        assert len(creta_items) > 0

        # 5. Test /api/v1/variants
        var_resp = await async_client.get("/api/v1/variants?fuel_type=Petrol")
        assert var_resp.status_code == 200
        var_items = var_resp.json()["items"]
        assert len(var_items) > 0

        # 6. Test /api/v1/vehicles/search
        search_resp = await async_client.get("/api/v1/vehicles/search?search=Creta")
        assert search_resp.status_code == 200
        search_results = search_resp.json()["items"]
        assert len(search_results) > 0

    async def test_downstream_on_road_calculation_compatibility(
        self, async_client: AsyncClient, db_session
    ):
        # 1. Ingest Tata vehicles
        await async_client.post(
            "/api/v1/ingestion/runs",
            json={"dataset_name": "tata_vehicles"},
        )

        # 2. Query Punch Pure 1.2 MT
        var_res = await db_session.execute(
            select(Variant).where(Variant.name == "Punch Pure 1.2 MT")
        )
        punch_variant = var_res.scalars().first()
        assert punch_variant is not None

        # 3. Ensure test State and City exist for location pricing
        st = (await db_session.execute(select(State).where(State.code == "DL"))).scalars().first()
        if not st:
            st = State(
                name="Delhi", code="DL", region_type="UNION_TERRITORY", active=True, country_id=1
            )
            db_session.add(st)
            await db_session.flush()

        ct = (
            (await db_session.execute(select(City).where(City.name == "New Delhi")))
            .scalars()
            .first()
        )
        if not ct:
            ct = City(
                state_id=st.id, name="New Delhi", slug="new-delhi", tier="Tier 1", active=True
            )
            db_session.add(ct)
            await db_session.flush()

        rto = (
            (await db_session.execute(select(RtoOffice).where(RtoOffice.code == "DL-01")))
            .scalars()
            .first()
        )
        if not rto:
            rto = RtoOffice(
                state_id=st.id,
                city_id=ct.id,
                code="DL-01",
                name="Mall Road",
                jurisdiction="North Delhi",
                active=True,
            )
            db_session.add(rto)
            await db_session.flush()

        # Add basic road tax rule if not present
        tax_rule = (
            (await db_session.execute(select(TaxRule).where(TaxRule.state_id == st.id)))
            .scalars()
            .first()
        )
        if not tax_rule:
            tax_rule = TaxRule(
                name="Delhi Standard Road Tax",
                state_id=st.id,
                tax_type="ROAD_TAX",
                calculation_method="PERCENTAGE",
                rate=Decimal("8.0"),
                fuel_type="Petrol",
                effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
                active=True,
            )
            db_session.add(tax_rule)
            await db_session.flush()

        # 4. Calculate on-road price via endpoint
        calc_resp = await async_client.post(
            "/api/v1/pricing/on-road",
            json={
                "variant_id": punch_variant.id,
                "state_id": st.id,
                "city_id": ct.id,
                "rto_id": rto.id,
                "registration_type": "INDIVIDUAL",
            },
        )
        assert calc_resp.status_code == 200
        calc_data = calc_resp.json()["data"]
        assert Decimal(str(calc_data["totals"]["ex_showroom_price"])) == Decimal("612900.00")
        assert Decimal(str(calc_data["totals"]["on_road_price"])) > Decimal("612900.00")
        assert len(calc_data["breakdown"]) >= 1
