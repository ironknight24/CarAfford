import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.seed import seed_database
from app.models.data_source import DataSource


@pytest.mark.asyncio
async def test_data_sources_api_flow(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """GET and POST /api/v1/data-sources manages data source catalog."""
    await seed_database(db_session)

    # 1. List data sources
    resp = await async_client.get("/api/v1/data-sources")
    assert resp.status_code == 200
    sources = resp.json()["data"]
    assert len(sources) > 0

    # 2. Get specific data source by ID
    first_id = sources[0]["id"]
    get_resp = await async_client.get(f"/api/v1/data-sources/{first_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["data"]["id"] == first_id

    # 3. Create new official data source
    create_payload = {
        "name": "Federation of Automobile Dealers Associations (FADA)",
        "slug": "fada-india-official",
        "source_type": "OFFICIAL_MANUFACTURER",
        "provider_type": "dealer_association",
        "organization": "FADA India",
        "base_url": "https://www.fada.in",
        "trust_level": 95,
        "is_active": True,
    }
    create_resp = await async_client.post("/api/v1/data-sources", json=create_payload)
    assert create_resp.status_code == 201
    created_ds = create_resp.json()["data"]
    assert created_ds["slug"] == "fada-india-official"
    assert created_ds["trust_level"] == 95


@pytest.mark.asyncio
async def test_ingestion_runs_api_flow(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """POST /api/v1/ingestion/runs triggers ingestion and GET returns run history."""
    await seed_database(db_session)

    # 1. Trigger Ingestion Run
    payload = {
        "data_source_id": 1,
        "dataset_name": "vehicles_catalogue",
        "notes": "Integration test run",
    }
    run_resp = await async_client.post("/api/v1/ingestion/runs", json=payload)
    assert run_resp.status_code == 201
    run_data = run_resp.json()["data"]
    assert run_data["id"] is not None
    assert run_data["status"] == "COMPLETED"
    assert run_data["records_seen"] > 0

    # 2. List Ingestion Runs
    list_resp = await async_client.get("/api/v1/ingestion/runs")
    assert list_resp.status_code == 200
    runs = list_resp.json()["data"]
    assert len(runs) > 0

    # 3. Get single run details
    run_id = run_data["id"]
    detail_resp = await async_client.get(f"/api/v1/ingestion/runs/{run_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["data"]["id"] == run_id


@pytest.mark.asyncio
async def test_data_quality_and_governance_apis(
    db_session: AsyncSession,
    async_client: AsyncClient,
):
    """GET /api/v1/ingestion/data-quality returns composite quality score and SLA reports."""
    await seed_database(db_session)

    # 1. Data Quality Overview
    quality_resp = await async_client.get("/api/v1/ingestion/data-quality")
    assert quality_resp.status_code == 200
    quality = quality_resp.json()["data"]
    assert float(quality["overall_quality_score"]) > 0
    assert "breakdown" in quality
    assert len(quality["freshness_report"]) > 0
    assert quality["data_status"] == "DEMO"

    # 2. Conflicts endpoint
    conflicts_resp = await async_client.get("/api/v1/ingestion/data-quality/conflicts")
    assert conflicts_resp.status_code == 200
    assert isinstance(conflicts_resp.json()["data"], list)

    # 3. Review Queue endpoint
    review_resp = await async_client.get("/api/v1/ingestion/data-quality/review-queue")
    assert review_resp.status_code == 200
    assert isinstance(review_resp.json()["data"], list)
