from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import InvalidFinancialInputException, ResourceNotFoundException
from app.models.base import utc_now
from app.models.pricing import VehiclePrice
from app.models.vehicle import CarModel, Manufacturer, Variant, VariantSpecification, VehicleMedia
from app.schemas.vehicle import (
    CarModelCreate,
    ManufacturerCreate,
    VariantCreate,
    VehicleFilterParams,
    VehicleSearchResultItem,
)
from app.schemas.pricing import VehiclePriceCreate


class VehicleRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ==========================================
    # Manufacturers
    # ==========================================
    async def get_manufacturers(
        self,
        page: int = 1,
        page_size: int = 20,
        active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Manufacturer], int]:
        stmt = select(Manufacturer)
        count_stmt = select(func.count(Manufacturer.id))

        if active is not None:
            stmt = stmt.where(Manufacturer.active == active)
            count_stmt = count_stmt.where(Manufacturer.active == active)

        if search:
            search_term = f"%{search}%"
            filter_expr = or_(
                Manufacturer.name.ilike(search_term),
                Manufacturer.slug.ilike(search_term),
                Manufacturer.country.ilike(search_term),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(Manufacturer.name).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_manufacturer_by_id(self, manufacturer_id: int) -> Optional[Manufacturer]:
        stmt = (
            select(Manufacturer)
            .options(selectinload(Manufacturer.models))
            .where(Manufacturer.id == manufacturer_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_manufacturer_by_slug(self, slug: str) -> Optional[Manufacturer]:
        stmt = (
            select(Manufacturer)
            .options(selectinload(Manufacturer.models))
            .where(Manufacturer.slug == slug)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_manufacturer(
        self, manufacturer: Manufacturer | ManufacturerCreate | dict
    ) -> Manufacturer:
        if isinstance(manufacturer, dict):
            obj = Manufacturer(**manufacturer)
        elif not isinstance(manufacturer, Manufacturer):
            obj = Manufacturer(**manufacturer.model_dump(exclude_unset=True))
        else:
            obj = manufacturer
        self.session.add(obj)
        await self.session.flush()
        return obj

    # ==========================================
    # Car Models
    # ==========================================
    async def get_models(
        self,
        page: int = 1,
        page_size: int = 20,
        manufacturer_id: Optional[int] = None,
        body_type: Optional[str] = None,
        segment: Optional[str] = None,
        active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[CarModel], int]:
        stmt = select(CarModel).options(selectinload(CarModel.manufacturer))
        count_stmt = select(func.count(CarModel.id))

        if manufacturer_id:
            stmt = stmt.where(CarModel.manufacturer_id == manufacturer_id)
            count_stmt = count_stmt.where(CarModel.manufacturer_id == manufacturer_id)

        if body_type:
            stmt = stmt.where(CarModel.body_type.ilike(f"%{body_type}%"))
            count_stmt = count_stmt.where(CarModel.body_type.ilike(f"%{body_type}%"))

        if segment:
            stmt = stmt.where(CarModel.segment.ilike(f"%{segment}%"))
            count_stmt = count_stmt.where(CarModel.segment.ilike(f"%{segment}%"))

        if active is not None:
            stmt = stmt.where(CarModel.active == active)
            count_stmt = count_stmt.where(CarModel.active == active)

        if search:
            search_term = f"%{search}%"
            stmt = stmt.join(Manufacturer, CarModel.manufacturer_id == Manufacturer.id)
            count_stmt = count_stmt.join(Manufacturer, CarModel.manufacturer_id == Manufacturer.id)
            filter_expr = or_(
                CarModel.name.ilike(search_term),
                CarModel.slug.ilike(search_term),
                Manufacturer.name.ilike(search_term),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(CarModel.name).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_model_by_id(self, model_id: int) -> Optional[CarModel]:
        stmt = (
            select(CarModel)
            .options(
                selectinload(CarModel.manufacturer),
                selectinload(CarModel.variants).selectinload(Variant.prices),
                selectinload(CarModel.media),
            )
            .where(CarModel.id == model_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_model_by_slug(self, slug: str) -> Optional[CarModel]:
        stmt = (
            select(CarModel)
            .options(
                selectinload(CarModel.manufacturer),
                selectinload(CarModel.variants),
                selectinload(CarModel.media),
            )
            .where(CarModel.slug == slug)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_model(self, model: CarModel | CarModelCreate | dict) -> CarModel:
        if isinstance(model, dict):
            obj = CarModel(**model)
        elif not isinstance(model, CarModel):
            obj = CarModel(**model.model_dump(exclude_unset=True))
        else:
            obj = model
        self.session.add(obj)
        await self.session.flush()
        return obj

    # ==========================================
    # Variants
    # ==========================================
    async def get_variants(
        self,
        page: int = 1,
        page_size: int = 20,
        model_id: Optional[int] = None,
        manufacturer_id: Optional[int] = None,
        fuel_type: Optional[str] = None,
        transmission: Optional[str] = None,
        drivetrain: Optional[str] = None,
        active: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Variant], int]:
        stmt = (
            select(Variant)
            .join(CarModel, Variant.model_id == CarModel.id)
            .join(Manufacturer, CarModel.manufacturer_id == Manufacturer.id)
            .options(
                selectinload(Variant.model).selectinload(CarModel.manufacturer),
                selectinload(Variant.prices),
                selectinload(Variant.media),
                selectinload(Variant.specification),
            )
        )
        count_stmt = (
            select(func.count(Variant.id))
            .join(CarModel, Variant.model_id == CarModel.id)
            .join(Manufacturer, CarModel.manufacturer_id == Manufacturer.id)
        )

        if model_id:
            stmt = stmt.where(Variant.model_id == model_id)
            count_stmt = count_stmt.where(Variant.model_id == model_id)

        if manufacturer_id:
            stmt = stmt.where(CarModel.manufacturer_id == manufacturer_id)
            count_stmt = count_stmt.where(CarModel.manufacturer_id == manufacturer_id)

        if fuel_type:
            stmt = stmt.where(Variant.fuel_type.ilike(f"%{fuel_type}%"))
            count_stmt = count_stmt.where(Variant.fuel_type.ilike(f"%{fuel_type}%"))

        if transmission:
            stmt = stmt.where(Variant.transmission.ilike(f"%{transmission}%"))
            count_stmt = count_stmt.where(Variant.transmission.ilike(f"%{transmission}%"))

        if drivetrain:
            stmt = stmt.where(Variant.drivetrain.ilike(f"%{drivetrain}%"))
            count_stmt = count_stmt.where(Variant.drivetrain.ilike(f"%{drivetrain}%"))

        if active is not None:
            stmt = stmt.where(Variant.active == active)
            count_stmt = count_stmt.where(Variant.active == active)

        if search:
            search_term = f"%{search}%"
            filter_expr = or_(
                Variant.name.ilike(search_term),
                Variant.slug.ilike(search_term),
                CarModel.name.ilike(search_term),
                Manufacturer.name.ilike(search_term),
            )
            stmt = stmt.where(filter_expr)
            count_stmt = count_stmt.where(filter_expr)

        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        stmt = stmt.order_by(Variant.name).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_variant_by_id(self, variant_id: int) -> Optional[Variant]:
        stmt = (
            select(Variant)
            .options(
                selectinload(Variant.model).selectinload(CarModel.manufacturer),
                selectinload(Variant.prices),
                selectinload(Variant.media),
                selectinload(Variant.specification),
                selectinload(Variant.ex_showroom_prices),
            )
            .where(Variant.id == variant_id)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_variant_by_slug(self, slug: str) -> Optional[Variant]:
        stmt = (
            select(Variant)
            .options(
                selectinload(Variant.model).selectinload(CarModel.manufacturer),
                selectinload(Variant.prices),
                selectinload(Variant.media),
                selectinload(Variant.specification),
            )
            .where(Variant.slug == slug)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def create_variant(self, variant: Variant | VariantCreate | dict) -> Variant:
        if isinstance(variant, dict):
            obj = Variant(**variant)
        elif not isinstance(variant, Variant):
            obj = Variant(**variant.model_dump(exclude_unset=True))
        else:
            obj = variant
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def create_specification(self, spec: VariantSpecification | dict) -> VariantSpecification:
        if isinstance(spec, dict):
            obj = VariantSpecification(**spec)
        else:
            obj = spec
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def add_vehicle_media(self, media: VehicleMedia | dict) -> VehicleMedia:
        if isinstance(media, dict):
            obj = VehicleMedia(**media)
        else:
            obj = media
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def filter_variants(self, params: VehicleFilterParams) -> List[Variant]:
        """Legacy helper for Affordability Recommendation Engine."""
        items, _ = await self.get_variants(
            page=1,
            page_size=1000,
            manufacturer_id=params.manufacturer_id,
            fuel_type=params.fuel_type,
            transmission=params.transmission,
            active=params.active,
            search=params.search,
        )
        return items

    # ==========================================
    # Vehicle Prices & History
    # ==========================================
    async def get_current_price(
        self,
        variant_id: int,
        as_of_date: Optional[datetime] = None,
        price_type: str = "EX_SHOWROOM",
    ) -> Optional[VehiclePrice]:
        """Fetches the active/effective price for a variant as of a specific date (defaults to now)."""
        target_date = as_of_date or datetime.now(timezone.utc)
        stmt = (
            select(VehiclePrice)
            .options(selectinload(VehiclePrice.source))
            .where(
                VehiclePrice.variant_id == variant_id,
                VehiclePrice.price_type == price_type,
                VehiclePrice.effective_from <= target_date,
                or_(
                    VehiclePrice.effective_to.is_(None),
                    VehiclePrice.effective_to >= target_date,
                ),
            )
            .order_by(VehiclePrice.effective_from.desc(), VehiclePrice.id.desc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def get_price_history(
        self,
        variant_id: int,
        price_type: Optional[str] = None,
    ) -> List[VehiclePrice]:
        """Returns all historical and future price records for a variant ordered chronologically."""
        stmt = (
            select(VehiclePrice)
            .options(selectinload(VehiclePrice.source))
            .where(VehiclePrice.variant_id == variant_id)
        )
        if price_type:
            stmt = stmt.where(VehiclePrice.price_type == price_type)

        stmt = stmt.order_by(VehiclePrice.effective_from.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_prices_for_variant(
        self,
        variant_id: int,
        price_type: Optional[str] = None,
    ) -> List[VehiclePrice]:
        return await self.get_price_history(variant_id, price_type)

    async def get_price_at_date(
        self,
        variant_id: int,
        as_of_date: datetime,
        price_type: str = "EX_SHOWROOM",
    ) -> Optional[VehiclePrice]:
        return await self.get_current_price(
            variant_id, as_of_date=as_of_date, price_type=price_type
        )

    async def check_price_period_overlap(
        self,
        variant_id: int,
        price_type: str = "EX_SHOWROOM",
        effective_from: datetime = None,
        effective_to: Optional[datetime] = None,
        exclude_id: Optional[int] = None,
    ) -> bool:
        """Checks if a new price period overlaps with an existing price period for the same variant and price_type.
        Two intervals [A_from, A_to] and [B_from, B_to] overlap if:
        A_from <= (B_to or infinity) and (A_to or infinity) >= B_from
        """

        def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
            if dt is None:
                return None
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)

        n_from = to_utc(effective_from)
        n_to = to_utc(effective_to)

        stmt = select(VehiclePrice).where(
            VehiclePrice.variant_id == variant_id,
            VehiclePrice.price_type == price_type,
        )
        if exclude_id:
            stmt = stmt.where(VehiclePrice.id != exclude_id)

        result = await self.session.execute(stmt)
        existing_prices = result.scalars().all()

        for ep in existing_prices:
            ep_from = to_utc(ep.effective_from)
            ep_to = to_utc(ep.effective_to)

            # Condition for non-overlap:
            # 1. New interval is strictly before or contiguous before existing interval: n_to <= ep_from
            if n_to is not None and ep_from is not None and n_to <= ep_from:
                continue
            # 2. New interval is strictly after or contiguous after existing interval: ep_to <= n_from
            if ep_to is not None and n_from is not None and ep_to <= n_from:
                continue
            # Otherwise overlap detected
            return True

        return False

    async def add_vehicle_price(
        self,
        price: VehiclePrice | VehiclePriceCreate | dict,
        enforce_no_overlap: bool = True,
    ) -> VehiclePrice:
        if isinstance(price, dict):
            obj = VehiclePrice(**price)
        elif not isinstance(price, VehiclePrice):
            obj = VehiclePrice(**price.model_dump(exclude_unset=True))
        else:
            obj = price

        if enforce_no_overlap:
            has_overlap = await self.check_price_period_overlap(
                variant_id=obj.variant_id,
                price_type=obj.price_type,
                effective_from=obj.effective_from,
                effective_to=obj.effective_to,
            )
            if has_overlap:
                raise InvalidFinancialInputException(
                    f"Overlapping price period detected for variant {obj.variant_id} and price_type {obj.price_type}."
                )

        self.session.add(obj)
        await self.session.flush()
        return obj

    # ==========================================
    # Comprehensive Vehicle Search API
    # ==========================================
    async def search_vehicles(
        self,
        params: VehicleFilterParams,
    ) -> Tuple[List[VehicleSearchResultItem], int]:
        """Performs multi-criteria vehicle search with dynamic pagination and current price resolution."""
        now = datetime.now(timezone.utc)

        # Base query joining Variant, CarModel, Manufacturer, and latest active VehiclePrice
        stmt = (
            select(
                Variant,
                CarModel,
                Manufacturer,
                VehiclePrice,
            )
            .join(CarModel, Variant.model_id == CarModel.id)
            .join(Manufacturer, CarModel.manufacturer_id == Manufacturer.id)
            .outerjoin(
                VehiclePrice,
                (VehiclePrice.variant_id == Variant.id)
                & (VehiclePrice.price_type == "EX_SHOWROOM")
                & (VehiclePrice.effective_from <= now)
                & (or_(VehiclePrice.effective_to.is_(None), VehiclePrice.effective_to >= now)),
            )
        )

        count_stmt = (
            select(func.count(Variant.id))
            .join(CarModel, Variant.model_id == CarModel.id)
            .join(Manufacturer, CarModel.manufacturer_id == Manufacturer.id)
            .outerjoin(
                VehiclePrice,
                (VehiclePrice.variant_id == Variant.id)
                & (VehiclePrice.price_type == "EX_SHOWROOM")
                & (VehiclePrice.effective_from <= now)
                & (or_(VehiclePrice.effective_to.is_(None), VehiclePrice.effective_to >= now)),
            )
        )

        # Apply filters
        if params.active is not None:
            stmt = stmt.where(Variant.active == params.active)
            count_stmt = count_stmt.where(Variant.active == params.active)

        if params.manufacturer:
            m_filter = or_(
                Manufacturer.name.ilike(f"%{params.manufacturer}%"),
                Manufacturer.slug.ilike(f"%{params.manufacturer}%"),
            )
            stmt = stmt.where(m_filter)
            count_stmt = count_stmt.where(m_filter)

        if params.manufacturer_id:
            stmt = stmt.where(Manufacturer.id == params.manufacturer_id)
            count_stmt = count_stmt.where(Manufacturer.id == params.manufacturer_id)

        if params.model:
            mod_filter = or_(
                CarModel.name.ilike(f"%{params.model}%"),
                CarModel.slug.ilike(f"%{params.model}%"),
            )
            stmt = stmt.where(mod_filter)
            count_stmt = count_stmt.where(mod_filter)

        if params.model_id:
            stmt = stmt.where(CarModel.id == params.model_id)
            count_stmt = count_stmt.where(CarModel.id == params.model_id)

        if params.fuel_type:
            stmt = stmt.where(Variant.fuel_type.ilike(f"%{params.fuel_type}%"))
            count_stmt = count_stmt.where(Variant.fuel_type.ilike(f"%{params.fuel_type}%"))

        if params.transmission:
            stmt = stmt.where(Variant.transmission.ilike(f"%{params.transmission}%"))
            count_stmt = count_stmt.where(Variant.transmission.ilike(f"%{params.transmission}%"))

        if params.body_type:
            stmt = stmt.where(CarModel.body_type.ilike(f"%{params.body_type}%"))
            count_stmt = count_stmt.where(CarModel.body_type.ilike(f"%{params.body_type}%"))

        if params.segment:
            stmt = stmt.where(CarModel.segment.ilike(f"%{params.segment}%"))
            count_stmt = count_stmt.where(CarModel.segment.ilike(f"%{params.segment}%"))

        if params.minimum_seating_capacity:
            stmt = stmt.where(Variant.seating_capacity >= params.minimum_seating_capacity)
            count_stmt = count_stmt.where(
                Variant.seating_capacity >= params.minimum_seating_capacity
            )

        if params.minimum_price is not None:
            stmt = stmt.where(VehiclePrice.ex_showroom_price >= params.minimum_price)
            count_stmt = count_stmt.where(VehiclePrice.ex_showroom_price >= params.minimum_price)

        if params.maximum_price is not None:
            stmt = stmt.where(VehiclePrice.ex_showroom_price <= params.maximum_price)
            count_stmt = count_stmt.where(VehiclePrice.ex_showroom_price <= params.maximum_price)

        if params.search:
            s_term = f"%{params.search}%"
            s_filter = or_(
                Variant.name.ilike(s_term),
                Variant.slug.ilike(s_term),
                CarModel.name.ilike(s_term),
                CarModel.slug.ilike(s_term),
                Manufacturer.name.ilike(s_term),
            )
            stmt = stmt.where(s_filter)
            count_stmt = count_stmt.where(s_filter)

        # Count total
        total_res = await self.session.execute(count_stmt)
        total = total_res.scalar_one()

        # Paginate
        page = max(1, params.page)
        page_size = min(100, max(1, params.page_size))
        stmt = (
            stmt.order_by(CarModel.name, Variant.name)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )

        rows = await self.session.execute(stmt)
        items: List[VehicleSearchResultItem] = []

        for variant, model, mfg, price in rows:
            ex_price = price.ex_showroom_price if price else None
            p_type = price.price_type if price else None
            p_from = price.effective_from if price else None
            image_url = model.image_url

            items.append(
                VehicleSearchResultItem(
                    variant_id=variant.id,
                    variant_name=variant.name,
                    variant_slug=variant.slug,
                    trim_level=variant.trim_level,
                    model_id=model.id,
                    model_name=model.name,
                    model_slug=model.slug,
                    body_type=model.body_type,
                    segment=model.segment,
                    manufacturer_id=mfg.id,
                    manufacturer_name=mfg.name,
                    manufacturer_slug=mfg.slug,
                    country=mfg.country,
                    fuel_type=variant.fuel_type,
                    transmission=variant.transmission,
                    drivetrain=variant.drivetrain or "FWD",
                    seating_capacity=variant.seating_capacity,
                    engine_cc=variant.engine_cc,
                    engine_power_bhp=variant.engine_power_bhp,
                    torque_nm=variant.torque_nm,
                    mileage_claimed=variant.mileage_claimed,
                    battery_capacity_kwh=variant.battery_capacity_kwh,
                    range_km=variant.range_km,
                    active=variant.active,
                    current_ex_showroom_price=ex_price,
                    price_type=p_type,
                    price_effective_from=p_from,
                    image_url=image_url,
                )
            )

        return items, total
