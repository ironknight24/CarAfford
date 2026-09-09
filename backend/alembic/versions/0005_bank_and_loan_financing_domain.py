"""bank and car loan financing domain

Revision ID: 0005_financing_domain
Revises: 0004_tax_rules
Create Date: 2026-09-09 19:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0005_financing_domain"
down_revision: Union[str, None] = "0004_tax_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update banks table if needed
    # Note: banks table already created in initial migration with id, name, slug, bank_type, logo_url, is_active, created_at, updated_at
    with op.batch_alter_table("banks") as batch_op:
        batch_op.add_column(sa.Column("website_url", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False))
        batch_op.add_column(sa.Column("source_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key("fk_banks_source_id_data_sources", "data_sources", ["source_id"], ["id"], ondelete="SET NULL")
        batch_op.create_index("ix_banks_active", ["active"])

    # 2. Update loan_products table
    with op.batch_alter_table("loan_products") as batch_op:
        batch_op.add_column(sa.Column("vehicle_type", sa.String(length=50), server_default="CAR", nullable=False))
        batch_op.add_column(sa.Column("vehicle_condition", sa.String(length=50), server_default="NEW", nullable=False))
        batch_op.add_column(sa.Column("product_category", sa.String(length=50), server_default="STANDARD", nullable=False))
        batch_op.add_column(sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False))
        batch_op.create_index("ix_loan_products_active", ["active"])

    # 3. Create interest_rates table
    op.create_table(
        "interest_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("loan_product_id", sa.Integer(), nullable=False),
        sa.Column("annual_interest_rate", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("rate_type", sa.String(length=30), server_default="FLOATING", nullable=False),
        sa.Column("min_credit_score", sa.Integer(), nullable=True),
        sa.Column("max_credit_score", sa.Integer(), nullable=True),
        sa.Column("min_tenure_months", sa.Integer(), nullable=True),
        sa.Column("max_tenure_months", sa.Integer(), nullable=True),
        sa.Column("min_loan_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("max_loan_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("employment_type", sa.String(length=50), nullable=True),
        sa.Column("priority", sa.Integer(), server_default="100", nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_record_id", sa.String(length=255), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["loan_product_id"], ["loan_products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("annual_interest_rate >= 0", name="chk_interest_rates_rate_non_negative"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="chk_interest_rates_period_valid"),
    )
    op.create_index("ix_interest_rates_loan_product_id", "interest_rates", ["loan_product_id"])
    op.create_index("ix_interest_rates_active", "interest_rates", ["active"])
    op.create_index("ix_interest_rates_priority", "interest_rates", ["priority"])
    op.create_index("ix_interest_rates_effective_from", "interest_rates", ["effective_from"])
    op.create_index("ix_interest_rates_effective_to", "interest_rates", ["effective_to"])
    op.create_index("ix_interest_rates_resolution", "interest_rates", ["loan_product_id", "active", "effective_from", "effective_to"])

    # 4. Create loan_eligibility_rules table
    op.create_table(
        "loan_eligibility_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("loan_product_id", sa.Integer(), nullable=False),
        sa.Column("rule_name", sa.String(length=150), nullable=False),
        sa.Column("min_monthly_income", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("min_credit_score", sa.Integer(), nullable=True),
        sa.Column("max_credit_score", sa.Integer(), nullable=True),
        sa.Column("max_loan_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("max_ltv_percent", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("max_foir_percent", sa.Numeric(precision=5, scale=2), server_default="50.00", nullable=True),
        sa.Column("min_age_years", sa.Integer(), server_default="21", nullable=True),
        sa.Column("max_age_years", sa.Integer(), server_default="65", nullable=True),
        sa.Column("min_employment_months", sa.Integer(), server_default="12", nullable=True),
        sa.Column("allowed_employment_types", sa.String(length=150), server_default="SALARIED,SELF_EMPLOYED", nullable=True),
        sa.Column("allowed_residency_types", sa.String(length=150), server_default="RESIDENT_INDIAN,NRI", nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_record_id", sa.String(length=255), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["loan_product_id"], ["loan_products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="chk_eligibility_rules_period_valid"),
    )
    op.create_index("ix_loan_eligibility_rules_loan_product_id", "loan_eligibility_rules", ["loan_product_id"])
    op.create_index("ix_loan_eligibility_rules_active", "loan_eligibility_rules", ["active"])

    # 5. Create loan_fees table
    op.create_table(
        "loan_fees",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("loan_product_id", sa.Integer(), nullable=False),
        sa.Column("fee_name", sa.String(length=150), nullable=False),
        sa.Column("fee_type", sa.String(length=50), server_default="PROCESSING_FEE", nullable=False),
        sa.Column("calculation_method", sa.String(length=30), server_default="PERCENTAGE", nullable=False),
        sa.Column("fixed_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("minimum_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("maximum_amount", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("source_record_id", sa.String(length=255), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.ForeignKeyConstraint(["loan_product_id"], ["loan_products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["data_sources.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("effective_to IS NULL OR effective_to >= effective_from", name="chk_loan_fees_period_valid"),
    )
    op.create_index("ix_loan_fees_loan_product_id", "loan_fees", ["loan_product_id"])
    op.create_index("ix_loan_fees_fee_type", "loan_fees", ["fee_type"])
    op.create_index("ix_loan_fees_active", "loan_fees", ["active"])


def downgrade() -> None:
    op.drop_table("loan_fees")
    op.drop_table("loan_eligibility_rules")
    op.drop_table("interest_rates")
    with op.batch_alter_table("loan_products") as batch_op:
        batch_op.drop_column("active")
        batch_op.drop_column("product_category")
        batch_op.drop_column("vehicle_condition")
        batch_op.drop_column("vehicle_type")
    with op.batch_alter_table("banks") as batch_op:
        batch_op.drop_column("source_id")
        batch_op.drop_column("active")
        batch_op.drop_column("website_url")
