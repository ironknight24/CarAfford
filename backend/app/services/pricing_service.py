from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundException
from app.repositories.pricing_repo import PricingRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.pricing import (
    OnRoadPriceBreakdown,
    OnRoadPriceCalculationRequest,
    OnRoadPriceRequest,
    OnRoadPriceResponse,
)
from app.services.on_road_price_service import OnRoadPriceCalculationService


class PricingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.vehicle_repo = VehicleRepository(session)
        self.pricing_repo = PricingRepository(session)

    async def calculate_on_road_price(
        self,
        request: OnRoadPriceRequest,
    ) -> OnRoadPriceBreakdown:
        calc_req = OnRoadPriceCalculationRequest(
            variant_id=request.variant_id,
            state_id=request.state_id,
            city_id=request.city_id,
            is_bh_series=request.is_bh_series,
            is_financed=request.is_financed,
            insurance_option=(
                "ZERO_DEP" if request.include_zero_dep_insurance else "DEFAULT_ESTIMATE"
            ),
        )
        res: OnRoadPriceResponse = await OnRoadPriceCalculationService.calculate_on_road_price(
            db=self.session,
            request=calc_req,
        )

        # Extract breakdown components for backward compatibility
        rto_tax = Decimal("0.00")
        rto_tax_pct = Decimal("0.00")
        rto_cess = Decimal("0.00")
        reg_charges = Decimal("0.00")
        fastag = Decimal("0.00")
        green_cess = Decimal("0.00")
        hypo = Decimal("0.00")
        tcs = Decimal("0.00")
        ins_total = res.totals.total_insurance

        for item in res.breakdown:
            if item.component in ["ROAD_TAX", "MOTOR_VEHICLE_TAX"]:
                rto_tax += item.calculated_amount
                if item.rate:
                    rto_tax_pct = item.rate
            elif item.component in ["CESS", "SURCHARGE"]:
                rto_cess += item.calculated_amount
            elif item.component in ["REGISTRATION_FEE", "SMART_CARD_FEE", "HSRP_FEE"]:
                reg_charges += item.calculated_amount
            elif item.component == "FASTAG_FEE":
                fastag += item.calculated_amount
            elif item.component == "GREEN_TAX":
                green_cess += item.calculated_amount
            elif item.component == "HYPOTHECATION_FEE":
                hypo += item.calculated_amount
            elif item.component == "TCS":
                tcs += item.calculated_amount

        return OnRoadPriceBreakdown(
            variant_id=res.vehicle.variant_id,
            variant_name=res.vehicle.variant_name,
            model_name=res.vehicle.model_name or "",
            manufacturer_name=res.vehicle.manufacturer_name or "",
            state_id=res.location.state_id,
            state_name=res.location.state_name,
            city_name=res.location.city_name,
            ex_showroom_price=res.totals.ex_showroom_price,
            rto_road_tax=rto_tax,
            rto_road_tax_percent=rto_tax_pct,
            rto_cess=rto_cess,
            registration_charges=reg_charges,
            fastag_charges=fastag,
            green_cess=green_cess,
            hypothecation_charges=hypo,
            tcs_amount=tcs,
            insurance_estimated_idv=res.totals.ex_showroom_price * Decimal("0.95"),
            insurance_third_party_3yr=Decimal("0.00"),
            insurance_own_damage_1yr=Decimal("0.00"),
            insurance_zero_dep_addon=Decimal("0.00"),
            insurance_total=ins_total,
            on_road_price=res.totals.on_road_price,
            is_bh_series=res.is_bh_series,
            calculated_at=res.calculation_date.isoformat(),
        )
