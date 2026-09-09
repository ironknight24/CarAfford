"""data ingestion and provenance framework

Revision ID: 0006_ingestion_domain
Revises: 0005_financing_domain
Create Date: 2026-09-09 23:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


# revision identifiers, used by Alembic.
revision: str = "0006_ingestion_domain"
down_revision: Union[str, None] = "0005_financing_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update data_sources table
    with op.batch_alter_table("data_sources") as batch_op:
        batch_op.add_column(
            sa.Column("source_type", sa.String(length=50), server_default="DEMO_SEED", nullable=False)
        )
        batch_op.add_column(sa.Column("organization", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("licensing_notes", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("terms_url", sa.String(length=500), nullable=True))
        batch_op.add_column(
            sa.Column("trust_level", sa.Integer(), server_default="70", nullable=False)
        )
        batch_op.create_index("ix_data_sources_source_type", ["source_type"])

    # 2. Create ingestion_runs table
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("data_source_id", sa.Integer(), nullable=False),
        sa.Column("dataset_name", sa.String(length=100), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=50), server_default="RUNNING", nullable=False),
        sa.Column("records_seen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_created", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_updated", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_rejected", sa.Integer(), server_default="0", nullable=False),
        sa.Column("records_unchanged", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("validation_error_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["data_source_id"], ["data_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ingestion_runs_data_source_id", "ingestion_runs", ["data_source_id"])
    op.create_index("ix_ingestion_runs_dataset_name", "ingestion_runs", ["dataset_name"])
    op.create_index("ix_ingestion_runs_status", "ingestion_runs", ["status"])

    # 3. Create raw_ingestion_records table
    op.create_table(
        "raw_ingestion_records",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ingestion_run_id", sa.Integer(), nullable=False),
        sa.Column("source_record_id", sa.String(length=200), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("raw_payload", JSONB(), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("parsing_status", sa.String(length=50), server_default="PARSED", nullable=False),
        sa.Column("validation_status", sa.String(length=50), server_default="VALID", nullable=False),
        sa.Column("validation_errors", JSONB(), nullable=True),
        sa.Column("canonical_entity_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["ingestion_run_id"], ["ingestion_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_raw_ingestion_records_ingestion_run_id", "raw_ingestion_records", ["ingestion_run_id"])
    op.create_index("ix_raw_ingestion_records_source_record_id", "raw_ingestion_records", ["source_record_id"])
    op.create_index("ix_raw_ingestion_records_entity_type", "raw_ingestion_records", ["entity_type"])
    op.create_index("ix_raw_ingestion_records_payload_hash", "raw_ingestion_records", ["payload_hash"])
    op.create_index("ix_raw_ingestion_records_canonical_entity_id", "raw_ingestion_records", ["canonical_entity_id"])

    # 4. Create data_conflicts table
    op.create_table(
        "data_conflicts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("dataset_name", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("entity_identifier", sa.String(length=200), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("source_a_id", sa.Integer(), nullable=False),
        sa.Column("source_a_value", JSONB(), nullable=False),
        sa.Column("source_b_id", sa.Integer(), nullable=False),
        sa.Column("source_b_value", JSONB(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="UNRESOLVED", nullable=False),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["source_a_id"], ["data_sources.id"]),
        sa.ForeignKeyConstraint(["source_b_id"], ["data_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_conflicts_dataset_name", "data_conflicts", ["dataset_name"])
    op.create_index("ix_data_conflicts_entity_type", "data_conflicts", ["entity_type"])
    op.create_index("ix_data_conflicts_entity_identifier", "data_conflicts", ["entity_identifier"])
    op.create_index("ix_data_conflicts_status", "data_conflicts", ["status"])

    # 5. Create data_quality_review_items table
    op.create_table(
        "data_quality_review_items",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("raw_record_id", sa.Integer(), nullable=True),
        sa.Column("entity_type", sa.String(length=50), nullable=False),
        sa.Column("entity_identifier", sa.String(length=200), nullable=False),
        sa.Column("field_name", sa.String(length=100), nullable=False),
        sa.Column("current_value", JSONB(), nullable=True),
        sa.Column("proposed_value", JSONB(), nullable=False),
        sa.Column("status", sa.String(length=50), server_default="PENDING_REVIEW", nullable=False),
        sa.Column("reviewer_notes", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["raw_record_id"], ["raw_ingestion_records.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_data_quality_review_items_raw_record_id", "data_quality_review_items", ["raw_record_id"])
    op.create_index("ix_data_quality_review_items_entity_type", "data_quality_review_items", ["entity_type"])
    op.create_index("ix_data_quality_review_items_entity_identifier", "data_quality_review_items", ["entity_identifier"])
    op.create_index("ix_data_quality_review_items_status", "data_quality_review_items", ["status"])


def downgrade() -> None:
    op.drop_table("data_quality_review_items")
    op.drop_table("data_conflicts")
    op.drop_table("raw_ingestion_records")
    op.drop_table("ingestion_runs")
    with op.batch_alter_table("data_sources") as batch_op:
        batch_op.drop_index("ix_data_sources_source_type")
        batch_op.drop_column("trust_level")
        batch_op.drop_column("terms_url")
        batch_op.drop_column("licensing_notes")
        batch_op.drop_column("organization")
        batch_op.drop_column("source_type")
