from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidFinancialInputException, ResourceNotFoundException
from app.core.tco_constants import (
    DATA_STATUS_DEMO,
    DEFAULT_DEPRECIATION,
    DEFAULT_FUEL_PRICES,
    DEFAULT_INSURANCE_RENEWAL,
    DEFAULT_MAINTENANCE_RATES,
    TCO_DISCLAIMER,
    TCO_PERIODS_CONFIG,
    DepreciationConfig,
    FuelPriceConfig,
    InsuranceRenewalConfig,
    MaintenanceConfig,
)
from app.models.location import City, RtoOffice, State
from app.models.vehicle import CarModel, Manufacturer, Variant
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.finance import FinanceCalculationRequest
from app.schemas.pricing import OnRoadPriceCalculationRequest
from app.schemas.tco import (
    DepreciationAssumption,
    FuelPriceAssumption,
    InsuranceAssumption,
    MaintenanceAssumption,
    TCOAssumptionsResponse,
    TCOCalculationRequest,
    TCOCalculationResponse,
    TCOComparisonItem,
    TCOComparisonRequest,
    TCOComparisonResponse,
    TCODrivingProfile,
    TCOFinancingBreakdown,
    TCOInitialCostBreakdown,
    TCOOperatingCostsSummary,
    TCOPeriodBreakdown,
    TCOVehicleRequest,
)
from app.services.finance_service import FinanceService
from app.services.financing_engine_service import FinancingEngineService
from app.services.loan_rate_resolver import LoanRateResolverService
from app.services.on_road_price_service import OnRoadPriceCalculationService


