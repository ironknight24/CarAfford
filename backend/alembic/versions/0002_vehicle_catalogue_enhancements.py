"""vehicle_catalogue_enhancements

Revision ID: 0002_vehicle_catalogue
Revises: 0001_initial
Create Date: 2026-09-09 18:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002_vehicle_catalogue'
down_revision: Union[str, None] = '0001_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Update manufacturers
    with op.batch_alter_table('manufacturers') as batch_op:
        batch_op.add_column(sa.Column('country', sa.String(length=50), nullable=False, server_default='India'))
        batch_op.add_column(sa.Column('active', sa.Boolean(), nullable=False, server_default='true'))
        batch_op.create_index('ix_manufacturers_active', ['active'], unique=False)

    # 2. Update car_models
    with op.batch_alter_table('car_models') as batch_op:
        batch_op.add_column(sa.Column('segment', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('active', sa.Boolean(), nullable=False, server_default='true'))
        batch_op.add_column(sa.Column('launch_date', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('discontinued_date', sa.Date(), nullable=True))
        batch_op.create_index('ix_car_models_active', ['active'], unique=False)
        batch_op.create_index('ix_car_models_segment', ['segment'], unique=False)
        batch_op.create_unique_constraint('uq_car_models_manufacturer_name', ['manufacturer_id', 'name'])

    # 3. Update variants
    with op.batch_alter_table('variants') as batch_op:
        batch_op.add_column(sa.Column('drivetrain', sa.String(length=20), nullable=True, server_default='FWD'))
        batch_op.add_column(sa.Column('engine_cc', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('engine_power_bhp', sa.Numeric(precision=6, scale=2), nullable=True))
        batch_op.add_column(sa.Column('torque_nm', sa.Numeric(precision=6, scale=2), nullable=True))
        batch_op.add_column(sa.Column('mileage_claimed', sa.Numeric(precision=6, scale=2), nullable=True))
        batch_op.add_column(sa.Column('battery_capacity_kwh', sa.Numeric(precision=6, scale=2), nullable=True))
        batch_op.add_column(sa.Column('range_km', sa.Numeric(precision=6, scale=2), nullable=True))
        batch_op.add_column(sa.Column('active', sa.Boolean(), nullable=False, server_default='true'))
        batch_op.create_index('ix_variants_active', ['active'], unique=False)
        batch_op.create_index('ix_variants_drivetrain', ['drivetrain'], unique=False)

    # 4. Create vehicle_prices table
    op.create_table(
        'vehicle_prices',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=False),
        sa.Column('ex_showroom_price', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('price_type', sa.String(length=30), nullable=False, server_default='EX_SHOWROOM'),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=False),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_id', sa.Integer(), nullable=True),
        sa.Column('source_record_id', sa.String(length=255), nullable=True),
        sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('ex_showroom_price > 0', name='chk_vehicle_prices_amount_positive'),
        sa.CheckConstraint('effective_to IS NULL OR effective_to >= effective_from', name='chk_vehicle_prices_period_valid'),
        sa.ForeignKeyConstraint(['source_id'], ['data_sources.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['variant_id'], ['variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_vehicle_prices_id'), 'vehicle_prices', ['id'], unique=False)
    op.create_index(op.f('ix_vehicle_prices_variant_id'), 'vehicle_prices', ['variant_id'], unique=False)
    op.create_index(op.f('ix_vehicle_prices_price_type'), 'vehicle_prices', ['price_type'], unique=False)
    op.create_index(op.f('ix_vehicle_prices_effective_from'), 'vehicle_prices', ['effective_from'], unique=False)
    op.create_index(op.f('ix_vehicle_prices_effective_to'), 'vehicle_prices', ['effective_to'], unique=False)
    op.create_index(op.f('ix_vehicle_prices_source_id'), 'vehicle_prices', ['source_id'], unique=False)

    # 5. Create vehicle_media table
    op.create_table(
        'vehicle_media',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('variant_id', sa.Integer(), nullable=True),
        sa.Column('model_id', sa.Integer(), nullable=True),
        sa.Column('media_type', sa.String(length=50), nullable=False, server_default='IMAGE_EXTERIOR'),
        sa.Column('url', sa.String(length=1024), nullable=False),
        sa.Column('alt_text', sa.String(length=255), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint('variant_id IS NOT NULL OR model_id IS NOT NULL', name='chk_vehicle_media_target_not_null'),
        sa.ForeignKeyConstraint(['model_id'], ['car_models.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['variant_id'], ['variants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_vehicle_media_id'), 'vehicle_media', ['id'], unique=False)
    op.create_index(op.f('ix_vehicle_media_variant_id'), 'vehicle_media', ['variant_id'], unique=False)
    op.create_index(op.f('ix_vehicle_media_model_id'), 'vehicle_media', ['model_id'], unique=False)
    op.create_index(op.f('ix_vehicle_media_media_type'), 'vehicle_media', ['media_type'], unique=False)


def downgrade() -> None:
    op.drop_table('vehicle_media')
    op.drop_table('vehicle_prices')

    with op.batch_alter_table('variants') as batch_op:
        batch_op.drop_index('ix_variants_drivetrain')
        batch_op.drop_index('ix_variants_active')
        batch_op.drop_column('active')
        batch_op.drop_column('range_km')
        batch_op.drop_column('battery_capacity_kwh')
        batch_op.drop_column('mileage_claimed')
        batch_op.drop_column('torque_nm')
        batch_op.drop_column('engine_power_bhp')
        batch_op.drop_column('engine_cc')
        batch_op.drop_column('drivetrain')

    with op.batch_alter_table('car_models') as batch_op:
        batch_op.drop_constraint('uq_car_models_manufacturer_name', type_='unique')
        batch_op.drop_index('ix_car_models_segment')
        batch_op.drop_index('ix_car_models_active')
        batch_op.drop_column('discontinued_date')
        batch_op.drop_column('launch_date')
        batch_op.drop_column('active')
        batch_op.drop_column('segment')

    with op.batch_alter_table('manufacturers') as batch_op:
        batch_op.drop_index('ix_manufacturers_active')
        batch_op.drop_column('active')
        batch_op.drop_column('country')
