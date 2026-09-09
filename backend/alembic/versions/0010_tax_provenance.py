"""tax provenance and verification status

Revision ID: 0010_tax_provenance
Revises: 0009_finance_provenance
Create Date: 2026-09-09 23:53:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0010_tax_provenance"
down_revision: Union[str, None] = "0009_finance_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add verification_status column to tax_rules
    op.add_column(
        "tax_rules",
        sa.Column(
            "verification_status",
            sa.String(length=50),
            server_default="DEMO",
            nullable=False,
        ),
    )


def downgrade() -> None:
    # 1. Rollback tax_rules
    op.drop_column("tax_rules", "verification_status")
