from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.affordability_constants import (
    AFFORDABILITY_PROFILES,
    HEADROOM_COMFORTABLE_THRESHOLD,
    AffordabilityProfile,
    AffordabilityStatus,
    DATA_STATUS_DEMO,
    DISCLAIMER_TEXT,
    LimitingFactor,
)
from app.core.exceptions import InvalidFinancialInputException, ResourceNotFoundException
from app.models.location import City, RtoOffice, State
from app.models.vehicle import Variant
from app.repositories.finance_repo import FinanceRepository
from app.repositories.location_repo import LocationRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.affordability import (
    AffordabilityBudgetBreakdown,
    AffordabilityCalculateRequest,
    AffordabilityComparisonRequest,
    AffordabilityComparisonResponse,
    AffordabilityFinancingAssumption,
    AffordabilityProfileInfo,
    MultiVehicleAffordabilityRequest,
    MultiVehicleAffordabilityResponse,
    VehicleAffordabilityRequest,
    VehicleAffordabilityResponse,
)
from app.schemas.finance import BankComparisonRequest, LoanOfferItem
from app.schemas.pricing import OnRoadPriceCalculationRequest
from app.services.finance_service import FinanceService
from app.services.financing_engine_service import FinancingEngineService
from app.services.loan_rate_resolver import LoanRateResolverService
from app.services.on_road_price_service import OnRoadPriceCalculationService


