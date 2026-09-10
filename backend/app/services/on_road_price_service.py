from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundException
from app.models.location import City, RtoOffice, State
from app.models.pricing import VehiclePrice
from app.models.vehicle import Variant
from app.repositories.location_repo import LocationRepository
from app.repositories.pricing_repo import PricingRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.pricing import (
    DataQualityInfo,
    OnRoadPriceCalculationRequest,
    OnRoadPriceResponse,
    OnRoadPriceTotals,
    PriceBreakdownItem,
)
from app.schemas.tax_rule import (
    LocationResolutionContext,
    ResolvedTaxRuleItem,
    VehicleResolutionContext,
)
from app.services.insurance_service import InsuranceService
from app.services.tax_rule_resolver import TaxRuleResolverService


def round_inr(amount: Decimal) -> Decimal:
    """Rounds currency amounts to 2 decimal places using standard ROUND_HALF_UP."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class OnRoadPriceCalculationService:
    """Pure domain calculation engine for Indian vehicle on-road pricing.

    Consumes:
    - Vehicle Catalogue & Historical Ex-Showroom Pricing
    - Location Domain & Hierarchy
    - Tax & Registration Rules Domain via TaxRuleResolverService
    - Insurance Tariff Estimation & User Custom Quotes
    """

    @classmethod
    async def calculate_on_road_price(
        cls,
        db: AsyncSession,
        request: OnRoadPriceCalculationRequest,
    ) -> OnRoadPriceResponse:
        calc_date = request.calculation_date or datetime.now(timezone.utc)
        if calc_date.tzinfo is None:
            calc_date = calc_date.replace(tzinfo=timezone.utc)

        vehicle_repo = VehicleRepository(db)
        pricing_repo = PricingRepository(db)

        # =========================================================================
        # 1. VEHICLE RESOLUTION & VALIDATION
        # =========================================================================
        variant = await vehicle_repo.get_variant_by_id(request.variant_id)
        if not variant:
            raise ResourceNotFoundException(
                f"Vehicle variant with ID {request.variant_id} not found."
            )

        # =========================================================================
        # 2. LOCATION HIERARCHY VALIDATION
        # =========================================================================
        state = await db.get(State, request.state_id)
        if not state:
            raise ResourceNotFoundException(f"State with ID {request.state_id} not found.")

        city: Optional[City] = None
        if request.city_id is not None:
            city = await db.get(City, request.city_id)
            if not city:
                raise ResourceNotFoundException(f"City with ID {request.city_id} not found.")
            if city.state_id != state.id:
                raise ValueError(
                    f"City '{city.name}' (id={city.id}) does not belong to State '{state.name}' (id={state.id})."
                )

        rto: Optional[RtoOffice] = None
        if request.rto_id is not None:
            rto = await db.get(RtoOffice, request.rto_id)
            if not rto:
                raise ResourceNotFoundException(f"RTO with ID {request.rto_id} not found.")
            if rto.state_id != state.id:
                raise ValueError(
                    f"RTO '{rto.code}' (id={rto.id}) does not belong to State '{state.name}' (id={state.id})."
                )

        # =========================================================================
        # 3. AUTHORITATIVE HISTORICAL / ACTIVE PRICE RESOLUTION
        # =========================================================================
        active_price = await vehicle_repo.get_current_price(variant.id, as_of_date=calc_date)

        ex_showroom_price: Optional[Decimal] = None
        price_source_name = "OEM Price Bulletin"
        price_source_url: Optional[str] = None
        price_eff_from = calc_date
        price_eff_to = None

        if active_price:
            ex_showroom_price = round_inr(active_price.ex_showroom_price)
            if active_price.source:
                price_source_name = active_price.source.name
                price_source_url = active_price.source.base_url
            price_eff_from = active_price.effective_from
            price_eff_to = active_price.effective_to
        else:
            # Fallback check on ExShowroomPrice table
            legacy_price = await pricing_repo.get_ex_showroom_price(
                variant_id=variant.id,
                state_id=state.id,
                city_id=request.city_id,
            )
            if legacy_price:
                ex_showroom_price = round_inr(legacy_price.price_inr)

        if ex_showroom_price is None:
            raise ResourceNotFoundException(
                f"No active ex-showroom price found for variant '{variant.name}' on calculation date {calc_date.strftime('%Y-%m-%d')}."
            )

        is_ev = (
            variant.fuel_type.upper() in ["ELECTRIC", "EV"]
            or variant.battery_capacity_kwh is not None
        )
        engine_cc = variant.engine_cc or (
            variant.specification.engine_displacement_cc
            if variant.specification
            else (None if is_ev else 1199)
        )

        # Construct Context DTOs
        vehicle_ctx = VehicleResolutionContext(
            variant_id=variant.id,
            variant_name=variant.name,
            model_name=variant.model.name if variant.model else None,
            manufacturer_name=(
                variant.model.manufacturer.name
                if variant.model and variant.model.manufacturer
                else None
            ),
            fuel_type=variant.fuel_type,
            engine_cc=engine_cc,
            ex_showroom_price=ex_showroom_price,
            is_ev=is_ev,
            vehicle_type="CAR",
            usage_type="PRIVATE",
        )

        location_ctx = LocationResolutionContext(
            state_id=state.id,
            state_name=state.name,
            state_code=state.code,
            city_id=city.id if city else None,
            city_name=city.name if city else None,
            rto_id=rto.id if rto else None,
            rto_code=rto.code if rto else None,
            rto_name=rto.name if rto else None,
        )

        # =========================================================================
        # 4. STATUTORY TAX RULE RESOLUTION
        # =========================================================================
        rule_res = await TaxRuleResolverService.resolve_rules(
            db=db,
            state_id=state.id,
            city_id=city.id if city else None,
            rto_id=rto.id if rto else None,
            variant_id=variant.id,
            fuel_type=variant.fuel_type,
            engine_cc=engine_cc,
            ex_showroom_price=ex_showroom_price,
            is_ev=is_ev,
            vehicle_type="CAR",
            usage_type="PRIVATE",
            calculation_date=calc_date,
            is_bh_series=request.is_bh_series,
            is_financed=request.is_financed,
        )

        # =========================================================================
        # 5. LINE-ITEM MONETARY CALCULATIONS
        # =========================================================================
        breakdown_items: List[PriceBreakdownItem] = []

        # 5.1 Base Ex-Showroom Line Item
        breakdown_items.append(
            PriceBreakdownItem(
                component="EX_SHOWROOM",
                rule_name="Ex-Showroom Price",
                calculation_method="BASE_PRICE",
                base_amount=ex_showroom_price,
                calculated_amount=ex_showroom_price,
                source=price_source_name,
                source_url=price_source_url,
                effective_from=price_eff_from,
                effective_to=price_eff_to,
                explanation=f"Base ex-showroom retail price effective as of {calc_date.strftime('%Y-%m-%d')}",
                is_estimated=False,
                status="APPLIED",
            )
        )

        # Map to store intermediate calculated amounts for dependent rules (e.g. Cess on Road Tax)
        calculated_tax_map: Dict[str, Decimal] = {}
        road_tax_amount = Decimal("0.00")

        # 5.2 Process Statutory Rules
        for rule in rule_res.rules:
            # Determine base amount for calculation
            base_amount = ex_showroom_price
            if rule.base_amount_type == "ROAD_TAX":
                base_amount = road_tax_amount
            elif rule.base_amount_type == "BASE_TAX":
                base_amount = road_tax_amount
            elif rule.base_amount_type == "FIXED":
                base_amount = Decimal("0.00")

            calculated_amount = Decimal("0.00")
            rate_applied: Optional[Decimal] = rule.rate
            fixed_applied: Optional[Decimal] = rule.fixed_amount
            explanation = ""

            # Method: FIXED
            if rule.calculation_method == "FIXED":
                calculated_amount = round_inr(rule.fixed_amount or Decimal("0.00"))
                fixed_applied = calculated_amount
                explanation = f"Statutory fixed fee of ₹{calculated_amount:,.2f}"

            # Method: PERCENTAGE
            elif rule.calculation_method == "PERCENTAGE":
                rate_val = rule.rate or Decimal("0.00")
                rate_applied = rate_val
                calculated_amount = round_inr(base_amount * (rate_val / Decimal("100.0")))
                explanation = f"{rate_val}% on {rule.base_amount_type.replace('_', ' ').title()} (₹{base_amount:,.2f})"

            # Method: BRACKETED
            elif rule.calculation_method == "BRACKETED":
                matched_bracket = None
                for brk in rule.brackets:
                    min_v = Decimal(str(brk.minimum_value))
                    max_v = (
                        Decimal(str(brk.maximum_value)) if brk.maximum_value is not None else None
                    )

                    if min_v <= base_amount:
                        if max_v is None or base_amount <= max_v:
                            matched_bracket = brk
                            break

                if matched_bracket:
                    b_rate = (
                        Decimal(str(matched_bracket.rate))
                        if matched_bracket.rate is not None
                        else Decimal("0.00")
                    )
                    b_fixed = (
                        Decimal(str(matched_bracket.fixed_amount))
                        if matched_bracket.fixed_amount is not None
                        else Decimal("0.00")
                    )
                    rate_applied = b_rate
                    fixed_applied = b_fixed

                    bracket_pct_amount = round_inr(base_amount * (b_rate / Decimal("100.0")))
                    calculated_amount = round_inr(bracket_pct_amount + b_fixed)

                    max_str = (
                        f"₹{Decimal(str(matched_bracket.maximum_value)):,.0f}"
                        if matched_bracket.maximum_value is not None
                        else "Above"
                    )
                    min_str = f"₹{Decimal(str(matched_bracket.minimum_value)):,.0f}"
                    explanation = (
                        f"Tier bracket [{min_str} - {max_str}]: {b_rate}% on ₹{base_amount:,.2f}"
                    )
                else:
                    calculated_amount = Decimal("0.00")
                    explanation = f"No matching bracket found for value ₹{base_amount:,.2f}"

            # Method: FORMULA (e.g. MoRTH Bharat BH-Series)
            elif rule.calculation_method == "FORMULA":
                formula = rule.formula_definition or {}
                f_type = formula.get("type", "BH_SERIES")

                if f_type == "BH_SERIES":
                    # BH Series Formula: (ExShowroom * BaseRate * 1.25 * 2) / 15
                    if ex_showroom_price <= Decimal("1000000"):
                        b_rate = Decimal("8.0")
                    elif ex_showroom_price <= Decimal("2000000"):
                        b_rate = Decimal("10.0")
                    else:
                        b_rate = Decimal("12.0")

                    fuel_upper = variant.fuel_type.upper()
                    if "DIESEL" in fuel_upper:
                        b_rate += Decimal(str(formula.get("diesel_surcharge", 2.0)))
                    elif "ELECTRIC" in fuel_upper or "EV" in fuel_upper:
                        b_rate = max(
                            Decimal("0.0"), b_rate - Decimal(str(formula.get("ev_discount", 2.0)))
                        )

                    rate_applied = b_rate
                    total_15_yr = (ex_showroom_price * (b_rate / Decimal("100.0"))) * Decimal(
                        str(formula.get("factor", 1.25))
                    )
                    calculated_amount = round_inr(
                        (total_15_yr / Decimal("15.0"))
                        * Decimal(str(formula.get("payment_tenure_years", 2)))
                    )
                    explanation = f"MoRTH BH-Series initial 2-year tax cycle: ({b_rate}% of ₹{ex_showroom_price:,.2f} × 1.25 × 2) / 15"
                else:
                    calculated_amount = Decimal("0.00")
                    explanation = f"Evaluated custom formula definition '{f_type}'"

            # Store road tax for dependent Cess calculations
            if rule.tax_type in ["ROAD_TAX", "MOTOR_VEHICLE_TAX"]:
                road_tax_amount = calculated_amount

            calculated_tax_map[rule.tax_type] = calculated_amount

            # Check status
            status_val = "APPLIED"
            if calculated_amount == Decimal("0.00"):
                status_val = "ZERO_CHARGE"

            breakdown_items.append(
                PriceBreakdownItem(
                    component=rule.tax_type,
                    tax_rule_id=rule.rule_id,
                    rule_name=rule.name,
                    calculation_method=rule.calculation_method,
                    base_amount=base_amount,
                    rate=rate_applied,
                    fixed_amount=fixed_applied,
                    calculated_amount=calculated_amount,
                    source=rule.source_name,
                    source_url=rule.source_url,
                    effective_from=rule.effective_from,
                    effective_to=rule.effective_to,
                    explanation=explanation,
                    is_estimated=False,
                    status=status_val,
                )
            )

        # 5.3 Federal Tax Collected at Source (TCS) - Section 206C(1F)
        tcs_threshold = Decimal("1000000.00")
        if ex_showroom_price > tcs_threshold:
            tcs_amount = round_inr(ex_showroom_price * Decimal("0.01"))
            breakdown_items.append(
                PriceBreakdownItem(
                    component="TCS",
                    tax_rule_id=None,
                    rule_name="Tax Collected at Source (TCS Section 206C(1F))",
                    calculation_method="PERCENTAGE",
                    base_amount=ex_showroom_price,
                    rate=Decimal("1.00"),
                    fixed_amount=Decimal("0.00"),
                    calculated_amount=tcs_amount,
                    source="Income Tax Department of India",
                    source_url="https://incometaxindia.gov.in",
                    effective_from=datetime(2020, 10, 1, tzinfo=timezone.utc),
                    effective_to=None,
                    explanation="1.00% statutory TCS applicable on retail motor vehicle sales exceeding ₹10,00,000",
                    is_estimated=False,
                    status="APPLIED",
                )
            )

        # 5.4 Insurance Calculation
        ins_amount = Decimal("0.00")
        ins_option = request.insurance_option.upper()

        if ins_option == "USER_PROVIDED" and request.insurance_amount is not None:
            ins_amount = round_inr(request.insurance_amount)
            breakdown_items.append(
                PriceBreakdownItem(
                    component="INSURANCE",
                    rule_name="User-Provided Motor Insurance Quote",
                    calculation_method="USER_OVERRIDE",
                    base_amount=None,
                    rate=None,
                    fixed_amount=ins_amount,
                    calculated_amount=ins_amount,
                    source="User Input",
                    source_url=None,
                    explanation="Direct customized insurance amount provided by user",
                    is_estimated=False,
                    status="USER_OVERRIDDEN",
                )
            )
        else:
            include_zero_dep = ins_option in ["DEFAULT_ESTIMATE", "ZERO_DEP"]
            ins_res = InsuranceService.estimate_insurance(
                ex_showroom_price=ex_showroom_price,
                engine_cc=engine_cc,
                is_ev=is_ev,
                include_zero_dep=include_zero_dep,
            )
            ins_amount = round_inr(ins_res.total_insurance_premium)
            ins_plan_title = (
                "1-Yr Own Damage + 3-Yr Third Party + Zero Dep (18% GST)"
                if include_zero_dep
                else "1-Yr Own Damage + 3-Yr Third Party (18% GST)"
            )
            breakdown_items.append(
                PriceBreakdownItem(
                    component="INSURANCE",
                    rule_name=f"Comprehensive Motor Insurance ({ins_plan_title})",
                    calculation_method="ESTIMATE",
                    base_amount=ins_res.estimated_idv,
                    rate=None,
                    fixed_amount=ins_amount,
                    calculated_amount=ins_amount,
                    source="IRDAI Motor Tariff Board",
                    source_url="https://irdai.gov.in",
                    explanation=f"Estimated IDV (₹{ins_res.estimated_idv:,.2f}) with 3-Yr TP (₹{ins_res.third_party_3yr:,.2f}), 1-Yr OD, and 18% GST",
                    is_estimated=True,
                    status="APPLIED",
                )
            )

        # =========================================================================
        # 6. TOTALS COMPUTATION (SUM OF LINE ITEMS - ZERO FLOATING POINT DISCREPANCY)
        # =========================================================================
        total_taxes = Decimal("0.00")
        total_fees = Decimal("0.00")
        total_other = Decimal("0.00")

        tax_components = {"ROAD_TAX", "MOTOR_VEHICLE_TAX", "CESS", "SURCHARGE", "GREEN_TAX", "TCS"}
        fee_components = {
            "REGISTRATION_FEE",
            "SMART_CARD_FEE",
            "HSRP_FEE",
            "HYPOTHECATION_FEE",
            "FASTAG_FEE",
        }

        for item in breakdown_items:
            if item.component == "EX_SHOWROOM":
                continue
            elif item.component == "INSURANCE":
                continue
            elif item.component in tax_components:
                total_taxes += item.calculated_amount
            elif item.component in fee_components:
                total_fees += item.calculated_amount
            else:
                total_other += item.calculated_amount

        total_taxes = round_inr(total_taxes)
        total_fees = round_inr(total_fees)
        total_other = round_inr(total_other)

        on_road_price = round_inr(
            ex_showroom_price + total_taxes + total_fees + ins_amount + total_other
        )

        totals = OnRoadPriceTotals(
            ex_showroom_price=ex_showroom_price,
            total_statutory_taxes=total_taxes,
            total_registration_and_fees=total_fees,
            total_insurance=ins_amount,
            total_other_charges=total_other,
            on_road_price=on_road_price,
        )

        # =========================================================================
        # 7. DATA QUALITY & AUDIT PROVENANCE
        # =========================================================================
        sources_list: List[str] = []
        for item in breakdown_items:
            if item.source and item.source not in sources_list:
                sources_list.append(item.source)

        data_quality = DataQualityInfo(
            is_estimated=True,
            has_demo_rules=True,
            data_status="DEMO",
            sources=sources_list,
            disclaimer="Estimated on-road price computed using demonstration statutory tax & registration rules. Actual dealer invoices and RTO receipts may vary.",
        )

        return OnRoadPriceResponse(
            vehicle=vehicle_ctx,
            location=location_ctx,
            calculation_date=calc_date,
            is_bh_series=request.is_bh_series,
            is_financed=request.is_financed,
            insurance_option=request.insurance_option,
            breakdown=breakdown_items,
            totals=totals,
            data_quality=data_quality,
        )
