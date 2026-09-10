import pytest
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.affordability_constants import (
    AFFORDABILITY_PROFILES,
    AffordabilityProfile,
    AffordabilityStatus,
    LimitingFactor,
)
from app.core.exceptions import InvalidFinancialInputException, ResourceNotFoundException
from app.db.seed import seed_database
from app.models.finance import Bank, InterestRate, LoanEligibilityRule, LoanProduct
from app.models.location import City, Country, RtoOffice, State
from app.models.pricing import VehiclePrice
from app.models.vehicle import CarModel, Manufacturer, Variant
from app.schemas.affordability import (
    AffordabilityCalculateRequest,
    AffordabilityComparisonRequest,
    MultiVehicleAffordabilityRequest,
    VehicleAffordabilityRequest,
)
from app.services.affordability_service import AffordabilityService, round_inr
from app.services.finance_service import FinanceService


@pytest.mark.asyncio
class TestAffordabilityMathAndProfiles:
    """Tests the mathematical correctness and risk profile tiers of the Affordability Engine."""

    async def test_basic_affordability_budget_balanced(self, db_session: AsyncSession):
        """Income ₹100,000, Existing EMI ₹10,000, Balanced profile (35% FOIR) -> Max EMI ₹35k, Car EMI ₹25k."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State))).scalars().first()
        assert state is not None

        req = AffordabilityCalculateRequest(
            monthly_take_home_income=Decimal("100000.00"),
            existing_monthly_emi=Decimal("10000.00"),
            available_down_payment=Decimal("200000.00"),
            state_id=state.id,
            credit_score=750,
            preferred_loan_tenure_months=60,
            affordability_profile=AffordabilityProfile.BALANCED,
        )
        res = await AffordabilityService.calculate_capacity(db_session, req)

        assert res.monthly_take_home_income == Decimal("100000.00")
        assert res.existing_monthly_emi == Decimal("10000.00")
        assert res.maximum_total_emi == Decimal("35000.00")
        assert res.available_car_emi == Decimal("25000.00")
        assert res.available_down_payment == Decimal("200000.00")
        assert res.maximum_affordable_loan > Decimal("1000000.00")
        assert res.maximum_affordable_on_road_price == res.maximum_affordable_loan + Decimal(
            "200000.00"
        )
        assert res.recommended_safe_budget < res.maximum_affordable_on_road_price
        assert res.stretch_budget > res.maximum_affordable_on_road_price
        assert res.limiting_factor in (LimitingFactor.EMI_CAP, LimitingFactor.LOAN_MAXIMUM)

    async def test_existing_emi_capacity_exhaustion(self, db_session: AsyncSession):
        """Tests zero EMI, moderate EMI, and existing EMI exceeding the allowed FOIR threshold."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State))).scalars().first()
        assert state is not None

        # 1. Zero existing EMI
        req_zero = AffordabilityCalculateRequest(
            monthly_take_home_income=Decimal("100000.00"),
            existing_monthly_emi=Decimal("0.00"),
            available_down_payment=Decimal("100000.00"),
            state_id=state.id,
            affordability_profile=AffordabilityProfile.BALANCED,
        )
        res_zero = await AffordabilityService.calculate_capacity(db_session, req_zero)
        assert res_zero.available_car_emi == Decimal("35000.00")

        # 2. Existing EMI exactly at threshold (₹35,000)
        req_exact = AffordabilityCalculateRequest(
            monthly_take_home_income=Decimal("100000.00"),
            existing_monthly_emi=Decimal("35000.00"),
            available_down_payment=Decimal("100000.00"),
            state_id=state.id,
            affordability_profile=AffordabilityProfile.BALANCED,
        )
        res_exact = await AffordabilityService.calculate_capacity(db_session, req_exact)
        assert res_exact.available_car_emi == Decimal("0.00")
        assert res_exact.maximum_affordable_loan == Decimal("0.00")
        assert res_exact.maximum_affordable_on_road_price == Decimal("100000.00")
        assert res_exact.limiting_factor == LimitingFactor.EMI_CAP

        # 3. Existing EMI exceeding threshold (₹45,000 > ₹35,000)
        req_over = AffordabilityCalculateRequest(
            monthly_take_home_income=Decimal("100000.00"),
            existing_monthly_emi=Decimal("45000.00"),
            available_down_payment=Decimal("100000.00"),
            state_id=state.id,
            affordability_profile=AffordabilityProfile.BALANCED,
        )
        res_over = await AffordabilityService.calculate_capacity(db_session, req_over)
        assert res_over.available_car_emi == Decimal("0.00")
        assert res_over.maximum_affordable_loan == Decimal("0.00")
        assert res_over.maximum_affordable_on_road_price == Decimal("100000.00")
        assert len(res_over.warnings) > 0

    async def test_affordability_profile_monotonicity(self, db_session: AsyncSession):
        """Verifies CONSERVATIVE (30%) < BALANCED (35%) < STRETCH (40%) for the same profile."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State))).scalars().first()
        assert state is not None

        base_kwargs = {
            "monthly_take_home_income": Decimal("100000.00"),
            "existing_monthly_emi": Decimal("10000.00"),
            "available_down_payment": Decimal("200000.00"),
            "state_id": state.id,
            "credit_score": 750,
            "preferred_loan_tenure_months": 60,
        }

        res_cons = await AffordabilityService.calculate_capacity(
            db_session,
            AffordabilityCalculateRequest(
                **base_kwargs, affordability_profile=AffordabilityProfile.CONSERVATIVE
            ),
        )
        res_bal = await AffordabilityService.calculate_capacity(
            db_session,
            AffordabilityCalculateRequest(
                **base_kwargs, affordability_profile=AffordabilityProfile.BALANCED
            ),
        )
        res_str = await AffordabilityService.calculate_capacity(
            db_session,
            AffordabilityCalculateRequest(
                **base_kwargs, affordability_profile=AffordabilityProfile.STRETCH
            ),
        )

        assert res_cons.maximum_total_emi == Decimal("30000.00")
        assert res_cons.available_car_emi == Decimal("20000.00")

        assert res_bal.maximum_total_emi == Decimal("35000.00")
        assert res_bal.available_car_emi == Decimal("25000.00")

        assert res_str.maximum_total_emi == Decimal("40000.00")
        assert res_str.available_car_emi == Decimal("30000.00")

        assert (
            res_cons.maximum_affordable_loan
            < res_bal.maximum_affordable_loan
            < res_str.maximum_affordable_loan
        )
        assert (
            res_cons.maximum_affordable_on_road_price
            < res_bal.maximum_affordable_on_road_price
            < res_str.maximum_affordable_on_road_price
        )

    async def test_down_payment_variations(self, db_session: AsyncSession):
        """Tests zero down payment, normal down payment, and large down payment."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State))).scalars().first()
        assert state is not None

        base_kwargs = {
            "monthly_take_home_income": Decimal("100000.00"),
            "existing_monthly_emi": Decimal("5000.00"),
            "state_id": state.id,
            "credit_score": 750,
            "preferred_loan_tenure_months": 60,
            "affordability_profile": AffordabilityProfile.BALANCED,
        }

        res_zero = await AffordabilityService.calculate_capacity(
            db_session,
            AffordabilityCalculateRequest(**base_kwargs, available_down_payment=Decimal("0.00")),
        )
        res_normal = await AffordabilityService.calculate_capacity(
            db_session,
            AffordabilityCalculateRequest(
                **base_kwargs, available_down_payment=Decimal("200000.00")
            ),
        )
        res_large = await AffordabilityService.calculate_capacity(
            db_session,
            AffordabilityCalculateRequest(
                **base_kwargs, available_down_payment=Decimal("1000000.00")
            ),
        )

        assert res_zero.available_down_payment == Decimal("0.00")
        assert res_normal.available_down_payment == Decimal("200000.00")
        assert res_large.available_down_payment == Decimal("1000000.00")
        assert (
            res_normal.maximum_affordable_on_road_price > res_zero.maximum_affordable_on_road_price
        )
        assert (
            res_large.maximum_affordable_on_road_price > res_normal.maximum_affordable_on_road_price
        )

    async def test_credit_score_rate_and_capacity_sensitivity(self, db_session: AsyncSession):
        """Higher credit scores should resolve more favorable interest rates."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State))).scalars().first()
        assert state is not None

        base_kwargs = {
            "monthly_take_home_income": Decimal("120000.00"),
            "existing_monthly_emi": Decimal("10000.00"),
            "available_down_payment": Decimal("200000.00"),
            "state_id": state.id,
            "preferred_loan_tenure_months": 60,
            "affordability_profile": AffordabilityProfile.BALANCED,
        }

        res_prime = await AffordabilityService.calculate_capacity(
            db_session,
            AffordabilityCalculateRequest(**base_kwargs, credit_score=820),
        )
        res_subprime = await AffordabilityService.calculate_capacity(
            db_session,
            AffordabilityCalculateRequest(**base_kwargs, credit_score=620),
        )

        assert (
            res_prime.applicable_financing_assumptions.interest_rate
            <= res_subprime.applicable_financing_assumptions.interest_rate
        )
        assert res_prime.maximum_affordable_loan >= res_subprime.maximum_affordable_loan


@pytest.mark.asyncio
class TestLocationHierarchyValidation:
    """Tests location validation in the Affordability Domain."""

    async def test_invalid_state_id_raises_404(self, db_session: AsyncSession):
        req = AffordabilityCalculateRequest(
            monthly_take_home_income=Decimal("100000.00"),
            state_id=999999,
            affordability_profile=AffordabilityProfile.BALANCED,
        )
        with pytest.raises(ResourceNotFoundException):
            await AffordabilityService.calculate_capacity(db_session, req)

    async def test_city_mismatch_state_raises_400(self, db_session: AsyncSession):
        await seed_database(db_session)
        states = (await db_session.execute(select(State))).scalars().all()
        assert len(states) >= 2
        state1 = states[0]
        state2 = states[1]
        city2 = (
            (await db_session.execute(select(City).where(City.state_id == state2.id)))
            .scalars()
            .first()
        )
        if city2:
            req = AffordabilityCalculateRequest(
                monthly_take_home_income=Decimal("100000.00"),
                state_id=state1.id,
                city_id=city2.id,
                affordability_profile=AffordabilityProfile.BALANCED,
            )
            with pytest.raises(InvalidFinancialInputException):
                await AffordabilityService.calculate_capacity(db_session, req)


@pytest.mark.asyncio
class TestVehicleAffordabilityEvaluation:
    """Tests evaluating whether specific vehicle variants are comfortable, affordable, stretch, or unaffordable."""

    async def test_evaluate_affordable_vs_unaffordable_vehicles(self, db_session: AsyncSession):
        await seed_database(db_session)
        state = (await db_session.execute(select(State))).scalars().first()
        variants = (
            (await db_session.execute(select(Variant).where(Variant.active == True)))
            .scalars()
            .all()
        )
        assert len(variants) > 0

        # High income user evaluating an entry level variant
        req_affordable = VehicleAffordabilityRequest(
            variant_id=variants[0].id,
            monthly_take_home_income=Decimal("250000.00"),
            existing_monthly_emi=Decimal("10000.00"),
            available_down_payment=Decimal("300000.00"),
            state_id=state.id,
            credit_score=800,
            preferred_loan_tenure_months=60,
            affordability_profile=AffordabilityProfile.BALANCED,
        )
        res_affordable = await AffordabilityService.evaluate_vehicle_affordability(
            db_session, req_affordable
        )
        assert res_affordable.variant_id == variants[0].id
        assert res_affordable.on_road_price > Decimal("0.00")
        assert res_affordable.affordability_status in (
            AffordabilityStatus.COMFORTABLE,
            AffordabilityStatus.AFFORDABLE,
        )
        assert res_affordable.affordable is True
        assert res_affordable.emi_headroom >= Decimal("0.00")

        # Moderate income user evaluating a car where EMI exceeds their budget
        req_unaffordable = VehicleAffordabilityRequest(
            variant_id=variants[-1].id,
            monthly_take_home_income=Decimal("80000.00"),
            existing_monthly_emi=Decimal("15000.00"),  # max total = 28k, available car EMI = 13k
            available_down_payment=Decimal("500000.00"),
            state_id=state.id,
            credit_score=750,
            preferred_loan_tenure_months=60,
            affordability_profile=AffordabilityProfile.BALANCED,
        )
        res_unaffordable = await AffordabilityService.evaluate_vehicle_affordability(
            db_session, req_unaffordable
        )
        assert res_unaffordable.affordable is False
        assert res_unaffordable.affordability_status in (
            AffordabilityStatus.NOT_AFFORDABLE,
            AffordabilityStatus.STRETCH,
        )

        # Ineligible applicant with low income
        req_ineligible = VehicleAffordabilityRequest(
            variant_id=variants[0].id,
            monthly_take_home_income=Decimal("15000.00"),
            existing_monthly_emi=Decimal("0.00"),
            available_down_payment=Decimal("10000.00"),
            state_id=state.id,
            credit_score=500,
            preferred_loan_tenure_months=60,
            affordability_profile=AffordabilityProfile.BALANCED,
        )
        res_ineligible = await AffordabilityService.evaluate_vehicle_affordability(
            db_session, req_ineligible
        )
        assert res_ineligible.affordable is False
        assert res_ineligible.affordability_status in (
            AffordabilityStatus.NO_FINANCING_OPTION,
            AffordabilityStatus.NOT_AFFORDABLE,
        )

    async def test_100_percent_cash_down_payment_is_comfortable(self, db_session: AsyncSession):
        await seed_database(db_session)
        state = (await db_session.execute(select(State))).scalars().first()
        variant = (
            (await db_session.execute(select(Variant).where(Variant.active == True)))
            .scalars()
            .first()
        )

        req = VehicleAffordabilityRequest(
            variant_id=variant.id,
            monthly_take_home_income=Decimal("100000.00"),
            existing_monthly_emi=Decimal("0.00"),
            available_down_payment=Decimal("5000000.00"),  # 50 Lakhs down payment
            state_id=state.id,
            credit_score=750,
            preferred_loan_tenure_months=60,
        )
        res = await AffordabilityService.evaluate_vehicle_affordability(db_session, req)
        assert res.required_loan == Decimal("0.00")
        assert res.estimated_emi == Decimal("0.00")
        assert res.affordable is True
        assert res.affordability_status == AffordabilityStatus.COMFORTABLE

    async def test_compare_vehicles_affordability(self, db_session: AsyncSession):
        await seed_database(db_session)
        state = (await db_session.execute(select(State))).scalars().first()
        variants = (
            (await db_session.execute(select(Variant).where(Variant.active == True)))
            .scalars()
            .all()
        )
        assert len(variants) >= 2

        comp_req = AffordabilityComparisonRequest(
            variant_ids=[variants[0].id, variants[1].id],
            monthly_take_home_income=Decimal("150000.00"),
            existing_monthly_emi=Decimal("10000.00"),
            available_down_payment=Decimal("200000.00"),
            state_id=state.id,
            credit_score=750,
            preferred_loan_tenure_months=60,
            affordability_profile=AffordabilityProfile.BALANCED,
        )
        comp_res = await AffordabilityService.compare_vehicles(db_session, comp_req)

        assert len(comp_res.vehicles) == 2
        assert comp_res.user_budget_summary.available_car_emi == Decimal(
            "42500.00"
        )  # (150k * 0.35) - 10k = 52.5k - 10k = 42.5k
        assert len(comp_res.comparison_notes) >= 2
