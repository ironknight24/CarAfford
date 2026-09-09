"""finance provenance enhancements

Revision ID: 0009_finance_provenance
Revises: 0008_vehicle_provenance
Create Date: 2026-09-09 23:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0009_finance_provenance"
down_revision: Union[str, None] = "0008_vehicle_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add provenance & verification columns to banks
    op.add_column("banks", sa.Column("source_record_id", sa.String(length=255), nullable=True))
    op.add_column("banks", sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("banks", sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False))

    # 2. Add provenance & verification columns to loan_products
    op.add_column("loan_products", sa.Column("source_id", sa.Integer(), nullable=True))
    op.add_column("loan_products", sa.Column("source_record_id", sa.String(length=255), nullable=True))
    op.add_column("loan_products", sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("loan_products", sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False))
    op.create_index("ix_loan_products_source_id", "loan_products", ["source_id"], unique=False)
    op.create_foreign_key("fk_loan_products_source_id", "loan_products", "data_sources", ["source_id"], ["id"], ondelete="SET NULL")

    # 3. Add verification_status column to interest_rates
    op.add_column("interest_rates", sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False))

    # 4. Add verification_status column to loan_eligibility_rules
    op.add_column("loan_eligibility_rules", sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False))

    # 5. Add verification_status column to loan_fees
    op.add_column("loan_fees", sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False))


def downgrade() -> None:
    # 5. Rollback loan_fees
    op.drop_column("loan_fees", "verification_status")

    # 4. Rollback loan_eligibility_rules
    op.drop_column("loan_eligibility_rules", "verification_status")

    # 3. Rollback interest_rates
    op.drop_column("interest_rates", "verification_status")

    # 2. Rollback loan_products
    op.drop_constraint("fk_loan_products_source_id", "loan_products", type_="foreignkey")
    op.drop_index("ix_loan_products_source_id", table_name="loan_products")
    op.drop_column("loan_products", "verification_status")
    op.drop_column("loan_products", "retrieved_at")
    op.drop_column("loan_products", "source_record_id")
    op.drop_column("loan_products", "source_id")

    # 1. Rollback banks
    op.drop_column("banks", "verification_status")
    op.drop_column("banks", "retrieved_at")
    op.drop_column("banks", "source_record_id")
