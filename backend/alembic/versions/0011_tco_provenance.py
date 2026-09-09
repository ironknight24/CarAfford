"""tco provenance and canonical tables

Revision ID: 0011_tco_provenance
Revises: 0010_tax_provenance
Create Date: 2026-09-10 00:06:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0011_tco_provenance"
down_revision: Union[str, None] = "0010_tax_provenance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. fuel_prices table
    op.create_table(
        "fuel_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fuel_type", sa.String(length=50), nullable=False),
        sa.Column("state_id", sa.Integer(), sa.ForeignKey("states.id"), nullable=True),
        sa.Column("state_code", sa.String(length=10), nullable=True),
        sa.Column("city_id", sa.Integer(), sa.ForeignKey("cities.id"), nullable=True),
        sa.Column("city_name", sa.String(length=100), nullable=True),
        sa.Column("price_per_unit", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit", sa.String(length=20), server_default="Litre", nullable=False),
        sa.Column("currency", sa.String(length=10), server_default="INR", nullable=False),
        sa.Column("observed_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("data_sources.id"), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("source_record_id", sa.String(length=100), nullable=True),
        sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fuel_prices_fuel_type", "fuel_prices", ["fuel_type"])
    op.create_index("ix_fuel_prices_state_id", "fuel_prices", ["state_id"])
    op.create_index("ix_fuel_prices_state_code", "fuel_prices", ["state_code"])
    op.create_index("ix_fuel_prices_city_id", "fuel_prices", ["city_id"])
    op.create_index("ix_fuel_prices_observed_date", "fuel_prices", ["observed_date"])
    op.create_index("ix_fuel_prices_is_active", "fuel_prices", ["is_active"])

    # 2. electricity_tariffs table
    op.create_table(
        "electricity_tariffs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tariff_type", sa.String(length=50), server_default="DOMESTIC_SLAB", nullable=False),
        sa.Column("state_id", sa.Integer(), sa.ForeignKey("states.id"), nullable=True),
        sa.Column("state_code", sa.String(length=10), nullable=True),
        sa.Column("discom_name", sa.String(length=100), nullable=True),
        sa.Column("rate_per_kwh", sa.Numeric(10, 2), nullable=False),
        sa.Column("fixed_charge_per_month", sa.Numeric(10, 2), nullable=True),
        sa.Column("currency", sa.String(length=10), server_default="INR", nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("data_sources.id"), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_electricity_tariffs_state_id", "electricity_tariffs", ["state_id"])
    op.create_index("ix_electricity_tariffs_state_code", "electricity_tariffs", ["state_code"])
    op.create_index("ix_electricity_tariffs_is_active", "electricity_tariffs", ["is_active"])

    # 3. maintenance_cost_benchmarks table
    op.create_table(
        "maintenance_cost_benchmarks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("powertrain", sa.String(length=50), nullable=False),
        sa.Column("segment", sa.String(length=50), nullable=True),
        sa.Column("manufacturer_id", sa.Integer(), sa.ForeignKey("manufacturers.id"), nullable=True),
        sa.Column("model_id", sa.Integer(), sa.ForeignKey("car_models.id"), nullable=True),
        sa.Column("annual_base_cost", sa.Numeric(10, 2), nullable=False),
        sa.Column("cost_per_km", sa.Numeric(10, 4), nullable=False),
        sa.Column("service_interval_km", sa.Integer(), server_default="10000", nullable=False),
        sa.Column("service_interval_months", sa.Integer(), server_default="12", nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("data_sources.id"), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_maintenance_powertrain", "maintenance_cost_benchmarks", ["powertrain"])
    op.create_index("ix_maintenance_segment", "maintenance_cost_benchmarks", ["segment"])
    op.create_index("ix_maintenance_is_active", "maintenance_cost_benchmarks", ["is_active"])

    # 4. insurance_renewal_benchmarks table
    op.create_table(
        "insurance_renewal_benchmarks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("fuel_type", sa.String(length=50), nullable=True),
        sa.Column("segment", sa.String(length=50), nullable=True),
        sa.Column("year_2_factor", sa.Numeric(5, 4), nullable=False),
        sa.Column("year_3_factor", sa.Numeric(5, 4), nullable=False),
        sa.Column("year_4_factor", sa.Numeric(5, 4), nullable=False),
        sa.Column("year_5_factor", sa.Numeric(5, 4), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("data_sources.id"), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_insurance_renewal_fuel_type", "insurance_renewal_benchmarks", ["fuel_type"])
    op.create_index("ix_insurance_renewal_segment", "insurance_renewal_benchmarks", ["segment"])
    op.create_index("ix_insurance_renewal_is_active", "insurance_renewal_benchmarks", ["is_active"])

    # 5. depreciation_benchmarks table
    op.create_table(
        "depreciation_benchmarks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("powertrain", sa.String(length=50), nullable=True),
        sa.Column("segment", sa.String(length=50), nullable=True),
        sa.Column("year_1_depreciation_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("year_2_depreciation_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("year_3_depreciation_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("year_4_depreciation_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("year_5_depreciation_pct", sa.Numeric(5, 2), nullable=False),
        sa.Column("methodology", sa.String(length=100), server_default="EMPIRICAL_MARKET_RESALE", nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("data_sources.id"), nullable=True),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("verification_status", sa.String(length=50), server_default="DEMO", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("updated_by", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_depreciation_powertrain", "depreciation_benchmarks", ["powertrain"])
    op.create_index("ix_depreciation_segment", "depreciation_benchmarks", ["segment"])
    op.create_index("ix_depreciation_is_active", "depreciation_benchmarks", ["is_active"])


def downgrade() -> None:
    op.drop_table("depreciation_benchmarks")
    op.drop_table("insurance_renewal_benchmarks")
    op.drop_table("maintenance_cost_benchmarks")
    op.drop_table("electricity_tariffs")
    op.drop_table("fuel_prices")
