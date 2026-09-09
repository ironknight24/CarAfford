"""location domain enhancements

Revision ID: 0003_location_domain
Revises: 0002_catalogue_domain
Create Date: 2026-09-09 18:41:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003_location_domain"
down_revision: Union[str, None] = "0002_catalogue_domain"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create countries table
    op.create_table(
        "countries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("iso_code", sa.String(length=2), nullable=False),
        sa.Column("iso3_code", sa.String(length=3), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_countries_name", "countries", ["name"], unique=True)
    op.create_index("ix_countries_iso_code", "countries", ["iso_code"], unique=True)
    op.create_index("ix_countries_iso3_code", "countries", ["iso3_code"], unique=True)
    op.create_index("ix_countries_active", "countries", ["active"], unique=False)

    # Insert default India country record for existing state foreign keys
    op.execute(
        sa.text(
            "INSERT INTO countries (id, name, iso_code, iso3_code, active, created_at, updated_at) "
            "VALUES (1, 'India', 'IN', 'IND', true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
            "ON CONFLICT (name) DO NOTHING"
        )
    )

    # 2. Update states table
    op.add_column("states", sa.Column("country_id", sa.Integer(), server_default="1", nullable=False))
    op.add_column("states", sa.Column("region_type", sa.String(length=30), server_default="STATE", nullable=False))
    op.add_column("states", sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.create_index("ix_states_country_id", "states", ["country_id"], unique=False)
    op.create_index("ix_states_region_type", "states", ["region_type"], unique=False)
    op.create_index("ix_states_active", "states", ["active"], unique=False)
    op.create_foreign_key("fk_states_country_id", "states", "countries", ["country_id"], ["id"], ondelete="CASCADE")
    op.create_unique_constraint("uq_states_country_code", "states", ["country_id", "code"])
    op.create_unique_constraint("uq_states_country_name", "states", ["country_id", "name"])

    # 3. Update cities table
    op.add_column("cities", sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.create_index("ix_cities_active", "cities", ["active"], unique=False)
    op.create_unique_constraint("uq_cities_state_name", "cities", ["state_id", "name"])
    op.create_unique_constraint("uq_cities_state_slug", "cities", ["state_id", "slug"])

    # 4. Update rto_offices table
    op.add_column("rto_offices", sa.Column("jurisdiction", sa.String(length=255), nullable=True))
    op.add_column("rto_offices", sa.Column("active", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("rto_offices", sa.Column("source_id", sa.Integer(), nullable=True))
    op.add_column("rto_offices", sa.Column("source_record_id", sa.String(length=255), nullable=True))
    op.add_column("rto_offices", sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_rto_offices_active", "rto_offices", ["active"], unique=False)
    op.create_index("ix_rto_offices_source_id", "rto_offices", ["source_id"], unique=False)
    op.create_foreign_key("fk_rto_offices_source_id", "rto_offices", "data_sources", ["source_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_rto_offices_state_code", "rto_offices", ["state_id", "code"])


def downgrade() -> None:
    # 4. Rollback rto_offices
    op.drop_constraint("uq_rto_offices_state_code", "rto_offices", type_="unique")
    op.drop_constraint("fk_rto_offices_source_id", "rto_offices", type_="foreignkey")
    op.drop_index("ix_rto_offices_source_id", table_name="rto_offices")
    op.drop_index("ix_rto_offices_active", table_name="rto_offices")
    op.drop_column("rto_offices", "retrieved_at")
    op.drop_column("rto_offices", "source_record_id")
    op.drop_column("rto_offices", "source_id")
    op.drop_column("rto_offices", "active")
    op.drop_column("rto_offices", "jurisdiction")

    # 3. Rollback cities
    op.drop_constraint("uq_cities_state_slug", "cities", type_="unique")
    op.drop_constraint("uq_cities_state_name", "cities", type_="unique")
    op.drop_index("ix_cities_active", table_name="cities")
    op.drop_column("cities", "active")

    # 2. Rollback states
    op.drop_constraint("uq_states_country_name", "states", type_="unique")
    op.drop_constraint("uq_states_country_code", "states", type_="unique")
    op.drop_constraint("fk_states_country_id", "states", type_="foreignkey")
    op.drop_index("ix_states_active", table_name="states")
    op.drop_index("ix_states_region_type", table_name="states")
    op.drop_index("ix_states_country_id", table_name="states")
    op.drop_column("states", "active")
    op.drop_column("states", "region_type")
    op.drop_column("states", "country_id")

    # 1. Rollback countries
    op.drop_index("ix_countries_active", table_name="countries")
    op.drop_index("ix_countries_iso3_code", table_name="countries")
    op.drop_index("ix_countries_iso_code", table_name="countries")
    op.drop_index("ix_countries_name", table_name="countries")
    op.drop_table("countries")
