"""initial_schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-09-09 12:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. data_sources
    op.create_table(
        'data_sources',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('slug', sa.String(length=150), nullable=False),
        sa.Column('provider_type', sa.String(length=100), nullable=False),
        sa.Column('base_url', sa.String(length=500), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_data_sources_id'), 'data_sources', ['id'], unique=False)
    op.create_index(op.f('ix_data_sources_name'), 'data_sources', ['name'], unique=True)
    op.create_index(op.f('ix_data_sources_slug'), 'data_sources', ['slug'], unique=True)

    # 2. states
    op.create_table(
        'states',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('code', sa.String(length=10), nullable=False),
        sa.Column('is_ut', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_states_id'), 'states', ['id'], unique=False)
    op.create_index(op.f('ix_states_name'), 'states', ['name'], unique=True)
    op.create_index(op.f('ix_states_code'), 'states', ['code'], unique=True)

    # 3. cities
    op.create_table(
        'cities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('state_id', sa.Integer(), nullable=False),
        sa.Column('tier', sa.String(length=10), nullable=False, server_default='Tier 1'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['state_id'], ['states.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_cities_id'), 'cities', ['id'], unique=False)
    op.create_index(op.f('ix_cities_name'), 'cities', ['name'], unique=False)
    op.create_index(op.f('ix_cities_slug'), 'cities', ['slug'], unique=True)
    op.create_index(op.f('ix_cities_state_id'), 'cities', ['state_id'], unique=False)

    # 4. rto_offices
    op.create_table(
        'rto_offices',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('code', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('state_id', sa.Integer(), nullable=False),
        sa.Column('city_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['city_id'], ['cities.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['state_id'], ['states.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_rto_offices_id'), 'rto_offices', ['id'], unique=False)
    op.create_index(op.f('ix_rto_offices_code'), 'rto_offices', ['code'], unique=True)
    op.create_index(op.f('ix_rto_offices_state_id'), 'rto_offices', ['state_id'], unique=False)
    op.create_index(op.f('ix_rto_offices_city_id'), 'rto_offices', ['city_id'], unique=False)

    # 5. tax_slabs
    op.create_table(
        'tax_slabs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('state_id', sa.Integer(), nullable=False),
        sa.Column('fuel_type', sa.String(length=30), nullable=False),
        sa.Column('min_ex_showroom', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('max_ex_showroom', sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column('tax_percent', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('cess_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.00'),
        sa.Column('flat_registration_fee', sa.Numeric(precision=10, scale=2), nullable=False, server_default='600.00'),
        sa.Column('fastag_fee', sa.Numeric(precision=10, scale=2), nullable=False, server_default='600.00'),
        sa.Column('green_cess_amount', sa.Numeric(precision=10, scale=2), nullable=False, server_default='0.00'),
        sa.Column('is_bh_series', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_verified_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['state_id'], ['states.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_tax_slabs_id'), 'tax_slabs', ['id'], unique=False)
    op.create_index(op.f('ix_tax_slabs_state_id'), 'tax_slabs', ['state_id'], unique=False)
    op.create_index(op.f('ix_tax_slabs_fuel_type'), 'tax_slabs', ['fuel_type'], unique=False)

    # 6. manufacturers
    op.create_table(
        'manufacturers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('country_of_origin', sa.String(length=50), nullable=False, server_default='India'),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_verified_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_manufacturers_id'), 'manufacturers', ['id'], unique=False)
    op.create_index(op.f('ix_manufacturers_name'), 'manufacturers', ['name'], unique=True)
    op.create_index(op.f('ix_manufacturers_slug'), 'manufacturers', ['slug'], unique=True)

    # 7. car_models
    op.create_table(
        'car_models',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('manufacturer_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('body_type', sa.String(length=50), nullable=False),
        sa.Column('image_url', sa.String(length=500), nullable=True),
        sa.Column('launch_year', sa.Integer(), nullable=False, server_default='2024'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_discontinued', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_verified_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['manufacturer_id'], ['manufacturers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_car_models_id'), 'car_models', ['id'], unique=False)
    op.create_index(op.f('ix_car_models_manufacturer_id'), 'car_models', ['manufacturer_id'], unique=False)
    op.create_index(op.f('ix_car_models_name'), 'car_models', ['name'], unique=False)
    op.create_index(op.f('ix_car_models_slug'), 'car_models', ['slug'], unique=True)
    op.create_index(op.f('ix_car_models_body_type'), 'car_models', ['body_type'], unique=False)

    # 8. variants
    op.create_table(
        'variants',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('model_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('slug', sa.String(length=150), nullable=False),
        sa.Column('trim_level', sa.String(length=50), nullable=False, server_default='Base'),
        sa.Column('fuel_type', sa.String(length=30), nullable=False),
        sa.Column('transmission', sa.String(length=50), nullable=False),
        sa.Column('seating_capacity', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_verified_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['model_id'], ['car_models.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_variants_id'), 'variants', ['id'], unique=False)
    op.create_index(op.f('ix_variants_model_id'), 'variants', ['model_id'], unique=False)
    op.create_index(op.f('ix_variants_name'), 'variants', ['name'], unique=False)
    op.create_index(op.f('ix_variants_slug'), 'variants', ['slug'], unique=True)
    op.create_index(op.f('ix_variants_fuel_type'), 'variants', ['fuel_type'], unique=False)
    op.create_index(op.f('ix_variants_transmission'), 'variants', ['transmission'], unique=False)

    # 9. variant_specifications
    op.create_table(
        'variant_specifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=False),
        sa.Column('engine_displacement_cc', sa.Integer(), nullable=True),
        sa.Column('battery_capacity_kwh', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('max_power_bhp', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('max_torque_nm', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('arai_mileage_kmpl', sa.Numeric(precision=5, scale=2), nullable=False, server_default='18.00'),
        sa.Column('fuel_tank_capacity_l', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('boot_space_l', sa.Integer(), nullable=True),
        sa.Column('airbags_count', sa.Integer(), nullable=False, server_default='6'),
        sa.Column('safety_rating_stars', sa.Integer(), nullable=True),
        sa.Column('ground_clearance_mm', sa.Integer(), nullable=True),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_verified_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['variant_id'], ['variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('variant_id'),
    )
    op.create_index(op.f('ix_variant_specifications_id'), 'variant_specifications', ['id'], unique=False)

    # 10. ex_showroom_prices
    op.create_table(
        'ex_showroom_prices',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=False),
        sa.Column('state_id', sa.Integer(), nullable=True),
        sa.Column('city_id', sa.Integer(), nullable=True),
        sa.Column('price_inr', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('is_current', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_verified_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['city_id'], ['cities.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['state_id'], ['states.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ex_showroom_prices_id'), 'ex_showroom_prices', ['id'], unique=False)
    op.create_index(op.f('ix_ex_showroom_prices_variant_id'), 'ex_showroom_prices', ['variant_id'], unique=False)
    op.create_index(op.f('ix_ex_showroom_prices_state_id'), 'ex_showroom_prices', ['state_id'], unique=False)
    op.create_index(op.f('ix_ex_showroom_prices_city_id'), 'ex_showroom_prices', ['city_id'], unique=False)

    # 11. price_histories
    op.create_table(
        'price_histories',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=False),
        sa.Column('state_id', sa.Integer(), nullable=True),
        sa.Column('price_inr', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('change_reason', sa.String(length=255), nullable=True),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['state_id'], ['states.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_price_histories_id'), 'price_histories', ['id'], unique=False)
    op.create_index(op.f('ix_price_histories_variant_id'), 'price_histories', ['variant_id'], unique=False)

    # 12. banks
    op.create_table(
        'banks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('bank_type', sa.String(length=50), nullable=False, server_default='Public'),
        sa.Column('logo_url', sa.String(length=500), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_verified_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_banks_id'), 'banks', ['id'], unique=False)
    op.create_index(op.f('ix_banks_name'), 'banks', ['name'], unique=True)
    op.create_index(op.f('ix_banks_slug'), 'banks', ['slug'], unique=True)

    # 13. loan_products
    op.create_table(
        'loan_products',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('bank_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('slug', sa.String(length=150), nullable=False),
        sa.Column('min_loan_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='100000.00'),
        sa.Column('max_loan_amount', sa.Numeric(precision=12, scale=2), nullable=False, server_default='10000000.00'),
        sa.Column('min_tenure_months', sa.Integer(), nullable=False, server_default='12'),
        sa.Column('max_tenure_months', sa.Integer(), nullable=False, server_default='84'),
        sa.Column('max_ltv_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='90.00'),
        sa.Column('processing_fee_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.50'),
        sa.Column('min_processing_fee', sa.Numeric(precision=10, scale=2), nullable=False, server_default='1500.00'),
        sa.Column('max_processing_fee', sa.Numeric(precision=10, scale=2), nullable=False, server_default='10000.00'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_verified_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['bank_id'], ['banks.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_loan_products_id'), 'loan_products', ['id'], unique=False)
    op.create_index(op.f('ix_loan_products_bank_id'), 'loan_products', ['bank_id'], unique=False)
    op.create_index(op.f('ix_loan_products_slug'), 'loan_products', ['slug'], unique=False)

    # 14. interest_rate_slabs
    op.create_table(
        'interest_rate_slabs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('loan_product_id', sa.Integer(), nullable=False),
        sa.Column('min_cibil_score', sa.Integer(), nullable=False, server_default='300'),
        sa.Column('max_cibil_score', sa.Integer(), nullable=False, server_default='900'),
        sa.Column('min_interest_rate', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('max_interest_rate', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('default_interest_rate', sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column('is_fixed', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_verified_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['loan_product_id'], ['loan_products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_interest_rate_slabs_id'), 'interest_rate_slabs', ['id'], unique=False)
    op.create_index(op.f('ix_interest_rate_slabs_loan_product_id'), 'interest_rate_slabs', ['loan_product_id'], unique=False)

    # 15. insurance_rate_rules
    op.create_table(
        'insurance_rate_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('min_engine_cc', sa.Integer(), nullable=True),
        sa.Column('max_engine_cc', sa.Integer(), nullable=True),
        sa.Column('is_ev', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('third_party_3yr_tariff_inr', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('own_damage_base_rate_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='2.80'),
        sa.Column('zero_dep_addon_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.70'),
        sa.Column('engine_protect_addon_inr', sa.Numeric(precision=10, scale=2), nullable=False, server_default='1500.00'),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('source', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(length=1024), nullable=True),
        sa.Column('effective_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_verified_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_insurance_rate_rules_id'), 'insurance_rate_rules', ['id'], unique=False)


def downgrade() -> None:
    op.drop_table('insurance_rate_rules')
    op.drop_table('interest_rate_slabs')
    op.drop_table('loan_products')
    op.drop_table('banks')
    op.drop_table('price_histories')
    op.drop_table('ex_showroom_prices')
    op.drop_table('variant_specifications')
    op.drop_table('variants')
    op.drop_table('car_models')
    op.drop_table('manufacturers')
    op.drop_table('tax_slabs')
    op.drop_table('rto_offices')
    op.drop_table('cities')
    op.drop_table('states')
    op.drop_table('data_sources')
