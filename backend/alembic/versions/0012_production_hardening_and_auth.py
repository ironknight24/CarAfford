"""production hardening and auth

Revision ID: 0012_production_hardening_and_auth
Revises: 0011_tco_provenance
Create Date: 2026-09-10 00:40:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0012_prod_hardening_auth"
down_revision: Union[str, None] = "0011_tco_provenance"

branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=50), server_default="USER", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_superuser", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_role", "users", ["role"])

    # 2. audit_logs table
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_email", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=True),
        sa.Column("previous_value", sa.JSON(), nullable=True),
        sa.Column("new_value", sa.JSON(), nullable=True),
        sa.Column("justification", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(length=100), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_id", "audit_logs", ["id"])
    op.create_index("ix_audit_logs_user_id", "audit_logs", ["user_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_entity_type", "audit_logs", ["entity_type"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    # 3. Composite performance indexes on high-frequency tables
    op.execute("CREATE INDEX IF NOT EXISTS ix_variants_model_fuel_trans ON variants (model_id, fuel_type, transmission);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_vehicle_prices_variant_dates ON vehicle_prices (variant_id, effective_from, effective_to);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_ex_showroom_prices_variant_state ON ex_showroom_prices (variant_id, state_id, is_current);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_tax_rules_state_fuel_dates ON tax_rules (state_id, fuel_type, effective_from, effective_to);")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_tax_rules_state_fuel_dates;")
    op.execute("DROP INDEX IF EXISTS ix_ex_showroom_prices_variant_state;")
    op.execute("DROP INDEX IF EXISTS ix_vehicle_prices_variant_dates;")
    op.execute("DROP INDEX IF EXISTS ix_variants_model_fuel_trans;")
    op.drop_table("audit_logs")
    op.drop_table("users")


