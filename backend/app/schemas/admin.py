from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.ingestion import (
    DataConflictRead,
    DataQualityOverviewResponse,
    DataQualityReviewItemRead,
    DataSourceRead,
    FreshnessReportItem,
    IngestionRunRead,
)


class AdminOverviewResponse(BaseModel):
    """Aggregated administrative overview of data sources, ingestion status, and quality metrics."""

    total_data_sources: int
    active_sources: int
    live_sources: int
    fixture_only_sources: int
    manual_review_sources: int
    total_ingestion_runs: int
    active_ingestion_runs: int
    failed_ingestion_runs: int
    stale_datasets: int
    expired_datasets: int
    unresolved_conflicts: int
    pending_review_items: int
    overall_quality_score: Decimal
    quality_rating: str
    datasets_freshness_summary: List[FreshnessReportItem]
    admin_auth_notice: str = (
        "Administrative operations isolated. Production authentication/RBAC is scheduled for Domain 17."
    )


class AdminDataSourceItem(BaseModel):
    """Enhanced data source representation for governance UI."""

    id: int
    name: str
    slug: str
    organization: Optional[str] = None
    source_type: str
    provider_type: str
    access_mode: str  # LIVE, FIXTURE_ONLY, MANUAL_REVIEW
    base_url: Optional[str] = None
    terms_url: Optional[str] = None
    trust_level: int
    freshness_sla_days: int
    last_retrieved_at: Optional[datetime] = None
    freshness_status: str  # CURRENT, STALE, EXPIRED, UNKNOWN
    age_days: Optional[int] = None
    is_active: bool
    quality_score: Decimal
    created_at: datetime
    updated_at: datetime


class AdminIngestionRunDetail(BaseModel):
    """Full audit detail for a specific ingestion run."""

    run: IngestionRunRead
    raw_records_count: int
    raw_samples: List[Dict[str, Any]] = Field(default_factory=list)
    validation_summary: Dict[str, Any] = Field(default_factory=dict)
    conflicts_detected: List[DataConflictRead] = Field(default_factory=list)
    quality_reviews: List[DataQualityReviewItemRead] = Field(default_factory=list)


class FreshnessDomainGroup(BaseModel):
    """Freshness status grouped by domain category."""

    domain_name: str
    domain_key: str
    total_datasets: int
    current_count: int
    stale_count: int
    expired_count: int
    datasets: List[FreshnessReportItem]


class AdminFreshnessResponse(BaseModel):
    """Grouped data freshness report across all functional domains."""

    domains: List[FreshnessDomainGroup]
    overall_freshness_pct: Decimal
    stale_datasets_count: int
    expired_datasets_count: int


class QualityScorePillar(BaseModel):
    """Single pillar contributing to the composite data quality score."""

    pillar_name: str
    pillar_key: str
    weight_pct: Decimal
    score: Decimal
    description: str
    status: str  # EXCELLENT, GOOD, FAIR, POOR


class AdminQualityResponse(BaseModel):
    """Comprehensive data quality scorecard and explanations."""

    overall_score: Decimal
    rating: str
    pillars: List[QualityScorePillar]
    score_change_explanation: str
    recommendations: List[str]