def round_inr(amount: Decimal) -> Decimal:
    """Rounds currency amounts to 2 decimal places using standard ROUND_HALF_UP."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class TCOService:
    """Pure domain calculation engine for Vehicle Total Cost of Ownership (TCO).
    
    Orchestrates:
    - OnRoadPriceCalculationService for location-specific vehicle acquisition cost & statutory taxes.
    - FinancingEngineService / FinanceService for loan interest, processing fees, and amortization.
    - Fuel & Energy Calculation engine for ICE (km/l), EV (km/kWh), CNG, and Hybrid models.
    - Motor Insurance Renewal models avoiding initial 1st-year on-road double counting.
    - Routine & Periodic Maintenance cost projections.
    - Multi-term (1-Year, 3-Year, 5-Year) Cash Outflows vs. Economic Ownership Costs.
    """

    @classmethod
    async def validate_location_hierarchy(
        cls,
        db: AsyncSession,
        state_id: int,
        city_id: Optional[int] = None,
        rto_id: Optional[int] = None,
    ) -> Tuple[State, Optional[City], Optional[RtoOffice]]:
        """Validates that state exists and city/rto belong to the state hierarchy."""
        state = await db.get(State, state_id)
        if not state:
            raise ResourceNotFoundException(f"State with ID {state_id} not found.")

        city: Optional[City] = None
        if city_id is not None:
            city = await db.get(City, city_id)
            if not city:
                raise ResourceNotFoundException(f"City with ID {city_id} not found.")
            if city.state_id != state.id:
                raise InvalidFinancialInputException(
                    f"City '{city.name}' (id={city.id}) does not belong to State '{state.name}' (id={state.id})."
                )

        rto: Optional[RtoOffice] = None
        if rto_id is not None:
            rto = await db.get(RtoOffice, rto_id)
            if not rto:
                raise ResourceNotFoundException(f"RTO with ID {rto_id} not found.")
            if rto.state_id != state.id:
                raise InvalidFinancialInputException(
                    f"RTO '{rto.code}' (id={rto.id}) does not belong to State '{state.name}' (id={state.id})."
                )

        return state, city, rto

    @classmethod
    def get_assumptions(cls) -> TCOAssumptionsResponse:
        """Returns active baseline TCO assumptions and their data provenance."""
        fuel_assumptions = {
            k: FuelPriceAssumption(
                fuel_type=v.fuel_type,
                price_per_unit=v.price_per_unit,
                unit=v.unit,
                currency=v.currency,
                effective_from=v.effective_from,
                source=v.source,
                data_status=v.data_status,
            )
            for k, v in DEFAULT_FUEL_PRICES.items()
        }

        maint_assumptions = {
            k: MaintenanceAssumption(
                fuel_type=v.fuel_type,
                annual_base_cost=v.annual_base_cost,
                cost_per_km=v.cost_per_km,
                service_interval_km=v.service_interval_km,
                service_interval_months=v.service_interval_months,
                source=v.source,
                data_status=v.data_status,
            )
            for k, v in DEFAULT_MAINTENANCE_RATES.items()
        }

        ins_assumption = InsuranceAssumption(
            year_2_factor=DEFAULT_INSURANCE_RENEWAL.year_2_factor,
            year_3_factor=DEFAULT_INSURANCE_RENEWAL.year_3_factor,
            year_4_factor=DEFAULT_INSURANCE_RENEWAL.year_4_factor,
            year_5_factor=DEFAULT_INSURANCE_RENEWAL.year_5_factor,
            source=DEFAULT_INSURANCE_RENEWAL.source,
            data_status=DEFAULT_INSURANCE_RENEWAL.data_status,
        )

        dep_assumption = DepreciationAssumption(
            year_1_depreciation_pct=DEFAULT_DEPRECIATION.year_1_depreciation_pct,
            year_2_depreciation_pct=DEFAULT_DEPRECIATION.year_2_depreciation_pct,
            year_3_depreciation_pct=DEFAULT_DEPRECIATION.year_3_depreciation_pct,
            year_4_depreciation_pct=DEFAULT_DEPRECIATION.year_4_depreciation_pct,
            year_5_depreciation_pct=DEFAULT_DEPRECIATION.year_5_depreciation_pct,
            source=DEFAULT_DEPRECIATION.source,
            data_status=DEFAULT_DEPRECIATION.data_status,
        )

        return TCOAssumptionsResponse(
            fuel_prices=fuel_assumptions,
            maintenance_rates=maint_assumptions,
            insurance_renewal=ins_assumption,
            depreciation=dep_assumption,
            data_status=DATA_STATUS_DEMO,
            disclaimer=TCO_DISCLAIMER,
        )

    # =========================================================================
    # CORE SUB-CALCULATION ENGINES
    # =========================================================================

    @classmethod
    def calculate_annual_fuel_cost(
        cls,
        fuel_type: str,
        efficiency: Decimal,
        annual_distance_km: Decimal,
        custom_fuel_price: Optional[Decimal] = None,
    ) -> Tuple[Decimal, Decimal, str, str]:
        """Calculates annual fuel or electricity expenditure in INR.
        
        Returns:
            (annual_fuel_cost, price_per_unit, fuel_unit, efficiency_unit)
        """
        norm_fuel = fuel_type.upper()
        if norm_fuel in ["EV", "ELECTRIC"]:
            norm_fuel = "ELECTRIC"
            eff_unit = "km/kWh"
        elif norm_fuel == "CNG":
            eff_unit = "km/kg"
        else:
            eff_unit = "km/l"

        fuel_config = DEFAULT_FUEL_PRICES.get(norm_fuel, DEFAULT_FUEL_PRICES["PETROL"])
        price_per_unit = custom_fuel_price if custom_fuel_price is not None and custom_fuel_price > 0 else fuel_config.price_per_unit
        fuel_unit = fuel_config.unit

        if efficiency <= 0 or annual_distance_km <= 0:
            return Decimal("0.00"), price_per_unit, fuel_unit, eff_unit

        # Units required = annual_distance / efficiency
        units_needed = annual_distance_km / efficiency
        annual_cost = units_needed * price_per_unit

        return round_inr(annual_cost), price_per_unit, fuel_unit, eff_unit

    @classmethod
    def calculate_annual_maintenance_cost(
        cls,
        fuel_type: str,
        annual_distance_km: Decimal,
    ) -> Decimal:
        """Calculates annual routine maintenance + per-km consumable wear cost in INR."""
        norm_fuel = fuel_type.upper()
        if norm_fuel in ["EV", "ELECTRIC"]:
            norm_fuel = "ELECTRIC"

        maint_config = DEFAULT_MAINTENANCE_RATES.get(norm_fuel, DEFAULT_MAINTENANCE_RATES["PETROL"])
        annual_cost = maint_config.annual_base_cost + (annual_distance_km * maint_config.cost_per_km)
        return round_inr(annual_cost)

    @classmethod
    def calculate_annual_insurance_renewal(
        cls,
        first_year_insurance: Decimal,
        year_index: int,
    ) -> Decimal:
        """Calculates renewal premium for a given ownership year (Year 2 to 5).
        
        Year 1 is covered in on-road price.
        """
        if year_index == 2:
            rate = DEFAULT_INSURANCE_RENEWAL.year_2_factor
        elif year_index == 3:
            rate = DEFAULT_INSURANCE_RENEWAL.year_3_factor
        elif year_index == 4:
            rate = DEFAULT_INSURANCE_RENEWAL.year_4_factor
        else:
            rate = DEFAULT_INSURANCE_RENEWAL.year_5_factor

        return round_inr(first_year_insurance * rate)

    @classmethod
    def calculate_depreciation_and_resale(
        cls,
        ex_showroom_price: Decimal,
        years: int,
    ) -> Tuple[Decimal, Decimal]:
        """Calculates cumulative depreciation and estimated resale value."""
        if years <= 1:
            pct = DEFAULT_DEPRECIATION.year_1_depreciation_pct
        elif years <= 2:
            pct = DEFAULT_DEPRECIATION.year_2_depreciation_pct
        elif years <= 3:
            pct = DEFAULT_DEPRECIATION.year_3_depreciation_pct
        elif years <= 4:
            pct = DEFAULT_DEPRECIATION.year_4_depreciation_pct
        else:
            pct = DEFAULT_DEPRECIATION.year_5_depreciation_pct

        dep_amount = round_inr(ex_showroom_price * (pct / Decimal("100.0")))
        resale_value = round_inr(ex_showroom_price - dep_amount)
        return dep_amount, resale_value

    # =========================================================================
    # PERIOD SIZING AND RECONCILIATION
    # =========================================================================

    @classmethod
    def build_period_breakdown(
        cls,
        period_key: str,
        years: int,
        months: int,
        label: str,
        annual_fuel_cost: Decimal,
        first_year_insurance: Decimal,
        annual_maintenance_cost: Decimal,
        down_payment: Decimal,
        amortization_schedule: List[Any],
        loan_tenure_months: int,
        loan_processing_fees: Decimal,
        ex_showroom_price: Decimal,
        is_financed: bool,
    ) -> TCOPeriodBreakdown:
        """Computes accurate period costs honoring loan tenure truncation & zero double counting."""
        # 1. Operating costs for period
        fuel_cost = round_inr(annual_fuel_cost * Decimal(str(years)))
        maint_cost = round_inr(annual_maintenance_cost * Decimal(str(years)))

        # Insurance renewals: Year 1 is in on-road price; renewal premiums apply for years 2..N
        insurance_renewals = Decimal("0.00")
        for y in range(2, years + 1):
            insurance_renewals += cls.calculate_annual_insurance_renewal(first_year_insurance, y)
        insurance_renewals = round_inr(insurance_renewals)

        total_operating = fuel_cost + insurance_renewals + maint_cost

        # 2. Financing costs for period
        # If loan tenure (e.g. 36 mo) < period months (e.g. 60 mo), repayments stop at month 36!
        principal_paid = Decimal("0.00")
        interest_paid = Decimal("0.00")
        repayment_paid = Decimal("0.00")

        if is_financed and amortization_schedule:
            for item in amortization_schedule:
                if item.month <= months:
                    principal_paid += item.principal_component
                    interest_paid += item.interest_component
                    repayment_paid += item.emi

        principal_paid = round_inr(principal_paid)
        interest_paid = round_inr(interest_paid)
        repayment_paid = round_inr(repayment_paid)
        fees_paid = loan_processing_fees if is_financed else Decimal("0.00")

        # 3. Total Cash Outflow:
        # Down Payment + Total Repayments in period + Financing Fees + Operating Costs in period
        total_cash_outflow = round_inr(down_payment + repayment_paid + fees_paid + total_operating)

        # 4. Depreciation and Economic Cost:
        depreciation_amount, resale_value = cls.calculate_depreciation_and_resale(ex_showroom_price, years)
        economic_cost = round_inr(total_cash_outflow - resale_value)

        # 5. Averages:
        avg_monthly = round_inr(total_cash_outflow / Decimal(str(months)))
        avg_monthly_operating = round_inr(total_operating / Decimal(str(months)))
        avg_annual = round_inr(total_cash_outflow / Decimal(str(years)))

        return TCOPeriodBreakdown(
            period_years=years,
            period_months=months,
            label=label,
            fuel_cost=fuel_cost,
            insurance_cost=insurance_renewals,
            maintenance_cost=maint_cost,
            total_operating_cost=total_operating,
            financing_interest=interest_paid,
            financing_fees=fees_paid,
            loan_principal_paid=principal_paid,
            total_loan_repayment_paid=repayment_paid,
            initial_down_payment=down_payment,
            total_cash_outflow=total_cash_outflow,
            estimated_depreciation=depreciation_amount,
            estimated_resale_value=resale_value,
            estimated_economic_cost=economic_cost,
            average_monthly_cost=avg_monthly,
            average_monthly_operating_cost=avg_monthly_operating,
            average_annual_cost=avg_annual,
        )

    # =========================================================================
    # PRIMARY CALCULATION ENTRY POINTS
    # =========================================================================

    @classmethod
    async def calculate_tco(
        cls,
        db: AsyncSession,
        request: TCOCalculationRequest,
    ) -> TCOCalculationResponse:
        """Executes full TCO calculation for a vehicle variant or generic profile."""
        calc_date = request.calculation_date or datetime.now(timezone.utc)
        if calc_date.tzinfo is None:
            calc_date = calc_date.replace(tzinfo=timezone.utc)

        # 1. Location validation
        state, city, rto = await cls.validate_location_hierarchy(
            db, request.state_id, request.city_id, request.rto_id
        )

        # 2. Vehicle resolution & On-Road Price lookup
        variant: Optional[Variant] = None
        ex_showroom_price = request.custom_ex_showroom_price or Decimal("1000000.00")
        total_on_road_price = request.custom_on_road_price or Decimal("1150000.00")
        first_year_insurance = Decimal("35000.00")
        fuel_type = request.fuel_type or "Petrol"
        efficiency = request.mileage_kmpl or Decimal("18.00")
        eff_source = "USER_PROVIDED" if request.mileage_kmpl else "DEFAULT_ASSUMPTION"
        vehicle_meta: Optional[Dict[str, Any]] = None

        if request.variant_id is not None:
            vehicle_repo = VehicleRepository(db)
            variant = await vehicle_repo.get_variant_by_id(request.variant_id)
            if not variant:
                raise ResourceNotFoundException(f"Vehicle variant with ID {request.variant_id} not found.")

            # Authoritative On-Road Price from OnRoadPriceCalculationService
            pricing_req = OnRoadPriceCalculationRequest(
                variant_id=variant.id,
                state_id=state.id,
                city_id=city.id if city else None,
                rto_id=rto.id if rto else None,
                calculation_date=calc_date,
                insurance_option="ZERO_DEP",
                is_bh_series=False,
                is_financed=request.is_financed,
            )
            pricing_res = await OnRoadPriceCalculationService.calculate_on_road_price(db, pricing_req)
            total_on_road_price = pricing_res.totals.on_road_price
            ex_showroom_price = pricing_res.totals.ex_showroom_price
            first_year_insurance = pricing_res.totals.total_insurance
            fuel_type = variant.fuel_type

            # Resolve efficiency
            is_ev = variant.fuel_type.upper() in ["ELECTRIC", "EV"]
            if request.mileage_kmpl is not None:
                efficiency = request.mileage_kmpl
                eff_source = "USER_OVERRIDE"
            elif is_ev:
                if variant.range_km and variant.battery_capacity_kwh and variant.battery_capacity_kwh > 0:
                    efficiency = round_inr(variant.range_km / variant.battery_capacity_kwh)
                    eff_source = "OEM_CLAIMED_RANGE"
                else:
                    efficiency = Decimal("7.00")  # ~7 km/kWh standard EV efficiency
                    eff_source = "BENCHMARK_ESTIMATE"
            else:
                efficiency = variant.arai_mileage_kmpl
                eff_source = "ARAI_CLAIMED"

            vehicle_meta = {
                "variant_id": variant.id,
                "variant_name": variant.name,
                "model_name": variant.model.name if variant.model else None,
                "manufacturer_name": variant.model.manufacturer.name if variant.model and variant.model.manufacturer else None,
                "fuel_type": variant.fuel_type,
                "transmission": variant.transmission,
                "seating_capacity": variant.seating_capacity,
                "is_ev": is_ev,
            }

        # 3. Down payment and Loan sizing
        # Default down payment to 20% if not specified
        down_payment = (
            request.down_payment
            if request.down_payment is not None
            else round_inr(total_on_road_price * Decimal("0.20"))
        )
        down_payment = min(down_payment, total_on_road_price)
        loan_principal = max(Decimal("0.00"), total_on_road_price - down_payment)

        # 4. Financing Resolution
        financing_breakdown: Optional[TCOFinancingBreakdown] = None
        amort_schedule: List[Any] = []
        interest_rate = Decimal("8.75")
        tenure_months = request.preferred_loan_tenure_months or 60
        monthly_emi = Decimal("0.00")
        total_interest = Decimal("0.00")
        processing_fees = Decimal("0.00")
        total_repayment = Decimal("0.00")

        if request.is_financed and loan_principal > 0:
            # Resolve best bank financing product
            try:
                eligible_offers = await FinancingEngineService.compare_financing_options(
                    db=db,
                    on_road_price=total_on_road_price,
                    down_payment=down_payment,
                    tenure_months=tenure_months,
                    credit_score=request.credit_score or 750,
                    calculation_date=calc_date,
                    variant_id=request.variant_id,
                    state_id=state.id,
                )
                if eligible_offers and len(eligible_offers) > 0:
                    best_offer = eligible_offers[0]
                    interest_rate = best_offer.annual_interest_rate
                    monthly_emi = best_offer.monthly_emi
                    total_interest = best_offer.total_interest
                    total_repayment = best_offer.total_repayment
                    processing_fees = best_offer.total_fees
                    bank_name = best_offer.bank_name
                    product_name = best_offer.product_name
                    bank_id = best_offer.bank_id
                else:
                    interest_rate = FinanceService.resolve_interest_rate_by_cibil(request.credit_score or 750)
                    monthly_emi = FinanceService.calculate_emi(loan_principal, interest_rate, tenure_months)
                    total_repayment = round_inr(monthly_emi * Decimal(str(tenure_months)))
                    total_interest = round_inr(total_repayment - loan_principal)
                    processing_fees = round_inr(min(Decimal("10000.00"), loan_principal * Decimal("0.005")))
                    bank_name = "Retail Auto Finance Benchmark"
                    product_name = "Prime Auto Loan"
                    bank_id = None
            except Exception:
                interest_rate = FinanceService.resolve_interest_rate_by_cibil(request.credit_score or 750)
                monthly_emi = FinanceService.calculate_emi(loan_principal, interest_rate, tenure_months)
                total_repayment = round_inr(monthly_emi * Decimal(str(tenure_months)))
                total_interest = round_inr(total_repayment - loan_principal)
                processing_fees = round_inr(min(Decimal("10000.00"), loan_principal * Decimal("0.005")))
                bank_name = "Retail Auto Finance Benchmark"
                product_name = "Prime Auto Loan"
                bank_id = None

            amort_schedule = FinanceService.calculate_amortization_schedule(
                principal=loan_principal,
                annual_interest_rate=interest_rate,
                tenure_months=tenure_months,
            )

            financing_breakdown = TCOFinancingBreakdown(
                bank_id=bank_id,
                bank_name=bank_name,
                loan_product_name=product_name,
                annual_interest_rate=interest_rate,
                tenure_months=tenure_months,
                monthly_emi=monthly_emi,
                total_interest=total_interest,
                processing_fees=processing_fees,
                total_repayment=total_repayment,
            )
        else:
            # 100% Cash / unfinanced
            down_payment = total_on_road_price
            loan_principal = Decimal("0.00")

        # 5. Operating Costs Calculation (Annual Base)
        annual_dist = request.annual_driving_distance_km or Decimal("12000.00")
        monthly_dist = request.monthly_driving_distance_km or Decimal("1000.00")

        annual_fuel, fuel_price_per_unit, fuel_unit, eff_unit = cls.calculate_annual_fuel_cost(
            fuel_type=fuel_type,
            efficiency=efficiency,
            annual_distance_km=annual_dist,
            custom_fuel_price=request.custom_fuel_price,
        )
        annual_maint = cls.calculate_annual_maintenance_cost(fuel_type, annual_dist)
        annual_ins_renewal = cls.calculate_annual_insurance_renewal(first_year_insurance, 2)
        annual_total_op = round_inr(annual_fuel + annual_maint + annual_ins_renewal)

        op_summary = TCOOperatingCostsSummary(
            annual_fuel_cost=annual_fuel,
            annual_insurance_cost=annual_ins_renewal,
            annual_maintenance_cost=annual_maint,
            annual_total_operating_cost=annual_total_op,
        )

        driving_profile = TCODrivingProfile(
            annual_distance_km=annual_dist,
            monthly_distance_km=monthly_dist,
            fuel_type=fuel_type,
            fuel_efficiency=efficiency,
            efficiency_unit=eff_unit,
            fuel_price_per_unit=fuel_price_per_unit,
            fuel_price_unit=fuel_unit,
            efficiency_source=eff_source,
        )

        initial_cost = TCOInitialCostBreakdown(
            ex_showroom_price=ex_showroom_price,
            total_on_road_price=total_on_road_price,
            down_payment=down_payment,
            loan_principal=loan_principal,
        )

        # 6. Multi-term Period Breakdown (1-Year, 3-Years, 5-Years)
        periods: Dict[str, TCOPeriodBreakdown] = {}
        for period_key, period_info in TCO_PERIODS_CONFIG.items():
            pb = cls.build_period_breakdown(
                period_key=period_key,
                years=period_info["years"],
                months=period_info["months"],
                label=period_info["label"],
                annual_fuel_cost=annual_fuel,
                first_year_insurance=first_year_insurance,
                annual_maintenance_cost=annual_maint,
                down_payment=down_payment,
                amortization_schedule=amort_schedule,
                loan_tenure_months=tenure_months,
                loan_processing_fees=processing_fees,
                ex_showroom_price=ex_showroom_price,
                is_financed=request.is_financed and loan_principal > 0,
            )
            periods[period_key] = pb

        location_meta = {
            "state_id": state.id,
            "state_name": state.name,
            "state_code": state.code,
            "city_id": city.id if city else None,
            "city_name": city.name if city else None,
            "rto_id": rto.id if rto else None,
            "rto_code": rto.code if rto else None,
        }

        return TCOCalculationResponse(
            vehicle=vehicle_meta,
            location=location_meta,
            driving_profile=driving_profile,
            initial_cost=initial_cost,
            financing=financing_breakdown,
            operating_costs=op_summary,
            periods=periods,
            data_status=DATA_STATUS_DEMO,
            disclaimer=TCO_DISCLAIMER,
        )

    @classmethod
    async def calculate_vehicle_tco(
        cls,
        db: AsyncSession,
        request: TCOVehicleRequest,
    ) -> TCOCalculationResponse:
        """Alias helper executing variant-specific TCO evaluation."""
        return await cls.calculate_tco(db, request)

    @classmethod
    async def compare_vehicles_tco(
        cls,
        db: AsyncSession,
        request: TCOComparisonRequest,
    ) -> TCOComparisonResponse:
        """Compares TCO for multiple vehicle variants side-by-side."""
        calc_date = datetime.now(timezone.utc)
        state, city, rto = await cls.validate_location_hierarchy(
            db, request.state_id, request.city_id, request.rto_id
        )

        compared_items: List[TCOComparisonItem] = []

        for vid in request.variant_ids:
            single_req = TCOCalculationRequest(
                variant_id=vid,
                state_id=request.state_id,
                city_id=request.city_id,
                rto_id=request.rto_id,
                monthly_driving_distance_km=request.monthly_driving_distance_km,
                annual_driving_distance_km=request.annual_driving_distance_km,
                down_payment=request.down_payment,
                credit_score=request.credit_score,
                preferred_loan_tenure_months=request.preferred_loan_tenure_months,
                is_financed=request.is_financed,
                calculation_date=calc_date,
            )
            try:
                res = await cls.calculate_tco(db, single_req)
                v_meta = res.vehicle or {}
                five_yr = res.periods.get("5_years")
                three_yr = res.periods.get("3_years")
                one_yr = res.periods.get("1_year")

                item = TCOComparisonItem(
                    variant_id=vid,
                    variant_name=v_meta.get("variant_name", f"Variant {vid}"),
                    model_name=v_meta.get("model_name", "Unknown Model"),
                    manufacturer_name=v_meta.get("manufacturer_name", "Unknown Make"),
                    fuel_type=v_meta.get("fuel_type", "Petrol"),
                    ex_showroom_price=res.initial_cost.ex_showroom_price,
                    on_road_price=res.initial_cost.total_on_road_price,
                    monthly_emi=res.financing.monthly_emi if res.financing else Decimal("0.00"),
                    annual_fuel_cost=res.operating_costs.annual_fuel_cost,
                    annual_operating_cost=res.operating_costs.annual_total_operating_cost,
                    one_year_tco=one_yr.total_cash_outflow if one_yr else Decimal("0.00"),
                    three_year_tco=three_yr.total_cash_outflow if three_yr else Decimal("0.00"),
                    five_year_tco=five_yr.total_cash_outflow if five_yr else Decimal("0.00"),
                    five_year_monthly_average=five_yr.average_monthly_cost if five_yr else Decimal("0.00"),
                    five_year_economic_cost=five_yr.estimated_economic_cost if five_yr else Decimal("0.00"),
                )
                compared_items.append(item)
            except Exception as e:
                continue

        # Sort by 5-year TCO ascending (most cost-effective first)
        compared_items.sort(key=lambda x: x.five_year_tco)

        location_meta = {
            "state_id": state.id,
            "state_name": state.name,
            "state_code": state.code,
            "city_id": city.id if city else None,
            "city_name": city.name if city else None,
        }

        driving_profile = {
            "annual_distance_km": request.annual_driving_distance_km or Decimal("12000.00"),
            "monthly_distance_km": request.monthly_driving_distance_km or Decimal("1000.00"),
        }

        return TCOComparisonResponse(
            driving_profile=driving_profile,
            location=location_meta,
            compared_vehicles=compared_items,
            data_status=DATA_STATUS_DEMO,
            disclaimer=TCO_DISCLAIMER,
        )
