from decimal import Decimal
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.affordability_constants import AffordabilityProfile, AffordabilityStatus
from app.core.recommendation_constants import RecommendationCategory
from app.db.seed import seed_database
from app.models.location import State
from app.models.vehicle import Variant
from app.schemas.recommendation import (
    QuickRecommendationRequest,
    RecommendationCompareRequest,
    RecommendationRequest,
)
from app.services.recommendation_service import RecommendationService


@pytest.mark.asyncio
class TestRecommendationCandidateFiltering:
    async def test_fuel_type_filtering(self, db_session: AsyncSession):
        """Fuel preference filter returns only matching fuel type variants."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State).limit(1))).scalars().first()

        req = RecommendationRequest(
            monthly_take_home_income=Decimal("150000.00"),
            available_down_payment=Decimal("300000.00"),
            state_id=state.id,
            fuel_preference="Petrol",
        )
        res = await RecommendationService.get_car_recommendations(db_session, req)
        assert res.data_status == "DEMO"
        assert len(res.recommendations) > 0
        for item in res.recommendations:
            assert "PETROL" in item.vehicle.fuel_type.upper()

    async def test_body_type_filtering(self, db_session: AsyncSession):
        """Body type filter returns only matching body type variants."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State).limit(1))).scalars().first()

        req = RecommendationRequest(
            monthly_take_home_income=Decimal("150000.00"),
            available_down_payment=Decimal("300000.00"),
            state_id=state.id,
            body_type="SUV",
        )
        res = await RecommendationService.get_car_recommendations(db_session, req)
        assert len(res.recommendations) > 0
        for item in res.recommendations:
            assert "SUV" in item.vehicle.body_type.upper()

    async def test_automatic_transmission_filtering(self, db_session: AsyncSession):
        """automatic_required filter returns only Automatic, AMT, CVT, DCT, or EV variants."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State).limit(1))).scalars().first()

        req = RecommendationRequest(
            monthly_take_home_income=Decimal("150000.00"),
            available_down_payment=Decimal("300000.00"),
            state_id=state.id,
            automatic_required=True,
        )
        res = await RecommendationService.get_car_recommendations(db_session, req)
        assert len(res.recommendations) > 0
        for item in res.recommendations:
            is_auto = item.vehicle.transmission.upper() in [
                "AUTOMATIC",
                "AMT",
                "CVT",
                "DCT",
                "AT",
            ] or item.vehicle.fuel_type.upper() in ["ELECTRIC", "EV"]
            assert is_auto


@pytest.mark.asyncio
class TestRecommendationAffordabilityAndStretch:
    async def test_unaffordable_vehicles_excluded_from_primary(self, db_session: AsyncSession):
        """Vehicles exceeding budget capacity are excluded from primary recommendations."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State).limit(1))).scalars().first()

        # Low income with ₹0 down payment -> only entry budget cars affordable
        req = RecommendationRequest(
            monthly_take_home_income=Decimal("40000.00"),
            existing_monthly_emi=Decimal("5000.00"),
            available_down_payment=Decimal("50000.00"),
            state_id=state.id,
            affordability_profile=AffordabilityProfile.CONSERVATIVE,
        )
        res = await RecommendationService.get_car_recommendations(db_session, req)
        assert res.total_excluded_count > 0
        for item in res.recommendations:
            assert item.affordability.status in ["COMFORTABLE", "AFFORDABLE"]

    async def test_stretch_vehicles_separated(self, db_session: AsyncSession):
        """Stretch vehicles appear strictly in stretch_options and not primary recommendations."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State).limit(1))).scalars().first()

        req = RecommendationRequest(
            monthly_take_home_income=Decimal("80000.00"),
            available_down_payment=Decimal("150000.00"),
            state_id=state.id,
            affordability_profile=AffordabilityProfile.BALANCED,
        )
        res = await RecommendationService.get_car_recommendations(db_session, req)
        for item in res.recommendations:
            assert item.affordability.status != "STRETCH"
        for item in res.stretch_options:
            assert item.affordability.status == "STRETCH"
            assert item.category == RecommendationCategory.STRETCH_OPTIONS.value


@pytest.mark.asyncio
class TestRecommendationScoringAndRanking:
    async def test_deterministic_scoring_and_ranking(self, db_session: AsyncSession):
        """Identical requests produce identical ranking and scores."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State).limit(1))).scalars().first()

        req = RecommendationRequest(
            monthly_take_home_income=Decimal("120000.00"),
            existing_monthly_emi=Decimal("10000.00"),
            available_down_payment=Decimal("250000.00"),
            state_id=state.id,
            annual_driving_distance_km=Decimal("15000.00"),
        )
        res1 = await RecommendationService.get_car_recommendations(db_session, req)
        res2 = await RecommendationService.get_car_recommendations(db_session, req)

        assert len(res1.recommendations) == len(res2.recommendations)
        for i in range(len(res1.recommendations)):
            assert res1.recommendations[i].variant_id == res2.recommendations[i].variant_id
            assert res1.recommendations[i].score == res2.recommendations[i].score
            assert res1.recommendations[i].rank == i + 1

    async def test_recommendation_explainability_reasons(self, db_session: AsyncSession):
        """Every recommended vehicle includes human-readable reasons."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State).limit(1))).scalars().first()

        req = RecommendationRequest(
            monthly_take_home_income=Decimal("100000.00"),
            available_down_payment=Decimal("200000.00"),
            state_id=state.id,
        )
        res = await RecommendationService.get_car_recommendations(db_session, req)
        for item in res.recommendations:
            assert len(item.reasons) >= 2
            assert item.category in [c.value for c in RecommendationCategory]

    async def test_result_limits_clamped(self, db_session: AsyncSession):
        """Default limit is 5, customizable up to 20."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State).limit(1))).scalars().first()

        req_default = RecommendationRequest(
            monthly_take_home_income=Decimal("200000.00"),
            available_down_payment=Decimal("500000.00"),
            state_id=state.id,
        )
        res_default = await RecommendationService.get_car_recommendations(db_session, req_default)
        assert len(res_default.recommendations) <= 5

        req_limit = RecommendationRequest(
            monthly_take_home_income=Decimal("200000.00"),
            available_down_payment=Decimal("500000.00"),
            state_id=state.id,
            limit=10,
        )
        res_limit = await RecommendationService.get_car_recommendations(db_session, req_limit)
        assert len(res_limit.recommendations) <= 10

    async def test_compare_recommendations_endpoint(self, db_session: AsyncSession):
        """Comparing variants applies multi-dimensional scoring."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State).limit(1))).scalars().first()
        variants = (await db_session.execute(select(Variant).limit(3))).scalars().all()
        assert len(variants) >= 2

        comp_req = RecommendationCompareRequest(
            variant_ids=[v.id for v in variants[:3]],
            monthly_take_home_income=Decimal("120000.00"),
            available_down_payment=Decimal("200000.00"),
            state_id=state.id,
        )
        comp_res = await RecommendationService.compare_recommendations(db_session, comp_req)
        assert comp_res.data_status == "DEMO"
        assert len(comp_res.ranked_vehicles) <= 3
        # Sorted descending by score
        for i in range(len(comp_res.ranked_vehicles) - 1):
            assert comp_res.ranked_vehicles[i].score >= comp_res.ranked_vehicles[i + 1].score
