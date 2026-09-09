from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundException
from app.models.location import State
from app.models.vehicle import Variant
from app.repositories.location_repo import LocationRepository
from app.repositories.pricing_repo import PricingRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.pricing import OnRoadPriceBreakdown, OnRoadPriceRequest
from app.services.insurance_service import InsuranceService
from app.services.tax_calculator import TaxCalculator


class PricingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.vehicle_repo = VehicleRepository(session)
        self.location_repo = LocationRepository(session)
        self.pricing_repo = PricingRepository(session)

    async def calculate_on_road_price(
        self,
        request: OnRoadPriceRequest,
    ) -> OnRoadPriceBreakdown:
        variant = await self.vehicle_repo.get_variant_by_id(request.variant_id)
        if not variant:
            raise ResourceNotFoundException(f"Vehicle variant with ID {request.variant_id} not found.")

        state = await self.location_repo.get_state_by_id(request.state_id)
        if not state:
            raise ResourceNotFoundException(f"State with ID {request.state_id} not found.")

        city_name: Optional[str] = None
        if request.city_id:
            city = await self.location_repo.get_city_by_id(request.city_id)
            city_name = city.name if city else None

        # 1. Fetch currently effective ex-showroom price
        ex_showroom_price: Optional[Decimal] = None
        current_vehicle_price = await self.vehicle_repo.get_current_price(variant.id)
        if current_vehicle_price:
            ex_showroom_price = current_vehicle_price.ex_showroom_price
        else:
            # Fallback to pricing repo
            ex_price_record = await self.pricing_repo.get_ex_showroom_price(
                variant_id=variant.id,
                state_id=state.id,
                city_id=request.city_id,
            )
            if ex_price_record:
                ex_showroom_price = ex_price_record.price_inr

        if ex_showroom_price is None:
            raise ResourceNotFoundException(f"No active ex-showroom price found for variant {variant.name}.")

        # 2. Fetch tax slab and calculate RTO taxes
        tax_slab = await self.location_repo.get_tax_slab_for_vehicle(
            state_id=state.id,
            fuel_type=variant.fuel_type,
            ex_showroom_price=ex_showroom_price,
            is_bh_series=request.is_bh_series,
        )

        tax_res = TaxCalculator.calculate_state_rto_tax(
            ex_showroom_price=ex_showroom_price,
            tax_slab=tax_slab,
            fuel_type=variant.fuel_type,
            is_bh_series=request.is_bh_series,
            is_financed=request.is_financed,
        )

        # 3. Calculate Insurance
        engine_cc = variant.engine_cc or (variant.specification.engine_displacement_cc if variant.specification else 1199)
        is_ev = "ELECTRIC" in variant.fuel_type.upper() or "EV" in variant.fuel_type.upper()
        ins_res = InsuranceService.estimate_insurance(
            ex_showroom_price=ex_showroom_price,
            engine_cc=engine_cc,
            is_ev=is_ev,
            include_zero_dep=request.include_zero_dep_insurance,
        )

        # 4. Total On-Road Price
        on_road_total = (
            ex_showroom_price
            + tax_res.total_rto_and_govt_charges
            + ins_res.total_insurance_premium
        )

        return OnRoadPriceBreakdown(
            variant_id=variant.id,
            variant_name=variant.name,
            model_name=variant.model.name,
            manufacturer_name=variant.model.manufacturer.name,
            state_id=state.id,
            state_name=state.name,
            city_name=city_name,
            ex_showroom_price=ex_showroom_price,
            rto_road_tax=tax_res.rto_tax,
            rto_road_tax_percent=tax_res.tax_percent,
            rto_cess=tax_res.cess_amount,
            registration_charges=tax_res.registration_fee,
            fastag_charges=tax_res.fastag_fee,
            green_cess=tax_res.green_cess,
            hypothecation_charges=tax_res.hypothecation_fee,
            tcs_amount=tax_res.tcs_amount,
            insurance_estimated_idv=ins_res.estimated_idv,
            insurance_third_party_3yr=ins_res.third_party_3yr,
            insurance_own_damage_1yr=ins_res.own_damage_1yr,
            insurance_zero_dep_addon=ins_res.zero_dep_addon,
            insurance_total=ins_res.total_insurance_premium,
            on_road_price=on_road_total,
            is_bh_series=request.is_bh_series,
            calculated_at=datetime.now(timezone.utc).isoformat(),
        )
