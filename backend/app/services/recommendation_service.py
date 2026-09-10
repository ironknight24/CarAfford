from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.affordability_constants import AffordabilityProfile, AffordabilityStatus
from app.core.recommendation_constants import (
    CATEGORY_DESCRIPTIONS,
    DATA_STATUS_DEMO,
    DEFAULT_RECOMMENDATION_LIMIT,
    DEFAULT_SCORING_WEIGHTS,
    MAX_RECOMMENDATION_LIMIT,
    MIN_RECOMMENDATION_LIMIT,
    RECOMMENDATION_DISCLAIMER,
    RecommendationCategory,
    ScoringWeights,
)
from app.models.location import State
from app.models.vehicle import CarModel, Manufacturer, Variant, VariantSpecification
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.affordability import (
    AffordabilityCalculateRequest,
    AffordabilityCategory,
    OwnershipCostBreakdown,
    VehicleAffordabilityRequest,
)
from app.schemas.pricing import OnRoadPriceBreakdown
from app.schemas.recommendation import (
    QuickRecommendationRequest,
    RecommendationAffordabilitySummary,
    RecommendationCompareRequest,
    RecommendationCompareResponse,
    RecommendationFinancingOption,
    RecommendationRequest,
    RecommendationResponse,
    RecommendationTCOSummary,
    RecommendationVehicleSummary,
    RecommendedVehicleItem,
    ScoringConfigResponse,
)
from app.schemas.tco import TCOCalculationRequest
from app.services.affordability_service import AffordabilityService
from app.services.tco_service import TCOService


