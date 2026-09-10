from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, utc_now
from app.core.ingestion_constants import (
    IngestionRunStatus,
    VerificationStatus,
    ConflictStatus,
    IngestionEntityType,
)


class IngestionRun(Base, TimestampMixin):
    """Execution log of an ingestion run for a specific data source and dataset."""

    __tablename__ = "ingestion_runs"

    data_source_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default=IngestionRunStatus.RUNNING.value, nullable=False, index=True
    )

    # Audit metrics
    records_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    records_unchanged: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validation_error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    checksum: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    data_source = relationship("DataSource", backref="ingestion_runs")
    raw_records = relationship(
        "RawIngestionRecord", back_populates="ingestion_run", cascade="all, delete-orphan"
    )


class RawIngestionRecord(Base, TimestampMixin):
    """Immutable staging table for raw external payloads before canonical normalization."""

    __tablename__ = "raw_ingestion_records"

    ingestion_run_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("ingestion_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_record_id: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    raw_payload: Mapped[Dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    parsing_status: Mapped[str] = mapped_column(String(50), default="PARSED", nullable=False)
    validation_status: Mapped[str] = mapped_column(String(50), default="VALID", nullable=False)
    validation_errors: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), default=list, nullable=True
    )

    # Target canonical entity linkage after promotion
    canonical_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)

    # Relationships
    ingestion_run = relationship("IngestionRun", back_populates="raw_records")


class DataConflictRecord(Base, TimestampMixin):
    """Discrepancies identified between multi-source values for the same canonical entity."""

    __tablename__ = "data_conflicts"

    dataset_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    entity_identifier: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)

    source_a_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_sources.id"), nullable=False)
    source_a_value: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )
    source_b_id: Mapped[int] = mapped_column(Integer, ForeignKey("data_sources.id"), nullable=False)
    source_b_value: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(50), default=ConflictStatus.UNRESOLVED.value, nullable=False, index=True
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    source_a = relationship("DataSource", foreign_keys=[source_a_id])
    source_b = relationship("DataSource", foreign_keys=[source_b_id])


class DataQualityReviewItem(Base, TimestampMixin):
    """Items flagged for manual verification or approval before canonical commitment."""

    __tablename__ = "data_quality_review_items"

    raw_record_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("raw_ingestion_records.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    entity_identifier: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)

    current_value: Mapped[Optional[Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    proposed_value: Mapped[Any] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(50), default=VerificationStatus.PENDING_REVIEW.value, nullable=False, index=True
    )
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    raw_record = relationship("RawIngestionRecord")
