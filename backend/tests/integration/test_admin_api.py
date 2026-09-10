from decimal import Decimal
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion_constants import ConflictStatus, VerificationStatus
from app.db.seed import seed_database
from app.models.data_source import DataSource
from app.models.ingestion import DataConflictRecord, DataQualityReviewItem, IngestionRun


@pytest.mark.asyncio
async def test_admin_overview_endpoint(async_client: AsyncClient, db_session: AsyncSession):
    await seed_database(db_session)
    response = await async_client.get("/api/v1/admin/overview")
    assert response.status_code == 200, response.text
    data = response.json()["data"]

    assert data["total_data_sources"] >= 5
    assert data["active_sources"] >= 5
    assert "overall_quality_score" in data
    assert "quality_rating" in data
    assert "admin_auth_notice" in data


@pytest.mark.asyncio
async def test_admin_data_sources_and_toggle(async_client: AsyncClient, db_session: AsyncSession):
    await seed_database(db_session)

    # 1. List data sources
    response = await async_client.get("/api/v1/admin/data-sources")
    assert response.status_code == 200
    sources = response.json()["data"]
    assert len(sources) >= 5
    first_src = sources[0]
    src_id = first_src["id"]
    initial_active = first_src["is_active"]
    assert "access_mode" in first_src
    assert "freshness_status" in first_src
    assert "quality_score" in first_src

    # 2. Toggle active state
    toggle_resp = await async_client.post(f"/api/v1/admin/data-sources/{src_id}/toggle")
    assert toggle_resp.status_code == 200
    updated_src = toggle_resp.json()["data"]
    assert updated_src["is_active"] != initial_active

    # 3. Toggle back
    toggle_resp2 = await async_client.post(f"/api/v1/admin/data-sources/{src_id}/toggle")
    assert toggle_resp2.status_code == 200
    assert toggle_resp2.json()["data"]["is_active"] == initial_active


@pytest.mark.asyncio
async def test_admin_ingestion_runs_and_detail(async_client: AsyncClient, db_session: AsyncSession):
    await seed_database(db_session)

    # Trigger a run first
    run_resp = await async_client.post(
        "/api/v1/ingestion/runs",
        json={"dataset_name": "fuel_prices", "notes": "Test Run for Admin Inspection"},
    )
    assert run_resp.status_code == 201
    run_id = run_resp.json()["data"]["id"]

    # List runs via admin endpoint
    list_resp = await async_client.get("/api/v1/admin/ingestion-runs")
    assert list_resp.status_code == 200
    runs = list_resp.json()["data"]
    assert any(r["id"] == run_id for r in runs)

    # Get run detail via admin endpoint
    detail_resp = await async_client.get(f"/api/v1/admin/ingestion-runs/{run_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()["data"]
    assert detail["run"]["id"] == run_id
    assert "validation_summary" in detail
    assert "raw_records_count" in detail


@pytest.mark.asyncio
async def test_admin_review_queue_and_actions(async_client: AsyncClient, db_session: AsyncSession):
    await seed_database(db_session)

    # Seed a test review item
    review_item = DataQualityReviewItem(
        entity_type="pricing",
        entity_identifier="variant_1_price",
        field_name="ex_showroom_price",
        proposed_value={"price": "1200000.00"},
        status=VerificationStatus.PENDING_REVIEW.value,
    )
    db_session.add(review_item)
    await db_session.commit()
    await db_session.refresh(review_item)

    # 1. List review items
    list_resp = await async_client.get("/api/v1/admin/review-queue")
    assert list_resp.status_code == 200
    items = list_resp.json()["data"]
    assert any(it["id"] == review_item.id for it in items)

    # 2. Approve review item
    approve_resp = await async_client.post(
        f"/api/v1/admin/review-queue/{review_item.id}/approve",
        json={
            "action": "APPROVE",
            "reviewer_name": "Audit Lead",
            "reviewer_notes": "Verified against official gazette.",
        },
    )
    assert approve_resp.status_code == 200
    app_data = approve_resp.json()["data"]
    assert app_data["status"] == VerificationStatus.VERIFIED.value

    # 3. Create another item and reject it
    review_item2 = DataQualityReviewItem(
        entity_type="vehicle",
        entity_identifier="variant_2_specs",
        field_name="boot_space_litres",
        proposed_value={"boot_space": "9999"},
        status=VerificationStatus.PENDING_REVIEW.value,
    )
    db_session.add(review_item2)
    await db_session.commit()
    await db_session.refresh(review_item2)

    reject_resp = await async_client.post(
        f"/api/v1/admin/review-queue/{review_item2.id}/reject",
        json={
            "action": "REJECT",
            "reviewer_name": "Audit Lead",
            "reviewer_notes": "Data is an erroneous outlier.",
        },
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["data"]["status"] == VerificationStatus.REJECTED.value


@pytest.mark.asyncio
async def test_admin_conflicts_and_resolution(async_client: AsyncClient, db_session: AsyncSession):
    await seed_database(db_session)

    sources = (await db_session.execute(select(DataSource).limit(2))).scalars().all()
    assert len(sources) >= 2

    # Create a test conflict
    conflict = DataConflictRecord(
        dataset_name="fuel_prices",
        entity_type="fuel_price",
        entity_identifier="bengaluru_petrol",
        field_name="price_per_unit",
        source_a_id=sources[0].id,
        source_b_id=sources[1].id,
        source_a_value={"price": "102.86"},
        source_b_value={"price": "101.50"},
        status=ConflictStatus.UNRESOLVED.value,
    )
    db_session.add(conflict)
    await db_session.commit()
    await db_session.refresh(conflict)

    # 1. List conflicts
    conf_resp = await async_client.get("/api/v1/admin/conflicts")
    assert conf_resp.status_code == 200
    conflicts = conf_resp.json()["data"]
    assert any(c["id"] == conflict.id for c in conflicts)

    # 2. Resolve conflict
    res_resp = await async_client.post(
        f"/api/v1/admin/conflicts/{conflict.id}/resolve",
        json={
            "accepted_source_id": sources[0].id,
            "resolution_notes": "Accepted IOCL official rate.",
        },
    )
    assert res_resp.status_code == 200
    res_data = res_resp.json()["data"]
    assert res_data["status"] == ConflictStatus.RESOLVED.value
    assert f"Adopted Source #{sources[0].id}" in res_data["resolution_notes"]


@pytest.mark.asyncio
async def test_admin_freshness_and_quality_reports(
    async_client: AsyncClient, db_session: AsyncSession
):
    await seed_database(db_session)

    # Freshness report
    fresh_resp = await async_client.get("/api/v1/admin/freshness")
    assert fresh_resp.status_code == 200
    fresh_data = fresh_resp.json()["data"]
    assert "domains" in fresh_data
    assert len(fresh_data["domains"]) == 6
    domain_keys = [d["domain_key"] for d in fresh_data["domains"]]
    assert "vehicles" in domain_keys
    assert "taxes" in domain_keys
    assert "finance" in domain_keys
    assert "tco" in domain_keys

    # Quality score breakdown
    qual_resp = await async_client.get("/api/v1/admin/quality")
    assert qual_resp.status_code == 200
    qual_data = qual_resp.json()["data"]
    assert "overall_score" in qual_data
    assert "pillars" in qual_data
    assert len(qual_data["pillars"]) == 4
    assert "score_change_explanation" in qual_data
    assert len(qual_data["recommendations"]) > 0
