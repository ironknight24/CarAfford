from decimal import Decimal
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion_constants import (
    ConflictStatus,
    DataFreshnessStatus,
    IngestionRunStatus,
    VerificationStatus,
)
from app.db.seed import seed_database
from app.models.data_source import DataSource
from app.models.ingestion import DataConflictRecord, DataQualityReviewItem, IngestionRun
from app.schemas.admin import (
    AdminDataSourceItem,
    AdminFreshnessResponse,
    AdminIngestionRunDetail,
    AdminOverviewResponse,
    AdminQualityResponse,
)


@pytest.mark.asyncio
async def test_admin_schemas_and_models():
    """Validates admin schema construction and serialization."""
    overview = AdminOverviewResponse(
        total_data_sources=15,
        active_sources=14,
        live_sources=5,
        fixture_only_sources=8,
        manual_review_sources=2,
        total_ingestion_runs=20,
        active_ingestion_runs=0,
        failed_ingestion_runs=1,
        stale_datasets=2,
        expired_datasets=0,
        unresolved_conflicts=3,
        pending_review_items=4,
        overall_quality_score=Decimal("88.50"),
        quality_rating="EXCELLENT",
        datasets_freshness_summary=[],
    )
    assert overview.total_data_sources == 15
    assert overview.overall_quality_score == Decimal("88.50")
    assert "Domain 17" in overview.admin_auth_notice


@pytest.mark.asyncio
async def test_admin_governance_domain_seeding(db_session: AsyncSession):
    """Verifies that seed_database populates data sources and clean state for administration."""
    await seed_database(db_session)

    # Check that data sources exist
    sources = (await db_session.execute(select(DataSource))).scalars().all()
    assert len(sources) >= 5

    # Check that active flag is true by default
    active_sources = [s for s in sources if s.is_active]
    assert len(active_sources) == len(sources)
