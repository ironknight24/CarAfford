from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.core.ingestion_constants import (
    DataSourceType,
    IngestionRunStatus,
    VerificationStatus,
    DataFreshnessStatus,
    ConflictStatus,
    IngestionEntityType,
    DATA_QUALITY_WEIGHTS,
    INGESTION_DISCLAIMER,
)

# =============================================================================
# DATA SOURCE SCHEMAS
# =============================================================================


class DataSourceBase(BaseModel):
    name: str = Field(..., max_length=150)
    slug: str = Field(..., max_length=150)
    source_type: DataSourceType = DataSourceType.DEMO_SEED
    provider_type: str = Field("aggregator", max_length=100)
    organization: Optional[str] = Field(None, max_length=200)
    base_url: Optional[str] = Field(None, max_length=500)
    description: Optional[str] = None
    licensing_notes: Optional[str] = None
    terms_url: Optional[str] = Field(None, max_length=500)
    trust_level: int = Field(70, ge=0, le=100)
    is_active: bool = True


class DataSourceCreate(DataSourceBase):
    pass


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    source_type: Optional[DataSourceType] = None
    provider_type: Optional[str] = None
    organization: Optional[str] = None
    base_url: Optional[str] = None
    description: Optional[str] = None
    licensing_notes: Optional[str] = None
    terms_url: Optional[str] = None
    trust_level: Optional[int] = Field(None, ge=0, le=100)
    is_active: Optional[bool] = None


class DataSourceRead(DataSourceBase):
    id: int
    last_synced_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# INGESTION RUN SCHEMAS
# =============================================================================


class IngestionRunCreate(BaseModel):
    data_source_id: Optional[int] = None
    dataset_name: str = Field(..., max_length=100)
    notes: Optional[str] = None


class IngestionRunRead(BaseModel):
    id: int
    data_source_id: int
    dataset_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: IngestionRunStatus
    records_seen: int
    records_created: int
    records_updated: int
    records_rejected: int
    records_unchanged: int
    error_count: int
    validation_error_count: int
    checksum: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# RAW INGESTION RECORD SCHEMAS
# =============================================================================


class RawIngestionRecordRead(BaseModel):
    id: int
    ingestion_run_id: int
    source_record_id: Optional[str] = None
    entity_type: str
    raw_payload: Dict[str, Any]
    payload_hash: str
    retrieved_at: datetime
    source_url: Optional[str] = None
    parsing_status: str
    validation_status: str
    validation_errors: Optional[List[Dict[str, Any]]] = None
    canonical_entity_id: Optional[int] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# CONFLICT RESOLUTION SCHEMAS
# =============================================================================


class DataConflictRead(BaseModel):
    id: int
    dataset_name: str
    entity_type: str
    entity_id: Optional[int] = None
    entity_identifier: str
    field_name: str
    source_a_id: int
    source_a_value: Any
    source_b_id: int
    source_b_value: Any
    detected_at: datetime
    status: ConflictStatus
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DataConflictResolutionRequest(BaseModel):
    accepted_source_id: int
    resolution_notes: str


# =============================================================================
# MANUAL REVIEW QUEUE SCHEMAS
# =============================================================================


class DataQualityReviewItemRead(BaseModel):
    id: int
    raw_record_id: Optional[int] = None
    entity_type: str
    entity_identifier: str
    field_name: str
    current_value: Optional[Any] = None
    proposed_value: Any
    status: VerificationStatus
    reviewer_notes: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[str] = None
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DataQualityReviewAction(BaseModel):
    action: str = Field(..., description="APPROVE or REJECT")
    reviewer_notes: Optional[str] = None
    reviewer_name: Optional[str] = "Admin"


# =============================================================================
# DATA QUALITY & FRESHNESS SCHEMAS
# =============================================================================


class DataQualityScoreBreakdown(BaseModel):
    overall_quality_score: Decimal
    source_trust_score: Decimal
    freshness_score: Decimal
    completeness_score: Decimal
    validation_score: Decimal
    weights: Dict[str, Decimal] = DATA_QUALITY_WEIGHTS


class FreshnessReportItem(BaseModel):
    dataset_name: str
    sla_days: int
    last_synced_at: Optional[datetime] = None
    age_days: Optional[int] = None
    status: DataFreshnessStatus


class DataQualityOverviewResponse(BaseModel):
    overall_quality_score: Decimal
    breakdown: DataQualityScoreBreakdown
    total_sources: int
    active_sources: int
    total_ingestion_runs: int
    unresolved_conflicts_count: int
    pending_review_items_count: int
    freshness_report: List[FreshnessReportItem]
    data_status: str = "DEMO"
    disclaimer: str = INGESTION_DISCLAIMER
