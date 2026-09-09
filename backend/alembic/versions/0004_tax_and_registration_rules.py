"""tax and registration rules domain

Revision ID: 0004_tax_rules
Revises: 0003_location_domain
Create Date: 2026-09-09 18:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0004_tax_rules"
down_revision: Union[str, None] = "0003_location_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create tax_rules table
    op.create_table(
        "tax_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("state_id", sa.Integer(), nullable=False),
        sa.Column("city_id", sa.Integer(), nullable=True),
        sa.Column("rto_id", sa.Integer(), nullable=True),
        sa.Column("rule_category", sa.String(length=30), server_default="TAX", nullable=False),
        sa.Column("tax_type", sa.String(length=50), nullable=False),
        sa.Column("calculation_method", sa.String(length=30), server_default="PERCENTAGE", nullable=False),
        sa.Column("vehicle_type", sa.String(length=30), server_default="CAR", nullable=False),
        sa.Column("fuel_type", sa.String(length=30), nullable=True),
        sa.Column("is_ev", sa.Boolean(), nullable=True),
        sa.Column("usage_type", sa.String(length=30), server_default="PRIVATE", nullable=False),
        sa.Column("min_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("max_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("min_engine_cc", sa.Integer(), nullable=True),
        sa.Column("max_engine_cc", sa.Integer(), nullable=True),
        sa.Column("min_seating_capacity", sa.Integer(), nullable=True),
        sa.Column("max_seating_capacity", sa.Integer(), nullable=True),
        sa.Column("rate", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("fixed_amount", sa.Numeric(precision=12, scale=2), server_default="0.00", nullable=True),
        sa.Column("base_amount_type", sa.String(length=30), server_default="EX_SHOWROOM", nullable=False),
        sa.Column("formula_definition", sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_record_id", sa.String(length=255), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["state_id"], ["states.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["city_id"], ["cities.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["rto_id"], ["rto_offices.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("priority >= 0", name="chk_tax_rules_priority_non_negative"),
        sa.CheckConstraint("rate IS NULL OR rate >= 0", name="chk_tax_rules_rate_non_negative"),
        sa.CheckConstraint("fixed_amount IS NULL OR fixed_amount >= 0", name="chk_tax_rules_fixed_amount_non_negative"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="chk_tax_rules_effective_period_valid"),
        sa.CheckConstraint("min_price IS NULL OR max_price IS NULL OR max_price >= min_price", name="chk_tax_rules_price_range_valid"),
        sa.CheckConstraint("min_engine_cc IS NULL OR max_engine_cc IS NULL OR max_engine_cc >= min_engine_cc", name="chk_tax_rules_engine_cc_range_valid"),
    )

    op.create_index("ix_tax_rules_name", "tax_rules", ["name"], unique=False)
    op.create_index("ix_tax_rules_state_id", "tax_rules", ["state_id"], unique=False)
    op.create_index("ix_tax_rules_city_id", "tax_rules", ["city_id"], unique=False)
    op.create_index("ix_tax_rules_rto_id", "tax_rules", ["rto_id"], unique=False)
    op.create_index("ix_tax_rules_tax_type", "tax_rules", ["tax_type"], unique=False)
    op.create_index("ix_tax_rules_rule_category", "tax_rules", ["rule_category"], unique=False)
    op.create_index("ix_tax_rules_calculation_method", "tax_rules", ["calculation_method"], unique=False)
    op.create_index("ix_tax_rules_vehicle_type", "tax_rules", ["vehicle_type"], unique=False)
    op.create_index("ix_tax_rules_fuel_type", "tax_rules", ["fuel_type"], unique=False)
    op.create_index("ix_tax_rules_usage_type", "tax_rules", ["usage_type"], unique=False)
    op.create_index("ix_tax_rules_priority", "tax_rules", ["priority"], unique=False)
    op.create_index("ix_tax_rules_active", "tax_rules", ["active"], unique=False)
    op.create_index("ix_tax_rules_state_tax_type", "tax_rules", ["state_id", "tax_type"], unique=False)
    op.create_index("ix_tax_rules_effective_dates", "tax_rules", ["effective_from", "effective_to"], unique=False)
    op.create_index("ix_tax_rules_resolution_lookup", "tax_rules", ["state_id", "city_id", "rto_id", "active"], unique=False)

    # 2. Create tax_rule_brackets table
    op.create_table(
        "tax_rule_brackets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tax_rule_id", sa.Integer(), nullable=False),
        sa.Column("bracket_order", sa.Integer(), server_default="1", nullable=False),
        sa.Column("minimum_value", sa.Numeric(precision=12, scale=2), server_default="0.00", nullable=False),
        sa.Column("maximum_value", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("rate", sa.Numeric(precision=8, scale=4), nullable=True),
        sa.Column("fixed_amount", sa.Numeric(precision=12, scale=2), server_default="0.00", nullable=True),
        sa.Column("calculation_method", sa.String(length=30), server_default="PERCENTAGE", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["tax_rule_id"], ["tax_rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("minimum_value >= 0", name="chk_tax_brackets_min_non_negative"),
        sa.CheckConstraint("maximum_value IS NULL OR maximum_value > minimum_value", name="chk_tax_brackets_max_greater_than_min"),
        sa.CheckConstraint("rate IS NULL OR rate >= 0", name="chk_tax_brackets_rate_non_negative"),
        sa.CheckConstraint("fixed_amount IS NULL OR fixed_amount >= 0", name="chk_tax_brackets_fixed_non_negative"),
    )

    op.create_index("ix_tax_rule_brackets_tax_rule_id", "tax_rule_brackets", ["tax_rule_id"], unique=False)
    op.create_index("ix_tax_rule_brackets_rule_order", "tax_rule_brackets", ["tax_rule_id", "bracket_order"], unique=False)


def downgrade() -> None:
    op.drop_table("tax_rule_brackets")
    op.drop_table("tax_rules")
