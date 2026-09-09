from decimal import Decimal
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.location import State
from app.repositories.location_repo import LocationRepository
from app.repositories.pricing_repo import PricingRepository
from app.repositories.vehicle_repo import VehicleRepository
from app.schemas.affordability import (
    AffordabilityAnalysisRequest,
    AffordabilityBudgetSummary,
    AffordabilityCategory,
)
from app.schemas.pricing import OnRoadPriceRequest
from app.schemas.recommendation import (
    RecommendationResponse,
    RecommendedVehicleItem,
)
from app.schemas.vehicle import VehicleFilterParams
from app.services.affordability_engine import AffordabilityEngine
from app.services.finance_service import FinanceService
from app.services.pricing_service import PricingService


class RecommendationEngine:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.vehicle_repo = VehicleRepository(session)
        self.location_repo = LocationRepository(session)
        self.pricing_service = PricingService(session)

    async def get_car_recommendations(
        self,
        request: AffordabilityAnalysisRequest,
    ) -> RecommendationResponse:
        # 1. Compute user budget capacity
        cibil = request.cibil_score or 750
        commute_km = request.monthly_commute_km or 1000
        tenure = request.desired_tenure_months

        budget_summary: AffordabilityBudgetSummary = AffordabilityEngine.calculate_budget_summary(
            monthly_take_home_income=request.monthly_take_home_income,
            existing_monthly_emis=request.existing_monthly_emis,
            available_down_payment=request.available_down_payment,
            desired_tenure_months=tenure,
            cibil_score=cibil,
        )

        # 2. Query candidate vehicles
        all_variants, _ = await self.vehicle_repo.get_variants(page=1, page_size=100, active=True)

        recommended_items: List[RecommendedVehicleItem] = []

        # 3. Evaluate each variant for on-road pricing and TCO
        for variant in all_variants:
            # Apply user categorical preferences if specified
            if request.preferred_body_types and variant.model.body_type not in request.preferred_body_types:
                continue
            if request.preferred_fuel_types and variant.fuel_type not in request.preferred_fuel_types:
                continue
            if request.preferred_transmission and variant.transmission not in request.preferred_transmission:
                continue

            try:
                on_road_req = OnRoadPriceRequest(
                    variant_id=variant.id,
                    state_id=request.state_id,
                    city_id=request.city_id,
                )
                on_road_breakdown = await self.pricing_service.calculate_on_road_price(on_road_req)
            except Exception:
                continue

            on_road_price = on_road_breakdown.on_road_price

            # Exclude vehicles that are excessively beyond max budget (>115% of max budget)
            if on_road_price > (budget_summary.max_affordable_on_road_price * Decimal("1.15")):
                continue

            # Down payment logic:
            # User uses available down payment up to on-road price, minimum 10% down payment required by banks
            min_dp = on_road_price * Decimal("0.10")
            user_dp = max(min_dp, min(request.available_down_payment, on_road_price * Decimal("0.80")))
            loan_required = max(Decimal("0.00"), on_road_price - user_dp)

            # EMI for this vehicle
            if loan_required > 0:
                emi = FinanceService.calculate_emi(
                    principal=loan_required,
                    annual_interest_rate=budget_summary.estimated_interest_rate,
                    tenure_months=tenure,
                )
            else:
                emi = Decimal("0.00")

            # Technical spec fallbacks
            spec = variant.specification
            mileage = spec.arai_mileage_kmpl if (spec and spec.arai_mileage_kmpl) else (variant.mileage_claimed or Decimal("18.00"))
            safety = spec.safety_rating_stars if spec else 5
            airbags = spec.airbags_count if spec else 6

            # TCO calculation
            tco_breakdown = AffordabilityEngine.calculate_ownership_breakdown(
                monthly_emi=emi,
                annual_insurance_estimate=on_road_breakdown.insurance_total,
                ex_showroom_price=on_road_breakdown.ex_showroom_price,
                monthly_commute_km=commute_km,
                fuel_type=variant.fuel_type,
                arai_mileage_kmpl=mileage,
                monthly_income=request.monthly_take_home_income,
            )

            score, category, rationale = AffordabilityEngine.score_affordability(
                tco=tco_breakdown,
                monthly_income=request.monthly_take_home_income,
                existing_emis=request.existing_monthly_emis,
            )

            # Safety bonus to score
            final_score = score
            if safety and safety >= 5:
                final_score = min(100, final_score + 3)

            item = RecommendedVehicleItem(
                variant_id=variant.id,
                variant_name=variant.name,
                model_name=variant.model.name,
                model_slug=variant.model.slug,
                manufacturer_name=variant.model.manufacturer.name,
                manufacturer_slug=variant.model.manufacturer.slug,
                body_type=variant.model.body_type,
                fuel_type=variant.fuel_type,
                transmission=variant.transmission,
                seating_capacity=variant.seating_capacity,
                image_url=variant.model.image_url,
                arai_mileage_kmpl=mileage,
                safety_rating_stars=safety,
                airbags_count=airbags,
                ex_showroom_price=on_road_breakdown.ex_showroom_price,
                on_road_price=on_road_price,
                down_payment_required=user_dp,
                loan_amount=loan_required,
                estimated_monthly_emi=emi,
                interest_rate=budget_summary.estimated_interest_rate,
                tenure_months=tenure,
                ownership_cost=tco_breakdown,
                affordability_score=final_score,
                affordability_category=category,
                affordability_rationale=rationale,
                on_road_breakdown=on_road_breakdown,
            )
            recommended_items.append(item)

        # 4. Sort ranked recommendations
        # Priority: Affordability Score DESC, Safety DESC, Mileage DESC
        recommended_items.sort(
            key=lambda x: (
                x.affordability_score,
                x.safety_rating_stars or 0,
                x.arai_mileage_kmpl,
            ),
            reverse=True,
        )

        return RecommendationResponse(
            user_budget_summary=budget_summary,
            recommended_vehicles=recommended_items,
            total_matches_count=len(recommended_items),
            filter_applied_count=len(all_variants),
        )