def round_inr(amount: Decimal) -> Decimal:
    """Rounds monetary currency amounts strictly to 2 decimal places using standard ROUND_HALF_UP."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class AffordabilityService:
    """Core domain orchestrator for Indian vehicle affordability intelligence.

    Architectural Responsibilities:
    - Orchestrates User Financial Profile against the On-Road Price Engine and Finance Engine.
    - Pure Decimal arithmetic (zero floating-point precision error).
    - Enforces transparent risk profiles (CONSERVATIVE, BALANCED, STRETCH).
    - Reuses existing FinanceService, LoanRateResolverService, and OnRoadPriceCalculationService.
    - Clearly distinguishes application heuristics from official bank credit decisions.
    """

    @classmethod
    async def validate_location_hierarchy(
        cls,
        db: AsyncSession,
        state_id: int,
        city_id: Optional[int] = None,
        rto_id: Optional[int] = None,
    ) -> Tuple[State, Optional[City], Optional[RtoOffice]]:
        """Validates State -> City -> RTO hierarchy against active database records."""
        loc_repo = LocationRepository(db)
        state = await loc_repo.get_state_by_id(state_id)
        if not state:
            raise ResourceNotFoundException(f"State with ID {state_id} not found.")

        city: Optional[City] = None
        if city_id is not None:
            city = await loc_repo.get_city_by_id(city_id)
            if not city:
                raise ResourceNotFoundException(f"City with ID {city_id} not found.")
            if city.state_id != state_id:
                raise InvalidFinancialInputException(
                    f"City '{city.name}' (ID: {city_id}) does not belong to State '{state.name}' (ID: {state_id})."
                )

        rto: Optional[RtoOffice] = None
        if rto_id is not None:
            rto = await loc_repo.get_rto_by_id(rto_id)
            if not rto:
                raise ResourceNotFoundException(f"RTO with ID {rto_id} not found.")
            if rto.state_id != state_id:
                raise InvalidFinancialInputException(
                    f"RTO '{rto.code}' (ID: {rto_id}) does not belong to State '{state.name}' (ID: {state_id})."
                )
            if city_id is not None and rto.city_id is not None and rto.city_id != city_id:
                raise InvalidFinancialInputException(
                    f"RTO '{rto.code}' (ID: {rto_id}) does not belong to City '{city.name if city else city_id}'."
                )

        return state, city, rto

    @classmethod
    async def calculate_capacity(
        cls,
        db: AsyncSession,
        request: AffordabilityCalculateRequest,
    ) -> AffordabilityBudgetBreakdown:
        """Calculates user's total purchasing power, max loan, and safe budget limits."""
        # 1. Location Validation
        await cls.validate_location_hierarchy(
            db=db,
            state_id=request.state_id,
            city_id=request.city_id,
            rto_id=request.rto_id,
        )

        # 2. Profile & FOIR Budget Limits
        profile_cfg = AFFORDABILITY_PROFILES.get(
            request.affordability_profile,
            AFFORDABILITY_PROFILES[AffordabilityProfile.BALANCED],
        )
        max_foir_ratio: Decimal = profile_cfg["max_foir_ratio"]
        max_total_emi = round_inr(request.monthly_take_home_income * max_foir_ratio)
        available_car_emi = max(
            Decimal("0.00"), round_inr(max_total_emi - request.existing_monthly_emi)
        )

        # 3. Resolve Best Available Bank Financing Rate & Terms
        finance_repo = FinanceRepository(db)
        active_products = await finance_repo.get_active_loan_products_for_comparison(
            vehicle_type="CAR",
            is_ev=False,
        )

        calc_date = datetime.now(timezone.utc)
        best_rate = FinanceService.resolve_interest_rate_by_cibil(request.credit_score)
        best_product = None
        max_ltv_percent = Decimal("85.00")
        product_max_loan: Optional[Decimal] = None
        proc_fee = Decimal("0.00")

        if active_products:
            # Evaluate products to find the most competitive rate
            evaluated_products: List[Tuple[Any, Decimal]] = []
            for prod in active_products:
                rate, _, _ = LoanRateResolverService.resolve_product_interest_rate(
                    loan_product=prod,
                    loan_amount=Decimal("1000000.00"),
                    tenure_months=request.preferred_loan_tenure_months,
                    credit_score=request.credit_score,
                    employment_type=request.employment_type or "SALARIED",
                    calculation_date=calc_date,
                )
                evaluated_products.append((prod, rate))

            evaluated_products.sort(key=lambda x: x[1])
            if evaluated_products:
                best_product, best_rate = evaluated_products[0]
                max_ltv_percent = best_product.max_ltv_percent or Decimal("85.00")
                product_max_loan = best_product.max_loan_amount
                proc_fee = round_inr(best_product.min_processing_fee or Decimal("2500.00"))

        assumptions = AffordabilityFinancingAssumption(
            bank_id=best_product.bank_id if best_product else None,
            bank_name=(
                best_product.bank.name
                if (best_product and best_product.bank)
                else "Benchmark Retail Lenders"
            ),
            loan_product_id=best_product.id if best_product else None,
            loan_product_name=best_product.name if best_product else "Standard Auto Loan",
            interest_rate=best_rate,
            tenure_months=request.preferred_loan_tenure_months,
            product_max_ltv_percent=max_ltv_percent,
            product_max_loan_amount=product_max_loan,
            estimated_processing_fee=proc_fee,
        )

        warnings: List[str] = []

        # 4. Handle Case where Existing EMIs consume all capacity
        if available_car_emi <= Decimal("0.00"):
            max_loan = Decimal("0.00")
            max_on_road = request.available_down_payment
            safe_budget = request.available_down_payment
            stretch_budget = request.available_down_payment
            limiting_factor = LimitingFactor.EMI_CAP
            limiting_factor_reason = (
                f"Existing monthly debt of ₹{request.existing_monthly_emi:,.2f} meets or exceeds your "
                f"{profile_cfg['name']} profile's maximum monthly debt ceiling of ₹{max_total_emi:,.2f}."
            )
            warnings.append(
                "Existing debt obligations fully consume your allocated monthly EMI budget. "
                "Consider clearing existing loans or increasing upfront down payment."
            )
            return AffordabilityBudgetBreakdown(
                affordability_profile=request.affordability_profile,
                monthly_take_home_income=request.monthly_take_home_income,
                existing_monthly_emi=request.existing_monthly_emi,
                maximum_total_emi=max_total_emi,
                available_car_emi=Decimal("0.00"),
                available_down_payment=request.available_down_payment,
                maximum_affordable_loan=Decimal("0.00"),
                maximum_affordable_on_road_price=max_on_road,
                recommended_safe_budget=safe_budget,
                stretch_budget=stretch_budget,
                limiting_factor=limiting_factor,
                limiting_factor_reason=limiting_factor_reason,
                applicable_financing_assumptions=assumptions,
                data_status=DATA_STATUS_DEMO,
                warnings=warnings,
                disclaimer=DISCLAIMER_TEXT,
            )

        # 5. Reverse EMI: Calculate Loan Supported by Car EMI Budget
        emi_supported_loan = FinanceService.maximum_loan_for_emi(
            maximum_emi=available_car_emi,
            annual_interest_rate=best_rate,
            tenure_months=request.preferred_loan_tenure_months,
        )

        # 6. Apply Product Caps & LTV Constraints
        max_loan = emi_supported_loan
        limiting_factor = LimitingFactor.EMI_CAP
        limiting_factor_reason = (
            f"Affordability limit is determined by your available monthly car EMI budget of ₹{available_car_emi:,.2f} "
            f"under the {profile_cfg['name']} profile ({float(max_foir_ratio)*100:.0f}% FOIR limit)."
        )

        if product_max_loan is not None and max_loan > product_max_loan:
            max_loan = product_max_loan
            limiting_factor = LimitingFactor.LOAN_MAXIMUM
            limiting_factor_reason = (
                f"Borrowing capacity is capped by the maximum loan limit of ₹{product_max_loan:,.2f} "
                f"for {assumptions.loan_product_name}."
            )

        # Combine with Down Payment for Max On-Road Price
        max_on_road = round_inr(max_loan + request.available_down_payment)

        # Verify LTV ceiling on maximum on-road price
        if max_on_road > 0:
            ltv_ratio = max_ltv_percent / Decimal("100.0")
            if ltv_ratio < Decimal("1.0"):
                # If down payment is 0, maximum loan cannot exceed LTV * On-Road => loan must be 0 if down payment is 0
                ltv_supported_loan = round_inr(
                    (ltv_ratio / (Decimal("1.0") - ltv_ratio)) * request.available_down_payment
                )
                if request.available_down_payment == Decimal("0.00"):
                    warnings.append(
                        f"Most lenders require a minimum {float(Decimal('100.0') - max_ltv_percent):.0f}% down payment. "
                        "Providing a down payment will unlock your full loan capacity."
                    )
                elif ltv_supported_loan < max_loan:
                    max_loan = ltv_supported_loan
                    max_on_road = round_inr(max_loan + request.available_down_payment)
                    limiting_factor = LimitingFactor.LTV_CAP
                    limiting_factor_reason = (
                        f"Borrowing capacity is constrained by the lender's maximum LTV limit of {max_ltv_percent}% "
                        f"and your available down payment of ₹{request.available_down_payment:,.2f}."
                    )

        # Safe & Stretch budget boundaries
        safe_budget = round_inr(max_on_road * profile_cfg["safe_budget_multiplier"])
        stretch_budget = round_inr(max_on_road * profile_cfg["stretch_budget_multiplier"])

        if request.credit_score < 650:
            warnings.append(
                "Credit score is below 650. Lenders may require higher down payments or charge elevated interest rates."
            )

        return AffordabilityBudgetBreakdown(
            affordability_profile=request.affordability_profile,
            monthly_take_home_income=request.monthly_take_home_income,
            existing_monthly_emi=request.existing_monthly_emi,
            maximum_total_emi=max_total_emi,
            available_car_emi=available_car_emi,
            available_down_payment=request.available_down_payment,
            maximum_affordable_loan=max_loan,
            maximum_affordable_on_road_price=max_on_road,
            recommended_safe_budget=safe_budget,
            stretch_budget=stretch_budget,
            limiting_factor=limiting_factor,
            limiting_factor_reason=limiting_factor_reason,
            applicable_financing_assumptions=assumptions,
            data_status=DATA_STATUS_DEMO,
            warnings=warnings,
            disclaimer=DISCLAIMER_TEXT,
        )

    @classmethod
    async def evaluate_vehicle_affordability(
        cls,
        db: AsyncSession,
        request: VehicleAffordabilityRequest,
    ) -> VehicleAffordabilityResponse:
        """Evaluates whether a specific vehicle variant is affordable for the user's financial profile."""
        # 1. Location Validation
        await cls.validate_location_hierarchy(
            db=db,
            state_id=request.state_id,
            city_id=request.city_id,
            rto_id=request.rto_id,
        )

        # 2. Compute User Affordability Capacity
        cap_req = AffordabilityCalculateRequest(
            monthly_take_home_income=request.monthly_take_home_income,
            existing_monthly_emi=request.existing_monthly_emi,
            available_down_payment=request.available_down_payment,
            state_id=request.state_id,
            city_id=request.city_id,
            rto_id=request.rto_id,
            credit_score=request.credit_score,
            preferred_loan_tenure_months=request.preferred_loan_tenure_months,
            affordability_profile=request.affordability_profile,
        )
        user_capacity = await cls.calculate_capacity(db, cap_req)
        available_car_emi = user_capacity.available_car_emi
        profile_cfg = AFFORDABILITY_PROFILES.get(
            request.affordability_profile,
            AFFORDABILITY_PROFILES[AffordabilityProfile.BALANCED],
        )

        # 3. Vehicle Variant Lookup
        veh_repo = VehicleRepository(db)
        variant = await veh_repo.get_variant_by_id(request.variant_id)
        if not variant:
            raise ResourceNotFoundException(
                f"Vehicle variant with ID {request.variant_id} not found."
            )

        # 4. Authoritative Location-Specific On-Road Price Calculation
        pricing_req = OnRoadPriceCalculationRequest(
            variant_id=request.variant_id,
            state_id=request.state_id,
            city_id=request.city_id,
            rto_id=request.rto_id,
            calculation_date=datetime.now(timezone.utc),
            insurance_option="ZERO_DEP",
            is_bh_series=False,
            is_financed=True,
        )
        pricing_res = await OnRoadPriceCalculationService.calculate_on_road_price(db, pricing_req)
        on_road_price = pricing_res.totals.on_road_price
        ex_showroom_price = pricing_res.totals.ex_showroom_price

        # Down Payment & Loan Requirement
        down_payment = (
            request.down_payment_override
            if request.down_payment_override is not None
            else request.available_down_payment
        )
        if down_payment > on_road_price:
            down_payment = on_road_price
        required_loan = round_inr(max(Decimal("0.00"), on_road_price - down_payment))

        # 5. Handle Zero-Loan (100% Cash/Down Payment) Edge Case
        if required_loan == Decimal("0.00"):
            return VehicleAffordabilityResponse(
                variant_id=variant.id,
                variant_name=variant.name,
                model_name=variant.model.name if variant.model else "",
                manufacturer_name=(
                    variant.model.manufacturer.name
                    if (variant.model and variant.model.manufacturer)
                    else ""
                ),
                fuel_type=variant.fuel_type or "PETROL",
                transmission=variant.transmission or "MANUAL",
                ex_showroom_price=ex_showroom_price,
                on_road_price=on_road_price,
                down_payment=down_payment,
                required_loan=Decimal("0.00"),
                estimated_emi=Decimal("0.00"),
                available_car_emi=available_car_emi,
                emi_headroom=available_car_emi,
                affordable=True,
                affordability_status=AffordabilityStatus.COMFORTABLE,
                affordability_rationale=(
                    f"Fully affordable with upfront cash/down payment of ₹{down_payment:,.2f} "
                    f"covering the entire on-road price of ₹{on_road_price:,.2f} (₹0 loan required)."
                ),
                limiting_factor=None,
                selected_loan_offer=None,
                all_eligible_loan_offers=[],
                data_status=DATA_STATUS_DEMO,
                disclaimer=DISCLAIMER_TEXT,
            )

        # 6. Evaluate Bank Financing via Finance Engine
        bank_req = BankComparisonRequest(
            vehicle_variant_id=request.variant_id,
            state_id=request.state_id,
            city_id=request.city_id,
            rto_id=request.rto_id,
            down_payment=down_payment,
            loan_tenure_months=request.preferred_loan_tenure_months,
            credit_score=request.credit_score,
            monthly_income=request.monthly_take_home_income,
            employment_type="SALARIED",
            calculation_date=datetime.now(timezone.utc),
        )
        bank_comp = await FinancingEngineService.compare_bank_financing_offers(db, bank_req)
        offers = bank_comp.offers
        eligible_offers = [o for o in offers if o.estimated_eligibility]

        if not offers:
            return VehicleAffordabilityResponse(
                variant_id=variant.id,
                variant_name=variant.name,
                model_name=variant.model.name if variant.model else "",
                manufacturer_name=(
                    variant.model.manufacturer.name
                    if (variant.model and variant.model.manufacturer)
                    else ""
                ),
                fuel_type=variant.fuel_type or "PETROL",
                transmission=variant.transmission or "MANUAL",
                ex_showroom_price=ex_showroom_price,
                on_road_price=on_road_price,
                down_payment=down_payment,
                required_loan=required_loan,
                estimated_emi=Decimal("0.00"),
                available_car_emi=available_car_emi,
                emi_headroom=available_car_emi,
                affordable=False,
                affordability_status=AffordabilityStatus.NO_FINANCING_OPTION,
                affordability_rationale="No financing products could be resolved for this vehicle and location.",
                limiting_factor=LimitingFactor.NO_ELIGIBLE_LOAN,
                selected_loan_offer=None,
                all_eligible_loan_offers=[],
                data_status=DATA_STATUS_DEMO,
                disclaimer=DISCLAIMER_TEXT,
            )

        selected_offer: LoanOfferItem = eligible_offers[0] if eligible_offers else offers[0]
        estimated_emi = selected_offer.monthly_emi
        emi_headroom = round_inr(available_car_emi - estimated_emi)

        # Check if offer is eligible
        if not selected_offer.estimated_eligibility:
            reasons = (
                "; ".join(selected_offer.eligibility_reasons)
                if selected_offer.eligibility_reasons
                else "Lender criteria not met"
            )
            return VehicleAffordabilityResponse(
                variant_id=variant.id,
                variant_name=variant.name,
                model_name=variant.model.name if variant.model else "",
                manufacturer_name=(
                    variant.model.manufacturer.name
                    if (variant.model and variant.model.manufacturer)
                    else ""
                ),
                fuel_type=variant.fuel_type or "PETROL",
                transmission=variant.transmission or "MANUAL",
                ex_showroom_price=ex_showroom_price,
                on_road_price=on_road_price,
                down_payment=down_payment,
                required_loan=required_loan,
                estimated_emi=estimated_emi,
                available_car_emi=available_car_emi,
                emi_headroom=emi_headroom,
                affordable=False,
                affordability_status=AffordabilityStatus.NO_FINANCING_OPTION,
                affordability_rationale=f"No eligible financing options found. Primary reason: {reasons}.",
                limiting_factor=LimitingFactor.ELIGIBILITY,
                selected_offer=selected_offer,
                all_eligible_loan_offers=[],
                data_status=DATA_STATUS_DEMO,
                disclaimer=DISCLAIMER_TEXT,
            )

        # 7. Affordability Status Categorization
        if available_car_emi <= Decimal("0.00"):
            status = AffordabilityStatus.NOT_AFFORDABLE
            affordable = False
            limiting_factor = LimitingFactor.EMI_CAP
            rationale = (
                f"Not affordable. Existing debt obligations leave ₹0 available car EMI capacity, "
                f"while this vehicle requires a monthly EMI of ₹{estimated_emi:,.2f}."
            )
        elif estimated_emi <= available_car_emi:
            headroom_ratio = (
                emi_headroom / available_car_emi if available_car_emi > 0 else Decimal("0.00")
            )
            if headroom_ratio >= HEADROOM_COMFORTABLE_THRESHOLD:
                status = AffordabilityStatus.COMFORTABLE
                affordable = True
                limiting_factor = None
                rationale = (
                    f"Comfortably affordable. Required monthly EMI of ₹{estimated_emi:,.2f} leaves "
                    f"₹{emi_headroom:,.2f} surplus ({float(headroom_ratio)*100:.0f}% headroom) in your monthly car budget."
                )
            else:
                status = AffordabilityStatus.AFFORDABLE
                affordable = True
                limiting_factor = None
                rationale = (
                    f"Affordable within your {profile_cfg['name']} profile. Monthly EMI of ₹{estimated_emi:,.2f} "
                    f"fits within your ₹{available_car_emi:,.2f} allocated budget."
                )
        else:
            # Check if fits within absolute Stretch limit (40% FOIR)
            stretch_max_total_emi = round_inr(request.monthly_take_home_income * Decimal("0.40"))
            stretch_car_emi = max(
                Decimal("0.00"), round_inr(stretch_max_total_emi - request.existing_monthly_emi)
            )

            if estimated_emi <= stretch_car_emi:
                status = AffordabilityStatus.STRETCH
                affordable = False
                limiting_factor = LimitingFactor.EMI_CAP
                rationale = (
                    f"Stretch budget. Monthly EMI of ₹{estimated_emi:,.2f} exceeds your {profile_cfg['name']} "
                    f"budget by ₹{(-emi_headroom):,.2f}/month, but falls within an extended 40% debt limit."
                )
            else:
                status = AffordabilityStatus.NOT_AFFORDABLE
                affordable = False
                limiting_factor = LimitingFactor.EMI_CAP
                rationale = (
                    f"Not affordable. Monthly EMI of ₹{estimated_emi:,.2f} exceeds your available "
                    f"budget of ₹{available_car_emi:,.2f} by ₹{(-emi_headroom):,.2f}/month."
                )

        return VehicleAffordabilityResponse(
            variant_id=variant.id,
            variant_name=variant.name,
            model_name=variant.model.name if variant.model else "",
            manufacturer_name=(
                variant.model.manufacturer.name
                if (variant.model and variant.model.manufacturer)
                else ""
            ),
            fuel_type=variant.fuel_type or "PETROL",
            transmission=variant.transmission or "MANUAL",
            ex_showroom_price=ex_showroom_price,
            on_road_price=on_road_price,
            down_payment=down_payment,
            required_loan=required_loan,
            estimated_emi=estimated_emi,
            available_car_emi=available_car_emi,
            emi_headroom=emi_headroom,
            affordable=affordable,
            affordability_status=status,
            affordability_rationale=rationale,
            limiting_factor=limiting_factor,
            selected_loan_offer=selected_offer,
            all_eligible_loan_offers=eligible_offers,
            data_status=DATA_STATUS_DEMO,
            disclaimer=DISCLAIMER_TEXT,
        )

    @classmethod
    async def evaluate_multiple_vehicles(
        cls,
        db: AsyncSession,
        request: MultiVehicleAffordabilityRequest,
    ) -> MultiVehicleAffordabilityResponse:
        """Batch evaluates affordability for up to 20 vehicle variants."""
        results: List[VehicleAffordabilityResponse] = []
        for v_id in request.variant_ids:
            veh_req = VehicleAffordabilityRequest(
                variant_id=v_id,
                monthly_take_home_income=request.monthly_take_home_income,
                existing_monthly_emi=request.existing_monthly_emi,
                available_down_payment=request.available_down_payment,
                state_id=request.state_id,
                city_id=request.city_id,
                rto_id=request.rto_id,
                credit_score=request.credit_score,
                preferred_loan_tenure_months=request.preferred_loan_tenure_months,
                affordability_profile=request.affordability_profile,
            )
            eval_res = await cls.evaluate_vehicle_affordability(db, veh_req)
            results.append(eval_res)

        aff_count = sum(
            1
            for r in results
            if r.affordability_status
            in (AffordabilityStatus.COMFORTABLE, AffordabilityStatus.AFFORDABLE)
        )
        stretch_count = sum(
            1 for r in results if r.affordability_status == AffordabilityStatus.STRETCH
        )
        unaff_count = sum(
            1
            for r in results
            if r.affordability_status
            in (AffordabilityStatus.NOT_AFFORDABLE, AffordabilityStatus.NO_FINANCING_OPTION)
        )

        return MultiVehicleAffordabilityResponse(
            results=results,
            total_evaluated=len(results),
            affordable_count=aff_count,
            stretch_count=stretch_count,
            unaffordable_count=unaff_count,
            data_status=DATA_STATUS_DEMO,
            disclaimer=DISCLAIMER_TEXT,
        )

    @classmethod
    async def compare_vehicles(
        cls,
        db: AsyncSession,
        request: AffordabilityComparisonRequest,
    ) -> AffordabilityComparisonResponse:
        """Compares 2-5 vehicles against the user's financial profile side-by-side."""
        cap_req = AffordabilityCalculateRequest(
            monthly_take_home_income=request.monthly_take_home_income,
            existing_monthly_emi=request.existing_monthly_emi,
            available_down_payment=request.available_down_payment,
            state_id=request.state_id,
            city_id=request.city_id,
            rto_id=request.rto_id,
            credit_score=request.credit_score,
            preferred_loan_tenure_months=request.preferred_loan_tenure_months,
            affordability_profile=request.affordability_profile,
        )
        user_capacity = await cls.calculate_capacity(db, cap_req)

        multi_req = MultiVehicleAffordabilityRequest(
            variant_ids=request.variant_ids,
            monthly_take_home_income=request.monthly_take_home_income,
            existing_monthly_emi=request.existing_monthly_emi,
            available_down_payment=request.available_down_payment,
            state_id=request.state_id,
            city_id=request.city_id,
            rto_id=request.rto_id,
            credit_score=request.credit_score,
            preferred_loan_tenure_months=request.preferred_loan_tenure_months,
            affordability_profile=request.affordability_profile,
        )
        multi_res = await cls.evaluate_multiple_vehicles(db, multi_req)
        vehicles = multi_res.results

        # Generate comparative notes
        notes: List[str] = []
        if vehicles:
            cheapest = min(vehicles, key=lambda v: v.on_road_price)
            lowest_emi = min(vehicles, key=lambda v: v.estimated_emi)
            notes.append(
                f"Lowest on-road price: {cheapest.manufacturer_name} {cheapest.model_name} {cheapest.variant_name} "
                f"(₹{cheapest.on_road_price:,.2f})."
            )
            notes.append(
                f"Lowest monthly commitment: {lowest_emi.manufacturer_name} {lowest_emi.model_name} {lowest_emi.variant_name} "
                f"(₹{lowest_emi.estimated_emi:,.2f}/month)."
            )

            affordable_vehicles = [v for v in vehicles if v.affordable]
            if affordable_vehicles:
                notes.append(
                    f"{len(affordable_vehicles)} of {len(vehicles)} compared vehicles fit comfortably within your "
                    f"budget of ₹{user_capacity.available_car_emi:,.2f}/month."
                )
            else:
                notes.append(
                    "None of the compared vehicles fit within your current recommended monthly car budget. "
                    "Consider extending tenure or increasing upfront down payment."
                )

        return AffordabilityComparisonResponse(
            user_budget_summary=user_capacity,
            vehicles=vehicles,
            comparison_notes=notes,
            data_status=DATA_STATUS_DEMO,
            disclaimer=DISCLAIMER_TEXT,
        )

    @classmethod
    def get_profiles(cls) -> List[AffordabilityProfileInfo]:
        """Returns all configured affordability risk profiles and their descriptive thresholds."""
        profiles: List[AffordabilityProfileInfo] = []
        for code, cfg in AFFORDABILITY_PROFILES.items():
            max_foir = cfg["max_foir_ratio"]
            profiles.append(
                AffordabilityProfileInfo(
                    code=code,
                    name=cfg["name"],
                    max_foir_ratio=max_foir,
                    max_foir_percent=round_inr(max_foir * Decimal("100.0")),
                    safe_budget_multiplier=cfg["safe_budget_multiplier"],
                    stretch_budget_multiplier=cfg["stretch_budget_multiplier"],
                    description=cfg["description"],
                )
            )
        return profiles
