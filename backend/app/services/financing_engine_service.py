from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidFinancialInputException, ResourceNotFoundException
from app.models.finance import Bank, LoanProduct
from app.models.location import State
from app.models.vehicle import Variant
from app.repositories.finance_repo import FinanceRepository
from app.repositories.location_repo import LocationRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.finance import (
    AmortizationScheduleItem,
    BankComparisonRequest,
    BankComparisonResponse,
    FeeBreakdownItem,
    FinanceCalculationRequest,
    FinanceCalculationResponse,
    LoanOfferItem,
)
from app.schemas.pricing import OnRoadPriceCalculationRequest
from app.services.finance_service import FinanceService
from app.services.loan_eligibility_service import LoanEligibilityEvaluatorService
from app.services.loan_fee_service import LoanFeeCalculatorService
from app.services.loan_rate_resolver import LoanRateResolverService
from app.services.on_road_price_service import OnRoadPriceCalculationService


def round_inr(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class FinancingEngineService:
    """Orchestrates vehicle financing calculations, bank product comparison, and on-road price integration.

    Responsibilities:
    - Authoritative on-road price lookup via OnRoadPriceCalculationService when vehicle is supplied.
    - Rate resolution across multiple commercial banks.
    - Processing fees and statutory charges calculation.
    - Pre-qualification eligibility rule checks.
    - Comparison ranking across loan products.
    """

    @classmethod
    async def _resolve_on_road_price_and_vehicle(
        cls,
        db: AsyncSession,
        variant_id: Optional[int],
        state_id: Optional[int],
        city_id: Optional[int],
        rto_id: Optional[int],
        explicit_on_road_price: Optional[Decimal],
        calculation_date: datetime,
    ) -> Tuple[Decimal, Optional[str], Optional[str], Optional[str], bool, str]:
        """Resolves authoritative on-road price and vehicle metadata."""
        if variant_id is not None:
            if state_id is None:
                raise InvalidFinancialInputException(
                    "state_id is required when vehicle_variant_id is provided to calculate authoritative on-road price."
                )

            pricing_req = OnRoadPriceCalculationRequest(
                variant_id=variant_id,
                state_id=state_id,
                city_id=city_id,
                rto_id=rto_id,
                calculation_date=calculation_date,
                insurance_option="ZERO_DEP",
                is_bh_series=False,
                is_financed=True,
            )
            pricing_res = await OnRoadPriceCalculationService.calculate_on_road_price(
                db, pricing_req
            )
            on_road = pricing_res.totals.on_road_price
            v_name = pricing_res.vehicle.variant_name
            m_name = pricing_res.vehicle.model_name
            mfg_name = pricing_res.vehicle.manufacturer_name
            is_ev = pricing_res.vehicle.is_ev
            v_type = pricing_res.vehicle.vehicle_type
            return on_road, v_name, m_name, mfg_name, is_ev, v_type

        elif explicit_on_road_price is not None and explicit_on_road_price > 0:
            return round_inr(explicit_on_road_price), None, None, None, False, "CAR"
        else:
            raise InvalidFinancialInputException(
                "Either vehicle_variant_id (with state_id) or explicit on_road_price must be provided."
            )

    @classmethod
    def _evaluate_single_product_offer(
        cls,
        loan_product: LoanProduct,
        loan_amount: Decimal,
        on_road_price: Decimal,
        tenure_months: int,
        credit_score: Optional[int],
        monthly_income: Optional[Decimal],
        applicant_age: Optional[int],
        employment_type: Optional[str],
        calculation_date: datetime,
    ) -> LoanOfferItem:
        """Evaluates interest rate, fees, EMI, and eligibility for a single bank loan product."""
        # 1. Rate Resolution
        rate, rate_type, matched_rate_record = (
            LoanRateResolverService.resolve_product_interest_rate(
                loan_product=loan_product,
                loan_amount=loan_amount,
                tenure_months=tenure_months,
                credit_score=credit_score,
                employment_type=employment_type,
                calculation_date=calculation_date,
            )
        )

        # 2. Fee Calculation
        total_fees, fee_items = LoanFeeCalculatorService.calculate_product_fees(
            loan_product=loan_product,
            loan_amount=loan_amount,
            calculation_date=calculation_date,
        )
        proc_fee = next(
            (f.calculated_amount for f in fee_items if f.fee_type == "PROCESSING_FEE"),
            total_fees,
        )

        # 3. Eligibility Check
        is_eligible, elig_status, reasons = (
            LoanEligibilityEvaluatorService.evaluate_product_eligibility(
                loan_product=loan_product,
                loan_amount=loan_amount,
                on_road_price=on_road_price,
                tenure_months=tenure_months,
                credit_score=credit_score,
                monthly_income=monthly_income,
                applicant_age=applicant_age,
                employment_type=employment_type,
                calculation_date=calculation_date,
            )
        )

        # 4. EMI & Totals Calculation
        if loan_amount > 0:
            emi = FinanceService.calculate_emi(
                principal=loan_amount,
                annual_interest_rate=rate,
                tenure_months=tenure_months,
            )
            total_repayment = round_inr(emi * Decimal(str(tenure_months)))
            total_interest = round_inr(total_repayment - loan_amount)
        else:
            emi = Decimal("0.00")
            total_repayment = Decimal("0.00")
            total_interest = Decimal("0.00")

        ltv = FinanceService.calculate_ltv(loan_amount=loan_amount, on_road_price=on_road_price)
        bank = loan_product.bank

        eff_from = (
            matched_rate_record.effective_from
            if matched_rate_record
            else datetime(2024, 1, 1, tzinfo=timezone.utc)
        )
        eff_to = matched_rate_record.effective_to if matched_rate_record else None
        source_name = "Partner Bank Tariff Bulletin"
        try:
            if matched_rate_record and matched_rate_record.source:
                source_name = matched_rate_record.source.name
        except Exception:
            pass

        return LoanOfferItem(
            bank_id=bank.id,
            bank_name=bank.name,
            bank_slug=bank.slug,
            bank_type=bank.bank_type,
            logo_url=bank.logo_url,
            loan_product_id=loan_product.id,
            product_name=loan_product.name,
            product_slug=loan_product.slug,
            product_category=loan_product.product_category,
            annual_interest_rate=rate,
            rate_type=rate_type,
            tenure_months=tenure_months,
            principal_loan_amount=loan_amount,
            monthly_emi=emi,
            total_interest=total_interest,
            total_repayment=total_repayment,
            ltv_percent=ltv,
            processing_fee=proc_fee,
            total_fees=total_fees,
            fees_breakdown=fee_items,
            estimated_eligibility=is_eligible,
            eligibility_status=elig_status,
            eligibility_reasons=reasons,
            rate_effective_from=eff_from,
            rate_effective_to=eff_to,
            rate_source_name=source_name,
            data_status="DEMO",
            disclaimer="Estimated eligibility only - not a credit sanction. Actual rates and fees depend on bank underwriting.",
        )

    @classmethod
    async def calculate_financing(
        cls,
        db: AsyncSession,
        request: FinanceCalculationRequest,
    ) -> FinanceCalculationResponse:
        """Calculates detailed financing summary for a specific or optimal loan product."""
        calc_date = request.calculation_date or datetime.now(timezone.utc)
        if calc_date.tzinfo is None:
            calc_date = calc_date.replace(tzinfo=timezone.utc)

        # 1. Resolve on-road price & vehicle
        (
            on_road_price,
            v_name,
            m_name,
            mfg_name,
            is_ev,
            v_type,
        ) = await cls._resolve_on_road_price_and_vehicle(
            db=db,
            variant_id=request.vehicle_variant_id,
            state_id=request.state_id,
            city_id=request.city_id,
            rto_id=request.rto_id,
            explicit_on_road_price=request.on_road_price,
            calculation_date=calc_date,
        )

        down_payment = max(Decimal("0.00"), request.down_payment)
        if down_payment > on_road_price:
            down_payment = on_road_price
        loan_amount = round_inr(max(Decimal("0.00"), on_road_price - down_payment))

        # 2. Query target product or best product
        repo = FinanceRepository(db)
        target_product: Optional[LoanProduct] = None

        if request.loan_product_id:
            target_product = await repo.get_loan_product_by_id(request.loan_product_id)
            if not target_product:
                raise ResourceNotFoundException(
                    f"Loan product with ID {request.loan_product_id} not found."
                )
        elif request.bank_id:
            bank = await repo.get_bank_by_id(request.bank_id)
            if not bank:
                raise ResourceNotFoundException(f"Bank with ID {request.bank_id} not found.")
            # Select first active product matching vehicle
            products = bank.loan_products or []
            target_product = next((p for p in products if p.active), None)
            if not target_product:
                raise ResourceNotFoundException(
                    f"No active loan product found for Bank {bank.name}."
                )
        else:
            # Query all active products and select the best offer
            active_products = await repo.get_active_loan_products_for_comparison(
                vehicle_type=v_type,
                is_ev=is_ev,
            )
            if not active_products:
                raise ResourceNotFoundException(
                    "No active loan products available for financing calculation."
                )

            # Evaluate all and choose the one with lowest EMI / lowest rate
            offers = [
                cls._evaluate_single_product_offer(
                    loan_product=p,
                    loan_amount=loan_amount,
                    on_road_price=on_road_price,
                    tenure_months=request.loan_tenure_months,
                    credit_score=request.credit_score,
                    monthly_income=request.monthly_income,
                    applicant_age=request.applicant_age,
                    employment_type=request.employment_type,
                    calculation_date=calc_date,
                )
                for p in active_products
            ]
            offers.sort(
                key=lambda o: (not o.estimated_eligibility, o.monthly_emi, o.annual_interest_rate)
            )
            selected_offer = offers[0]
            target_product = next(
                p for p in active_products if p.id == selected_offer.loan_product_id
            )

        # 3. Generate offer for target product
        offer = cls._evaluate_single_product_offer(
            loan_product=target_product,
            loan_amount=loan_amount,
            on_road_price=on_road_price,
            tenure_months=request.loan_tenure_months,
            credit_score=request.credit_score,
            monthly_income=request.monthly_income,
            applicant_age=request.applicant_age,
            employment_type=request.employment_type,
            calculation_date=calc_date,
        )

        # 4. Optional Amortization Schedule
        schedule: Optional[List[AmortizationScheduleItem]] = None
        if request.include_amortization and loan_amount > 0:
            schedule = FinanceService.calculate_amortization_schedule(
                principal=loan_amount,
                annual_interest_rate=offer.annual_interest_rate,
                tenure_months=request.loan_tenure_months,
            )

        return FinanceCalculationResponse(
            variant_id=request.vehicle_variant_id,
            variant_name=v_name,
            model_name=m_name,
            manufacturer_name=mfg_name,
            on_road_price=on_road_price,
            down_payment=down_payment,
            loan_amount=loan_amount,
            tenure_months=request.loan_tenure_months,
            credit_score_used=request.credit_score or 750,
            calculation_date=calc_date,
            selected_offer=offer,
            amortization_schedule=schedule,
            data_quality={
                "is_estimated": True,
                "data_status": "DEMO",
                "disclaimer": "Financing terms are based on demonstration bank products and do not constitute an official loan sanction.",
            },
        )

    @classmethod
    async def compare_bank_financing_offers(
        cls,
        db: AsyncSession,
        request: BankComparisonRequest,
    ) -> BankComparisonResponse:
        """Compares loan offers across all available commercial banks and NBFC products."""
        calc_date = request.calculation_date or datetime.now(timezone.utc)
        if calc_date.tzinfo is None:
            calc_date = calc_date.replace(tzinfo=timezone.utc)

        # 1. Resolve on-road price & vehicle
        (
            on_road_price,
            v_name,
            m_name,
            mfg_name,
            is_ev,
            v_type,
        ) = await cls._resolve_on_road_price_and_vehicle(
            db=db,
            variant_id=request.vehicle_variant_id,
            state_id=request.state_id,
            city_id=request.city_id,
            rto_id=request.rto_id,
            explicit_on_road_price=request.on_road_price,
            calculation_date=calc_date,
        )

        down_payment = max(Decimal("0.00"), request.down_payment)
        if down_payment > on_road_price:
            down_payment = on_road_price
        loan_amount = round_inr(max(Decimal("0.00"), on_road_price - down_payment))

        # 2. Fetch all candidate active loan products
        repo = FinanceRepository(db)
        products = await repo.get_active_loan_products_for_comparison(
            vehicle_type=v_type,
            is_ev=is_ev,
        )

        offers: List[LoanOfferItem] = []
        for p in products:
            offer = cls._evaluate_single_product_offer(
                loan_product=p,
                loan_amount=loan_amount,
                on_road_price=on_road_price,
                tenure_months=request.loan_tenure_months,
                credit_score=request.credit_score,
                monthly_income=request.monthly_income,
                applicant_age=request.applicant_age,
                employment_type=request.employment_type,
                calculation_date=calc_date,
            )
            offers.append(offer)

        # 3. Sort offers:
        # - Estimated Eligibility (Eligible > Marginal > Ineligible)
        # - Monthly EMI ASC
        # - Processing Fee ASC
        offers.sort(
            key=lambda o: (
                (
                    0
                    if o.eligibility_status == "ESTIMATED_ELIGIBLE"
                    else (1 if o.eligibility_status == "MARGINAL" else 2)
                ),
                o.monthly_emi,
                o.total_fees,
            )
        )

        if offers:
            offers[0].is_recommended = True

        eligible_count = sum(1 for o in offers if o.estimated_eligibility)

        return BankComparisonResponse(
            variant_id=request.vehicle_variant_id,
            variant_name=v_name,
            model_name=m_name,
            manufacturer_name=mfg_name,
            on_road_price=on_road_price,
            down_payment=down_payment,
            loan_amount=loan_amount,
            tenure_months=request.loan_tenure_months,
            credit_score_used=request.credit_score or 750,
            calculation_date=calc_date,
            offers=offers,
            total_offers_count=len(offers),
            eligible_offers_count=eligible_count,
            data_quality={
                "is_estimated": True,
                "data_status": "DEMO",
                "disclaimer": "Financing terms are based on demonstration bank products and do not constitute an official loan sanction.",
            },
        )
