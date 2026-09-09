import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion_constants import ConflictStatus, DataSourceType
from app.db.seed import seed_database
from app.models.data_source import DataSource
from app.models.ingestion import DataConflictRecord, IngestionRun
from app.models.location import State, City, RtoOffice
from app.services.ingestion_service import IngestionService


@pytest.mark.asyncio
async def test_government_location_ingestion_api_flow(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """POST /api/v1/ingestion/runs triggers government location ingestion and updates location catalogue."""
    # 1. Trigger Government Location Ingestion
    payload = {
        "dataset_name": "locations_rto_directory",
        "notes": "MoRTH Parivahan integration test run",
    }
    run_resp = await async_client.post("/api/v1/ingestion/runs", json=payload)
    assert run_resp.status_code == 201
    run_data = run_resp.json()["data"]
    assert run_data["id"] is not None
    assert run_data["status"] == "COMPLETED"
    assert run_data["records_seen"] >= 10
    assert run_data["records_created"] >= 10
    assert run_data["error_count"] == 0

    # 2. Check Run in History
    run_id = run_data["id"]
    get_resp = await async_client.get(f"/api/v1/ingestion/runs/{run_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["dataset_name"] == "locations_rto_directory"


@pytest.mark.asyncio
async def test_canonical_location_apis_reflect_authoritative_provenance(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """Existing Location REST APIs return newly ingested government locations with provenance metadata."""
    # Trigger ingestion
    payload = {
        "dataset_name": "locations_rto_directory",
        "notes": "MoRTH test run for location APIs",
    }
    await async_client.post("/api/v1/ingestion/runs", json=payload)

    # 1. GET /api/v1/states
    states_resp = await async_client.get("/api/v1/states")
    assert states_resp.status_code == 200
    states = states_resp.json()["items"]
    assert len(states) > 0
    ka_state = [s for s in states if s["code"] == "KA"][0]
    assert ka_state["name"] == "Karnataka"
    assert ka_state["source_id"] is not None

    # 2. GET /api/v1/states/{state_id}/rtos
    state_id = ka_state["id"]
    rtos_resp = await async_client.get(f"/api/v1/states/{state_id}/rtos")
    assert rtos_resp.status_code == 200
    rtos = rtos_resp.json()["data"]
    assert len(rtos) >= 4
    ka01 = [r for r in rtos if r["code"] == "KA-01"][0]
    assert ka01["source_record_id"] == "MORTH-KA-01-KORAMANGALA"
    assert "Koramangala" in ka01["jurisdiction"]

    # 3. GET /api/v1/locations/search
    search_resp = await async_client.get("/api/v1/locations/search?q=Koramangala")
    assert search_resp.status_code == 200
    search_results = search_resp.json()["data"]
    assert len(search_results) > 0
    assert any(res["rto_code"] == "KA-01" for res in search_results)


@pytest.mark.asyncio
async def test_cross_source_location_conflict_detection_flow(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """Multi-source location discrepancies (e.g. differing jurisdiction text) surface in conflicts endpoint."""
    # 1. Create first data source & run
    payload1 = {
        "dataset_name": "locations_rto_directory",
        "notes": "MoRTH primary run",
    }
    await async_client.post("/api/v1/ingestion/runs", json=payload1)

    # 2. Simulate raw record from a secondary source with conflicting jurisdiction
    ds_secondary = await IngestionService.get_or_create_data_source(
        db_session,
        name="State Transport Portal (Secondary)",
        slug="secondary-transport-portal",
        source_type=DataSourceType.OFFICIAL_GOVERNMENT,
    )
    run_secondary = IngestionRun(
        data_source_id=ds_secondary.id,
        dataset_name="locations_rto_directory",
        status="COMPLETED",
    )
    db_session.add(run_secondary)
    await db_session.commit()
    # Check conflict detection directly
    await IngestionService._check_conflicts(
        db=db_session,
        dataset_name="locations_rto_directory",
        entity_type="LOCATION",
        entity_identifier="KA KA-01 Bengaluru",
        current_source_id=ds_secondary.id,
        normalized_payload={
            "rto_code": "KA-01",
            "jurisdiction": "Entire South Bengaluru Municipality Zone",
        },
    )
    await db_session.commit()

    # 3. Verify conflict appears in REST API
    conflicts_resp = await async_client.get("/api/v1/ingestion/data-quality/conflicts")
    assert conflicts_resp.status_code == 200
    conflicts = conflicts_resp.json()["data"]
    assert len(conflicts) >= 1
    c = conflicts[0]
    assert c["field_name"] == "jurisdiction"
    assert c["status"] == "UNRESOLVED"
