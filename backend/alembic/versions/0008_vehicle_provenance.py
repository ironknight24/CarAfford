"""vehicle provenance enhancements

Revision ID: 0008_vehicle_provenance
Revises: 0007_location_provenance
Create Date: 2026-09-09 23:25:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0008_vehicle_provenance"
down_revision: Union[str, None] = "0007_location_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add provenance & verification columns to manufacturers
    op.add_column("manufacturers", sa.Column("source_id", sa.Integer(), nullable=True))
    op.add_column("manufacturers", sa.Column("source_record_id", sa.String(length=255), nullable=True))
    op.add_column("manufacturers", sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("manufacturers", sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False))
    op.create_index("ix_manufacturers_source_id", "manufacturers", ["source_id"], unique=False)
    op.create_foreign_key("fk_manufacturers_source_id", "manufacturers", "data_sources", ["source_id"], ["id"], ondelete="SET NULL")

    # 2. Add provenance & verification columns to car_models
    op.add_column("car_models", sa.Column("source_id", sa.Integer(), nullable=True))
    op.add_column("car_models", sa.Column("source_record_id", sa.String(length=255), nullable=True))
    op.add_column("car_models", sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("car_models", sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False))
    op.create_index("ix_car_models_source_id", "car_models", ["source_id"], unique=False)
    op.create_foreign_key("fk_car_models_source_id", "car_models", "data_sources", ["source_id"], ["id"], ondelete="SET NULL")

    # 3. Add provenance & verification columns to variants
    op.add_column("variants", sa.Column("source_id", sa.Integer(), nullable=True))
    op.add_column("variants", sa.Column("source_record_id", sa.String(length=255), nullable=True))
    op.add_column("variants", sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("variants", sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False))
    op.create_index("ix_variants_source_id", "variants", ["source_id"], unique=False)
    op.create_foreign_key("fk_variants_source_id", "variants", "data_sources", ["source_id"], ["id"], ondelete="SET NULL")

    # 4. Add verification_status column to vehicle_prices
    op.add_column("vehicle_prices", sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False))


def downgrade() -> None:
    # 4. Rollback vehicle_prices
    op.drop_column("vehicle_prices", "verification_status")

    # 3. Rollback variants
    op.drop_constraint("fk_variants_source_id", "variants", type_="foreignkey")
    op.drop_index("ix_variants_source_id", table_name="variants")
    op.drop_column("variants", "verification_status")
    op.drop_column("variants", "retrieved_at")
    op.drop_column("variants", "source_record_id")
    op.drop_column("variants", "source_id")

    # 2. Rollback car_models
    op.drop_constraint("fk_car_models_source_id", "car_models", type_="foreignkey")
    op.drop_index("ix_car_models_source_id", table_name="car_models")
    op.drop_column("car_models", "verification_status")
    op.drop_column("car_models", "retrieved_at")
    op.drop_column("car_models", "source_record_id")
    op.drop_column("car_models", "source_id")

    # 1. Rollback manufacturers
    op.drop_constraint("fk_manufacturers_source_id", "manufacturers", type_="foreignkey")
    op.drop_index("ix_manufacturers_source_id", table_name="manufacturers")
    op.drop_column("manufacturers", "verification_status")
    op.drop_column("manufacturers", "retrieved_at")
    op.drop_column("manufacturers", "source_record_id")
    op.drop_column("manufacturers", "source_id")
