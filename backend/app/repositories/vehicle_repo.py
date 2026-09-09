from decimal import Decimal
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.vehicle import CarModel, Manufacturer, Variant, VariantSpecification
from app.schemas.vehicle import VehicleFilterParams


class VehicleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_manufacturers(self, active_only: bool = True) -> List[Manufacturer]:
        stmt = select(Manufacturer)
        if active_only:
            stmt = stmt.where(Manufacturer.is_active == True)
        stmt = stmt.order_by(Manufacturer.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_models(
        self,
        manufacturer_id: Optional[int] = None,
        body_type: Optional[str] = None,
    ) -> List[CarModel]:
        stmt = select(CarModel).options(selectinload(CarModel.manufacturer))
        if manufacturer_id:
            stmt = stmt.where(CarModel.manufacturer_id == manufacturer_id)
        if body_type:
            stmt = stmt.where(CarModel.body_type.ilike(f"%{body_type}%"))
        stmt = stmt.order_by(CarModel.name)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_variant_by_id(self, variant_id: int) -> Optional[Variant]:
        stmt = (
            select(Variant)
            .options(
                selectinload(Variant.model).selectinload(CarModel.manufacturer),
                selectinload(Variant.specification),
                selectinload(Variant.ex_showroom_prices),
            )
            .where(Variant.id == variant_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_all_active_variants(self) -> List[Variant]:
        stmt = (
            select(Variant)
            .options(
                selectinload(Variant.model).selectinload(CarModel.manufacturer),
                selectinload(Variant.specification),
                selectinload(Variant.ex_showroom_prices),
            )
            .where(Variant.is_active == True)
            .order_by(Variant.name)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def filter_variants(self, params: VehicleFilterParams) -> List[Variant]:
        stmt = (
            select(Variant)
            .join(CarModel, Variant.model_id == CarModel.id)
            .join(Manufacturer, CarModel.manufacturer_id == Manufacturer.id)
            .outerjoin(VariantSpecification, Variant.id == VariantSpecification.variant_id)
            .options(
                selectinload(Variant.model).selectinload(CarModel.manufacturer),
                selectinload(Variant.specification),
                selectinload(Variant.ex_showroom_prices),
            )
            .where(Variant.is_active == True)
        )

        if params.manufacturer_id:
            stmt = stmt.where(CarModel.manufacturer_id == params.manufacturer_id)
        if params.body_type:
            stmt = stmt.where(CarModel.body_type.ilike(f"%{params.body_type}%"))
        if params.fuel_type:
            stmt = stmt.where(Variant.fuel_type.ilike(f"%{params.fuel_type}%"))
        if params.transmission:
            stmt = stmt.where(Variant.transmission.ilike(f"%{params.transmission}%"))
        if params.min_seating:
            stmt = stmt.where(Variant.seating_capacity >= params.min_seating)
        if params.min_safety_rating:
            stmt = stmt.where(VariantSpecification.safety_rating_stars >= params.min_safety_rating)
        if params.search:
            search_term = f"%{params.search}%"
            stmt = stmt.where(
                (Variant.name.ilike(search_term))
                | (CarModel.name.ilike(search_term))
                | (Manufacturer.name.ilike(search_term))
            )

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
