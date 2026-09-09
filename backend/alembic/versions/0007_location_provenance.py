"""location provenance enhancements

Revision ID: 0007_location_provenance
Revises: 0006_ingestion_domain
Create Date: 2026-09-09 23:15:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0007_location_provenance"
down_revision: Union[str, None] = "0006_ingestion_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add provenance columns to states
    op.add_column("states", sa.Column("source_id", sa.Integer(), nullable=True))
    op.add_column("states", sa.Column("source_record_id", sa.String(length=255), nullable=True))
    op.add_column("states", sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_states_source_id", "states", ["source_id"], unique=False)
    op.create_foreign_key("fk_states_source_id", "states", "data_sources", ["source_id"], ["id"], ondelete="SET NULL")

    # 2. Add provenance columns to cities
    op.add_column("cities", sa.Column("source_id", sa.Integer(), nullable=True))
    op.add_column("cities", sa.Column("source_record_id", sa.String(length=255), nullable=True))
    op.add_column("cities", sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_cities_source_id", "cities", ["source_id"], unique=False)
    op.create_foreign_key("fk_cities_source_id", "cities", "data_sources", ["source_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    # 2. Rollback cities
    op.drop_constraint("fk_cities_source_id", "cities", type_="foreignkey")
    op.drop_index("ix_cities_source_id", table_name="cities")
    op.drop_column("cities", "retrieved_at")
    op.drop_column("cities", "source_record_id")
    op.drop_column("cities", "source_id")

    # 1. Rollback states
    op.drop_constraint("fk_states_source_id", "states", type_="foreignkey")
    op.drop_index("ix_states_source_id", table_name="states")
    op.drop_column("states", "retrieved_at")
    op.drop_column("states", "source_record_id")
    op.drop_column("states", "source_id")
