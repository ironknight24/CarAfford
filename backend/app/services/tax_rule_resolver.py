from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import City, RtoOffice, State
from app.models.tax_rule import TaxRule
from app.models.vehicle import Variant
from app.repositories.pricing_repo import PricingRepository
from app.repositories.tax_rule_repo import TaxRuleRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.tax_rule import (
    LocationResolutionContext,
    ResolvedTaxRuleItem,
    TaxRuleBracketRead,
    TaxRuleResolveResponse,
    VehicleResolutionContext,
)


class TaxRuleResolverService:
    """Pure domain service for deterministic, location-aware, temporal statutory tax and registration rule resolution."""

    @classmethod
    async def resolve_rules(
        cls,
        db: AsyncSession,
        state_id: int,
        city_id: Optional[int] = None,
        rto_id: Optional[int] = None,
        variant_id: Optional[int] = None,
        fuel_type: Optional[str] = None,
        engine_cc: Optional[int] = None,
        ex_showroom_price: Optional[Decimal] = None,
        is_ev: Optional[bool] = None,
        vehicle_type: str = "CAR",
        usage_type: str = "PRIVATE",
        calculation_date: Optional[datetime] = None,
        is_bh_series: bool = False,
        is_financed: bool = True,
    ) -> TaxRuleResolveResponse:
        calc_date = calculation_date or datetime.now(timezone.utc)
        if calc_date.tzinfo is None:
            calc_date = calc_date.replace(tzinfo=timezone.utc)

        # 1. Validate & fetch Location Hierarchy
        state = await db.get(State, state_id)
        if not state:
            raise ValueError(f"State with ID={state_id} not found.")

        city: Optional[City] = None
        if city_id is not None:
            city = await db.get(City, city_id)
            if not city:
                raise ValueError(f"City with ID={city_id} not found.")
            if city.state_id != state.id:
                raise ValueError(f"City '{city.name}' does not belong to State '{state.name}'.")

        rto: Optional[RtoOffice] = None
        if rto_id is not None:
            rto = await db.get(RtoOffice, rto_id)
            if not rto:
                raise ValueError(f"RTO with ID={rto_id} not found.")
            if rto.state_id != state.id:
                raise ValueError(f"RTO '{rto.code}' does not belong to State '{state.name}'.")

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

        # 2. Resolve Vehicle Attributes
        v_name = None
        m_name = None
        mfg_name = None
        v_fuel = fuel_type or "Petrol"
        v_cc = engine_cc
        v_price = ex_showroom_price or Decimal("1000000.00")
        v_is_ev = is_ev if is_ev is not None else False

        if variant_id is not None:
            vehicle_repo = VehicleRepository(db)
            variant = await vehicle_repo.get_variant_by_id(variant_id)
            if not variant:
                raise ValueError(f"Vehicle variant with ID={variant_id} not found.")
            v_name = variant.name
            m_name = variant.model.name if variant.model else None
            mfg_name = (
                variant.model.manufacturer.name
                if variant.model and variant.model.manufacturer
                else None
            )
            v_fuel = variant.fuel_type
            v_cc = variant.engine_cc
            v_is_ev = (
                variant.fuel_type.upper() in ["ELECTRIC", "EV"]
                or variant.battery_capacity_kwh is not None
            )
            if is_ev is not None:
                v_is_ev = is_ev

            # Get active price for calculation date
            if ex_showroom_price is None:
                active_price = await vehicle_repo.get_current_price(
                    variant.id, as_of_date=calc_date
                )
                if active_price:
                    v_price = active_price.ex_showroom_price

        vehicle_ctx = VehicleResolutionContext(
            variant_id=variant_id,
            variant_name=v_name,
            model_name=m_name,
            manufacturer_name=mfg_name,
            fuel_type=v_fuel,
            engine_cc=v_cc,
            ex_showroom_price=v_price,
            is_ev=v_is_ev,
            vehicle_type=vehicle_type,
            usage_type=usage_type,
        )

        # 3. Retrieve Candidate Active Rules
        candidates = await TaxRuleRepository.get_candidate_rules_for_resolution(
            db=db,
            state_id=state.id,
            city_id=city.id if city else None,
            rto_id=rto.id if rto else None,
            calculation_date=calc_date,
        )

        # 4. Filter, Match & Score Candidates
        matched_by_tax_type: Dict[str, List[Tuple[int, TaxRule, int, str]]] = {}

        for rule in candidates:
            # Check vehicle type
            if rule.vehicle_type not in ["ANY", vehicle_type.upper()]:
                continue

            # Check usage type
            if rule.usage_type not in ["ANY", usage_type.upper()]:
                continue

            # Check EV condition
            if rule.is_ev is not None and rule.is_ev != v_is_ev:
                continue

            # Check Fuel condition
            if rule.fuel_type and rule.fuel_type.upper() != "ANY":
                if (
                    rule.fuel_type.upper() not in v_fuel.upper()
                    and v_fuel.upper() not in rule.fuel_type.upper()
                ):
                    continue

            # Check Price bounds
            if rule.min_price is not None and v_price < rule.min_price:
                continue
            if rule.max_price is not None and v_price > rule.max_price:
                continue

            # Check Engine CC bounds
            if v_cc is not None:
                if rule.min_engine_cc is not None and v_cc < rule.min_engine_cc:
                    continue
                if rule.max_engine_cc is not None and v_cc > rule.max_engine_cc:
                    continue

            # Check Hypothecation finance condition
            if rule.tax_type == "HYPOTHECATION_FEE" and not is_financed:
                continue

            # Check BH Series condition
            is_bh_rule = (
                rule.formula_definition is not None
                and isinstance(rule.formula_definition, dict)
                and rule.formula_definition.get("type") == "BH_SERIES"
            )
            if is_bh_series and not is_bh_rule and rule.tax_type == "ROAD_TAX":
                continue
            if not is_bh_series and is_bh_rule:
                continue

            # Calculate Precedence Tier and Specificity Score
            tier = 100
            tier_label = "State-level"
            if rule.rto_id is not None and rto and rule.rto_id == rto.id:
                tier = 300
                tier_label = "RTO-specific"
            elif rule.city_id is not None and city and rule.city_id == city.id:
                tier = 200
                tier_label = "City-specific"

            score = tier
            # Fuel specificity bonus
            if rule.fuel_type and rule.fuel_type.upper() != "ANY":
                score += 50
            # EV specificity bonus
            if rule.is_ev is not None:
                score += 30
            # CC/Price specificity bonus
            if rule.min_engine_cc is not None or rule.max_engine_cc is not None:
                score += 20
            if rule.min_price is not None or rule.max_price is not None:
                score += 20
            # Explicit priority
            score += rule.priority

            tax_type_key = rule.tax_type.upper()
            if tax_type_key not in matched_by_tax_type:
                matched_by_tax_type[tax_type_key] = []
            matched_by_tax_type[tax_type_key].append((score, rule, tier, tier_label))

        # 5. Deterministic Selection of Best Rule per Tax Type
        resolved_items: List[ResolvedTaxRuleItem] = []

        # Canonical display order
        preferred_tax_type_order = [
            "ROAD_TAX",
            "MOTOR_VEHICLE_TAX",
            "CESS",
            "SURCHARGE",
            "GREEN_TAX",
            "REGISTRATION_FEE",
            "SMART_CARD_FEE",
            "HSRP_FEE",
            "HYPOTHECATION_FEE",
            "FASTAG_FEE",
            "OTHER",
        ]

        ordered_tax_types = sorted(
            matched_by_tax_type.keys(),
            key=lambda t: (
                preferred_tax_type_order.index(t) if t in preferred_tax_type_order else 99
            ),
        )

        for t_type in ordered_tax_types:
            candidates_list = matched_by_tax_type[t_type]
            # Sort by total score descending, then rule.id ascending for stability
            candidates_list.sort(key=lambda item: (item[0], item[1].priority), reverse=True)
            best_score, best_rule, tier, tier_label = candidates_list[0]

            brackets_dto = [TaxRuleBracketRead.model_validate(b) for b in best_rule.brackets]

            resolved_items.append(
                ResolvedTaxRuleItem(
                    rule_id=best_rule.id,
                    name=best_rule.name,
                    description=best_rule.description,
                    rule_category=best_rule.rule_category,
                    tax_type=best_rule.tax_type,
                    calculation_method=best_rule.calculation_method,
                    rate=best_rule.rate,
                    fixed_amount=best_rule.fixed_amount,
                    base_amount_type=best_rule.base_amount_type,
                    brackets=brackets_dto,
                    formula_definition=best_rule.formula_definition,
                    priority=best_rule.priority,
                    precedence_tier=tier,
                    precedence_label=tier_label,
                    effective_from=best_rule.effective_from,
                    effective_to=best_rule.effective_to,
                    source_name=best_rule.source.name if best_rule.source else None,
                    source_url=best_rule.source.base_url if best_rule.source else None,
                    source_record_id=best_rule.source_record_id,
                    retrieved_at=best_rule.retrieved_at,
                    verification_status=best_rule.verification_status,
                )
            )

        return TaxRuleResolveResponse(
            location=location_ctx,
            vehicle=vehicle_ctx,
            calculation_date=calc_date,
            is_bh_series=is_bh_series,
            is_financed=is_financed,
            rules=resolved_items,
            rules_count=len(resolved_items),
        )