def round_inr(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def round_score(score: Decimal) -> Decimal:
    return score.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


class RecommendationService:
    """Pure domain recommendation engine for CarAfford.

    Orchestrates:
    - Vehicle Catalogue & Candidate Filtering
    - Affordability Engine (On-Road Price & Banking Eligibility)
    - Total Cost of Ownership (TCO) Engine
    - Multi-dimensional Weighted Scoring & Transparent Categorization
    """

    @classmethod
    def get_scoring_config(cls) -> ScoringConfigResponse:
        """Returns the active scoring model weights, category definitions, and limits."""
        return ScoringConfigResponse(
            weights=DEFAULT_SCORING_WEIGHTS,
            categories=CATEGORY_DESCRIPTIONS,
            default_limit=DEFAULT_RECOMMENDATION_LIMIT,
            max_limit=MAX_RECOMMENDATION_LIMIT,
            data_status=DATA_STATUS_DEMO,
            disclaimer=RECOMMENDATION_DISCLAIMER,
        )

    @classmethod
    async def get_car_recommendations(
        cls,
        db: AsyncSession,
        request: RecommendationRequest,
    ) -> RecommendationResponse:
        """Evaluates vehicle catalogue candidates against user financial profile, location, and preferences."""
        calc_date = request.calculation_date or datetime.now(timezone.utc)
        if calc_date.tzinfo is None:
            calc_date = calc_date.replace(tzinfo=timezone.utc)

        # 1. Location hierarchy check
        state, city, rto = await AffordabilityService.validate_location_hierarchy(
            db, request.state_id, request.city_id, request.rto_id
        )

        # 2. Compute user overall financial budget & capacity
        afford_req = AffordabilityCalculateRequest(
            monthly_take_home_income=request.monthly_take_home_income,
            existing_monthly_emi=request.existing_monthly_emi,
            available_down_payment=request.available_down_payment,
            state_id=state.id,
            city_id=city.id if city else None,
            rto_id=rto.id if rto else None,
            credit_score=request.credit_score or 750,
            preferred_loan_tenure_months=request.preferred_loan_tenure_months or 60,
            affordability_profile=request.affordability_profile or AffordabilityProfile.BALANCED,
            calculation_date=calc_date,
        )
        budget_summary = await AffordabilityService.calculate_capacity(db, afford_req)

        # 3. Retrieve and filter candidate vehicles from catalogue
        query = (
            select(Variant)
            .join(CarModel, Variant.model_id == CarModel.id)
            .join(Manufacturer, CarModel.manufacturer_id == Manufacturer.id)
            .options(
                selectinload(Variant.model).selectinload(CarModel.manufacturer),
                selectinload(Variant.specification),
            )
            .where(Variant.active == True)
        )

        if request.manufacturer_id is not None:
            query = query.where(CarModel.manufacturer_id == request.manufacturer_id)
        if request.fuel_preference:
            norm_fuel = request.fuel_preference.strip().upper()
            if norm_fuel in ["EV", "ELECTRIC"]:
                query = query.where(Variant.fuel_type.in_(["Electric", "EV"]))
            else:
                query = query.where(Variant.fuel_type.ilike(f"%{norm_fuel}%"))
        if request.body_type:
            query = query.where(CarModel.body_type.ilike(f"%{request.body_type.strip()}%"))
        if request.transmission:
            query = query.where(Variant.transmission.ilike(f"%{request.transmission.strip()}%"))
        if request.automatic_required is True:
            query = query.where(
                (Variant.transmission.in_(["Automatic", "AMT", "CVT", "DCT", "AT"]))
                | (Variant.fuel_type.in_(["Electric", "EV"]))
            )
        if request.seating_capacity is not None:
            query = query.where(Variant.seating_capacity >= request.seating_capacity)
        if request.variant_ids:
            query = query.where(Variant.id.in_(request.variant_ids))

        res = await db.execute(query)
        candidates: List[Variant] = list(res.scalars().all())
        total_candidates = len(candidates)

        # 4. Evaluate Affordability & TCO for candidate variants
        affordable_items: List[Dict[str, Any]] = []
        stretch_items: List[Dict[str, Any]] = []
        excluded_count = 0

        annual_dist = request.annual_driving_distance_km or Decimal("12000.00")
        monthly_dist = request.monthly_driving_distance_km or Decimal("1000.00")

        for variant in candidates:
            # Evaluate Affordability via existing Domain 7 Affordability Engine
            try:
                veh_afford_req = VehicleAffordabilityRequest(
                    variant_id=variant.id,
                    monthly_take_home_income=request.monthly_take_home_income,
                    existing_monthly_emi=request.existing_monthly_emi,
                    available_down_payment=request.available_down_payment,
                    state_id=state.id,
                    city_id=city.id if city else None,
                    rto_id=rto.id if rto else None,
                    credit_score=request.credit_score or 750,
                    preferred_loan_tenure_months=request.preferred_loan_tenure_months or 60,
                    affordability_profile=request.affordability_profile
                    or AffordabilityProfile.BALANCED,
                    calculation_date=calc_date,
                )
                afford_eval = await AffordabilityService.evaluate_vehicle_affordability(
                    db=db,
                    request=veh_afford_req,
                )
            except Exception:
                excluded_count += 1
                continue

            # Price bounds filter if user specified
            if (
                request.minimum_price is not None
                and afford_eval.on_road_price < request.minimum_price
            ):
                excluded_count += 1
                continue
            if (
                request.maximum_price is not None
                and afford_eval.on_road_price > request.maximum_price
            ):
                excluded_count += 1
                continue

            # Safety rating filter if user specified
            spec = variant.specification
            safety_stars = spec.safety_rating_stars if spec and spec.safety_rating_stars else 3
            if (
                request.minimum_safety_rating is not None
                and safety_stars < request.minimum_safety_rating
            ):
                excluded_count += 1
                continue

            # Exclude non-viable options
            if (
                afford_eval.affordability_status
                in [
                    AffordabilityStatus.NOT_AFFORDABLE,
                    AffordabilityStatus.NO_FINANCING_OPTION,
                ]
                or not afford_eval.affordable
            ):
                excluded_count += 1
                continue

            # Evaluate TCO via existing Domain 8 TCO Engine
            try:
                tco_req = TCOCalculationRequest(
                    variant_id=variant.id,
                    state_id=state.id,
                    city_id=city.id if city else None,
                    rto_id=rto.id if rto else None,
                    annual_driving_distance_km=annual_dist,
                    down_payment=afford_eval.down_payment,
                    credit_score=request.credit_score or 750,
                    preferred_loan_tenure_months=request.preferred_loan_tenure_months or 60,
                    is_financed=True,
                    calculation_date=calc_date,
                )
                tco_eval = await TCOService.calculate_tco(db, tco_req)
            except Exception:
                excluded_count += 1
                continue

            item_data = {
                "variant": variant,
                "affordability": afford_eval,
                "tco": tco_eval,
                "spec": spec,
                "safety_stars": safety_stars,
                "airbags": spec.airbags_count if spec else 6,
                "arai_mileage": variant.arai_mileage_kmpl,
            }

            if afford_eval.affordability_status == AffordabilityStatus.STRETCH:
                stretch_items.append(item_data)
            else:
                affordable_items.append(item_data)

        # 5. Score Candidates
        scored_affordable = cls._score_candidate_pool(affordable_items, request, budget_summary)
        scored_stretch = cls._score_candidate_pool(stretch_items, request, budget_summary)

        # 6. Categorize and Rank Top Recommendations
        limit = min(
            MAX_RECOMMENDATION_LIMIT,
            max(MIN_RECOMMENDATION_LIMIT, request.limit or DEFAULT_RECOMMENDATION_LIMIT),
        )
        recommendations = cls._build_recommended_items(
            scored_affordable[:limit],
            is_stretch=False,
            monthly_income=request.monthly_take_home_income,
        )
        stretch_recommendations = cls._build_recommended_items(
            scored_stretch[:limit], is_stretch=True, monthly_income=request.monthly_take_home_income
        )

        return RecommendationResponse(
            user_budget_summary=budget_summary,
            recommendations=recommendations,
            stretch_options=stretch_recommendations,
            total_candidates_evaluated=total_candidates,
            total_affordable_count=len(affordable_items),
            total_stretch_count=len(stretch_items),
            total_excluded_count=excluded_count,
            returned_count=len(recommendations),
            data_status=DATA_STATUS_DEMO,
            disclaimer=RECOMMENDATION_DISCLAIMER,
        )

    @classmethod
    async def get_quick_recommendations(
        cls,
        db: AsyncSession,
        request: QuickRecommendationRequest,
    ) -> RecommendationResponse:
        """Simplified recommendation workflow using minimal user financial parameters."""
        rec_req = RecommendationRequest(
            monthly_take_home_income=request.monthly_take_home_income,
            existing_monthly_emi=request.existing_monthly_emi,
            available_down_payment=request.available_down_payment,
            state_id=request.state_id,
            city_id=request.city_id,
            credit_score=request.credit_score,
            limit=request.limit,
        )
        return await cls.get_car_recommendations(db, rec_req)

    @classmethod
    async def compare_recommendations(
        cls,
        db: AsyncSession,
        request: RecommendationCompareRequest,
    ) -> RecommendationCompareResponse:
        """Compares and ranks explicitly chosen vehicles using the recommendation scoring model."""
        rec_req = RecommendationRequest(
            monthly_take_home_income=request.monthly_take_home_income,
            existing_monthly_emi=request.existing_monthly_emi,
            available_down_payment=request.available_down_payment,
            state_id=request.state_id,
            city_id=request.city_id,
            rto_id=request.rto_id,
            credit_score=request.credit_score,
            preferred_loan_tenure_months=request.preferred_loan_tenure_months,
            affordability_profile=request.affordability_profile,
            annual_driving_distance_km=request.annual_driving_distance_km,
            variant_ids=request.variant_ids,
            limit=len(request.variant_ids),
        )

        res = await cls.get_car_recommendations(db, rec_req)
        # Filter strictly to requested variant IDs
        target_ids = set(request.variant_ids)
        all_recs = [r for r in res.recommendations if r.variant_id in target_ids]
        all_recs.extend([r for r in res.stretch_options if r.variant_id in target_ids])
        all_recs.sort(key=lambda x: x.score, reverse=True)

        summary_notes = [
            f"Compared {len(all_recs)} vehicle variants against your monthly income of ₹{request.monthly_take_home_income:,.2f}.",
            (
                f"Rank #1: {all_recs[0].variant_name} with overall score {all_recs[0].score}/100."
                if all_recs
                else "No vehicles matched your criteria."
            ),
        ]

        return RecommendationCompareResponse(
            user_budget_summary=res.user_budget_summary,
            ranked_vehicles=all_recs,
            scoring_weights=DEFAULT_SCORING_WEIGHTS,
            comparison_summary=summary_notes,
            data_status=DATA_STATUS_DEMO,
            disclaimer=RECOMMENDATION_DISCLAIMER,
        )

    # =========================================================================
    # SCORING & CATEGORIZATION LOGIC
    # =========================================================================

    @classmethod
    def _score_candidate_pool(
        cls,
        candidates: List[Dict[str, Any]],
        request: RecommendationRequest,
        budget: Any,
    ) -> List[Dict[str, Any]]:
        """Applies transparent weighted multi-dimensional scoring across all candidate vehicles."""
        if not candidates:
            return []

        # Extract range boundaries for relative normalization
        tco_5yr_values = [float(c["tco"].periods["5_years"].total_cash_outflow) for c in candidates]
        min_tco = min(tco_5yr_values)
        max_tco = max(tco_5yr_values)

        monthly_burdens = [
            float(
                c["affordability"].estimated_emi
                + c["tco"].operating_costs.annual_fuel_cost / Decimal("12.0")
            )
            for c in candidates
        ]
        min_monthly = min(monthly_burdens)
        max_monthly = max(monthly_burdens)

        avail_car_emi = (
            float(budget.available_car_emi) if float(budget.available_car_emi) > 0 else 1.0
        )

        for idx, item in enumerate(candidates):
            afford = item["affordability"]
            tco = item["tco"]
            variant = item["variant"]
            spec = item["spec"]

            # 1. Affordability Dimension (30%)
            # COMFORTABLE -> 100 base, AFFORDABLE -> 80 base, STRETCH -> 50 base
            base_afford = (
                100.0
                if afford.affordability_status == AffordabilityStatus.COMFORTABLE
                else (
                    80.0 if afford.affordability_status == AffordabilityStatus.AFFORDABLE else 50.0
                )
            )
            headroom_ratio = max(0.0, min(1.0, float(afford.emi_headroom) / avail_car_emi))
            afford_score = round(0.70 * base_afford + 0.30 * (base_afford * headroom_ratio))

            # 2. TCO Dimension (25%)
            cur_tco = float(tco.periods["5_years"].total_cash_outflow)
            if max_tco == min_tco:
                tco_score = 100.0
            else:
                tco_score = 100.0 - ((cur_tco - min_tco) / (max_tco - min_tco) * 100.0)
            tco_score = round(max(0.0, min(100.0, tco_score)))

            # 3. Preference Match Dimension (20%)
            pref_points = 0
            # Fuel (30 pts)
            if not request.fuel_preference:
                pref_points += 30
            elif request.fuel_preference.strip().upper() in variant.fuel_type.upper():
                pref_points += 30
            # Transmission (25 pts)
            if not request.transmission and request.automatic_required is None:
                pref_points += 25
            elif request.automatic_required and variant.transmission.upper() in [
                "AUTOMATIC",
                "AMT",
                "CVT",
                "DCT",
                "AT",
            ]:
                pref_points += 25
            elif (
                request.transmission
                and request.transmission.strip().upper() in variant.transmission.upper()
            ):
                pref_points += 25
            # Body Type (25 pts)
            if not request.body_type:
                pref_points += 25
            elif request.body_type.strip().upper() in variant.model.body_type.upper():
                pref_points += 25
            # Seating (20 pts)
            if not request.seating_capacity:
                pref_points += 20
            elif variant.seating_capacity >= request.seating_capacity:
                pref_points += 20

            pref_score = pref_points  # Max 100

            # 4. Monthly Burden Dimension (15%)
            cur_monthly = float(
                afford.estimated_emi + tco.operating_costs.annual_fuel_cost / Decimal("12.0")
            )
            if max_monthly == min_monthly:
                monthly_score = 100.0
            else:
                monthly_score = 100.0 - (
                    (cur_monthly - min_monthly) / (max_monthly - min_monthly) * 100.0
                )
            monthly_score = round(max(0.0, min(100.0, monthly_score)))

            # 5. Vehicle Value & Safety Dimension (10%)
            val_points = 0.0
            val_points += min(50.0, float(item["safety_stars"]) * 10.0)  # Max 50
            val_points += min(25.0, float(item["airbags"]) * 4.0)  # Max 25
            val_points += min(25.0, float(item["arai_mileage"]) * 1.0)  # Max 25
            val_score = round(val_points)

            # Composite Score calculation
            weights = DEFAULT_SCORING_WEIGHTS
            composite = (
                Decimal(str(afford_score)) * weights.affordability_weight
                + Decimal(str(tco_score)) * weights.tco_weight
                + Decimal(str(pref_score)) * weights.preference_match_weight
                + Decimal(str(monthly_score)) * weights.monthly_cost_weight
                + Decimal(str(val_score)) * weights.vehicle_value_weight
            )

            item["scores"] = {
                "affordability_score": int(afford_score),
                "tco_score": int(tco_score),
                "preference_match_score": int(pref_score),
                "monthly_cost_score": int(monthly_score),
                "vehicle_value_score": int(val_score),
                "composite_score": round_score(composite),
            }

        # Sort descending by composite score
        candidates.sort(key=lambda x: x["scores"]["composite_score"], reverse=True)
        return candidates

    @classmethod
    def _build_recommended_items(
        cls,
        candidates: List[Dict[str, Any]],
        is_stretch: bool = False,
        monthly_income: Optional[Decimal] = None,
    ) -> List[RecommendedVehicleItem]:
        """Assembles fully structured and explained recommendation items with categories and reasons."""
        results: List[RecommendedVehicleItem] = []
        if not candidates:
            return results

        # Find category leaders among top candidates
        best_tco_idx = min(
            range(len(candidates)),
            key=lambda i: float(candidates[i]["tco"].periods["5_years"].total_cash_outflow),
        )
        best_emi_idx = min(
            range(len(candidates)),
            key=lambda i: float(candidates[i]["affordability"].estimated_emi),
        )
        best_fit_idx = max(
            range(len(candidates)),
            key=lambda i: candidates[i]["scores"]["preference_match_score"],
        )

        for rank, item in enumerate(candidates, start=1):
            variant: Variant = item["variant"]
            model: CarModel = variant.model
            mfg: Manufacturer = model.manufacturer
            afford = item["affordability"]
            tco = item["tco"]
            spec = item["spec"]
            scores = item["scores"]

            # Assign smart category
            if is_stretch:
                category = RecommendationCategory.STRETCH_OPTIONS.value
            elif rank == 1:
                category = RecommendationCategory.BEST_OVERALL.value
            elif rank == 2 or (
                rank <= 3 and float(afford.emi_headroom) > float(afford.available_car_emi) * 0.25
            ):
                category = RecommendationCategory.BEST_VALUE.value
            elif rank - 1 == best_tco_idx:
                category = RecommendationCategory.LOWEST_5_YEAR_TCO.value
            elif rank - 1 == best_emi_idx:
                category = RecommendationCategory.LOWEST_MONTHLY_COST.value
            elif rank - 1 == best_fit_idx:
                category = RecommendationCategory.BEST_FIT.value
            else:
                category = RecommendationCategory.BEST_VALUE.value

            # Build transparent reasons
            reasons: List[str] = []
            if float(afford.emi_headroom) > 0:
                reasons.append(
                    f"Comfortably within budget with ₹{afford.emi_headroom:,.2f}/mo EMI headroom."
                )
            else:
                reasons.append("Fits precisely within your monthly car EMI allocation.")

            five_yr_tco = tco.periods["5_years"].total_cash_outflow
            reasons.append(
                f"Estimated 5-year ownership cost is ₹{five_yr_tco:,.2f} (₹{tco.periods['5_years'].average_monthly_cost:,.2f}/mo all-inclusive)."
            )

            if item["safety_stars"] >= 4:
                reasons.append(
                    f"{item['safety_stars']}-Star Safety rating with {item['airbags']} airbags standard."
                )
            if variant.arai_mileage_kmpl:
                reasons.append(
                    f"Fuel efficient: {variant.arai_mileage_kmpl} km/l claimed efficiency."
                )

            warnings: List[str] = [
                "Fuel prices, insurance renewals, and bank loan rates are calculated using demo baseline data.",
            ]
            if is_stretch:
                warnings.append(
                    "This vehicle utilizes your stretch budget capacity; consider conservative financing."
                )

            # Best loan offer
            fin_opt: Optional[RecommendationFinancingOption] = None
            if afford.selected_loan_offer:
                top_offer = afford.selected_loan_offer
                fin_opt = RecommendationFinancingOption(
                    bank_name=top_offer.bank_name,
                    product_name=top_offer.product_name,
                    interest_rate=top_offer.annual_interest_rate,
                    tenure_months=top_offer.tenure_months,
                    monthly_emi=top_offer.monthly_emi,
                    processing_fee=getattr(
                        top_offer,
                        "total_fees",
                        getattr(top_offer, "processing_fee", Decimal("0.00")),
                    ),
                    total_interest=top_offer.total_interest,
                )
            elif afford.all_eligible_loan_offers and len(afford.all_eligible_loan_offers) > 0:
                top_offer = afford.all_eligible_loan_offers[0]
                fin_opt = RecommendationFinancingOption(
                    bank_name=top_offer.bank_name,
                    product_name=top_offer.product_name,
                    interest_rate=top_offer.annual_interest_rate,
                    tenure_months=top_offer.tenure_months,
                    monthly_emi=top_offer.monthly_emi,
                    processing_fee=getattr(
                        top_offer,
                        "total_fees",
                        getattr(top_offer, "processing_fee", Decimal("0.00")),
                    ),
                    total_interest=top_offer.total_interest,
                )

            # Ownership cost breakdown for backward compatibility
            p5 = tco.periods["5_years"]
            m_emi = afford.estimated_emi
            m_fuel = round_inr(tco.operating_costs.annual_fuel_cost / Decimal("12.0"))
            m_ins = round_inr(tco.operating_costs.annual_insurance_cost / Decimal("12.0"))
            m_maint = round_inr(tco.operating_costs.annual_maintenance_cost / Decimal("12.0"))
            m_tco = p5.average_monthly_cost
            tco_pct = (
                round_inr((m_tco / monthly_income) * Decimal("100.0"))
                if monthly_income and monthly_income > 0
                else Decimal("0.00")
            )
            legacy_ownership_cost = OwnershipCostBreakdown(
                monthly_emi=m_emi,
                monthly_fuel_cost=m_fuel,
                monthly_insurance_cost=m_ins,
                monthly_maintenance_cost=m_maint,
                total_monthly_tco=m_tco,
                tco_percentage_of_income=tco_pct,
            )

            rec_item = RecommendedVehicleItem(
                category=category,
                rank=rank,
                score=scores["composite_score"],
                variant_id=variant.id,
                vehicle=RecommendationVehicleSummary(
                    variant_id=variant.id,
                    variant_name=variant.name,
                    model_name=model.name,
                    model_slug=model.slug,
                    manufacturer_name=mfg.name,
                    manufacturer_slug=mfg.slug,
                    body_type=model.body_type,
                    fuel_type=variant.fuel_type,
                    transmission=variant.transmission,
                    seating_capacity=variant.seating_capacity,
                    image_url=model.image_url,
                    arai_mileage_kmpl=variant.arai_mileage_kmpl,
                    safety_rating_stars=item["safety_stars"],
                    airbags_count=item["airbags"],
                    ex_showroom_price=tco.initial_cost.ex_showroom_price,
                    on_road_price=afford.on_road_price,
                ),
                affordability=RecommendationAffordabilitySummary(
                    status=(
                        afford.affordability_status.value
                        if hasattr(afford.affordability_status, "value")
                        else str(afford.affordability_status)
                    ),
                    available_car_emi=afford.available_car_emi,
                    estimated_emi=afford.estimated_emi,
                    emi_headroom=afford.emi_headroom,
                    loan_amount=afford.required_loan,
                    down_payment=afford.down_payment,
                    affordability_score=scores["affordability_score"],
                ),
                financing=fin_opt,
                tco=RecommendationTCOSummary(
                    annual_fuel_cost=tco.operating_costs.annual_fuel_cost,
                    annual_maintenance_cost=tco.operating_costs.annual_maintenance_cost,
                    five_year_tco=p5.total_cash_outflow,
                    five_year_monthly_average=p5.average_monthly_cost,
                    tco_score=scores["tco_score"],
                ),
                preference_match_score=scores["preference_match_score"],
                reasons=reasons,
                warnings=warnings,
                # Backward-compatibility fields
                variant_name=variant.name,
                model_name=model.name,
                model_slug=model.slug,
                manufacturer_name=mfg.name,
                manufacturer_slug=mfg.slug,
                body_type=model.body_type,
                fuel_type=variant.fuel_type,
                transmission=variant.transmission,
                seating_capacity=variant.seating_capacity,
                image_url=model.image_url,
                arai_mileage_kmpl=variant.arai_mileage_kmpl,
                safety_rating_stars=item["safety_stars"],
                airbags_count=item["airbags"],
                ex_showroom_price=tco.initial_cost.ex_showroom_price,
                on_road_price=afford.on_road_price,
                down_payment_required=afford.down_payment,
                loan_amount=afford.required_loan,
                estimated_monthly_emi=afford.estimated_emi,
                interest_rate=fin_opt.interest_rate if fin_opt else Decimal("8.75"),
                tenure_months=fin_opt.tenure_months if fin_opt else 60,
                ownership_cost=legacy_ownership_cost,
                affordability_score=scores["affordability_score"],
                affordability_category=(
                    AffordabilityCategory.COMFORTABLE
                    if afford.affordability_status == AffordabilityStatus.COMFORTABLE
                    else (
                        AffordabilityCategory.MODERATE
                        if afford.affordability_status == AffordabilityStatus.AFFORDABLE
                        else AffordabilityCategory.STRETCH
                    )
                ),
                affordability_rationale=afford.affordability_rationale,
                on_road_breakdown=None,
            )
            results.append(rec_item)

        return results
