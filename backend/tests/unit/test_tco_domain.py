from decimal import Decimal
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidFinancialInputException, ResourceNotFoundException
from app.core.tco_constants import DEFAULT_FUEL_PRICES, DEFAULT_MAINTENANCE_RATES
from app.db.seed import seed_database
from app.models.location import City, State
from app.models.vehicle import Variant
from app.schemas.tco import TCOCalculationRequest, TCOComparisonRequest, TCOVehicleRequest
from app.services.finance_service import FinanceService
from app.services.tco_service import TCOService, round_inr


class TestTCOFuelAndEnergyMath:
    def test_ice_fuel_cost_calculation(self):
        """10,000 km/year, 15 km/l, ₹100/litre -> Annual fuel cost = ₹66,666.67."""
        annual_dist = Decimal("10000.00")
        efficiency = Decimal("15.00")
        fuel_price = Decimal("100.00")

        cost, price, unit, eff_unit = TCOService.calculate_annual_fuel_cost(
            fuel_type="PETROL",
            efficiency=efficiency,
            annual_distance_km=annual_dist,
            custom_fuel_price=fuel_price,
        )

        expected = round_inr((annual_dist / efficiency) * fuel_price)
        assert cost == Decimal("66666.67")
        assert cost == expected
        assert unit == "Litre"
        assert eff_unit == "km/l"
        assert isinstance(cost, Decimal)

    def test_ev_electricity_cost_calculation(self):
        """EV kWh-based calculation: 12,000 km/year, 7.0 km/kWh, ₹8.50/kWh -> ₹14,571.43."""
        annual_dist = Decimal("12000.00")
        efficiency = Decimal("7.00")
        kwh_price = Decimal("8.50")

        cost, price, unit, eff_unit = TCOService.calculate_annual_fuel_cost(
            fuel_type="ELECTRIC",
            efficiency=efficiency,
            annual_distance_km=annual_dist,
            custom_fuel_price=kwh_price,
        )

        expected = round_inr((annual_dist / efficiency) * kwh_price)
        assert cost == Decimal("14571.43")
        assert cost == expected
        assert unit == "kWh"
        assert eff_unit == "km/kWh"
        assert isinstance(cost, Decimal)

    def test_driving_distance_monthly_to_annual_reconciliation(self):
        """Monthly distance * 12 == Annual distance."""
        req = TCOCalculationRequest(
            state_id=1,
            monthly_driving_distance_km=Decimal("1250.00"),
        )
        assert req.annual_driving_distance_km == Decimal("15000.00")

        req2 = TCOCalculationRequest(
            state_id=1,
            annual_driving_distance_km=Decimal("18000.00"),
        )
        assert req2.monthly_driving_distance_km == Decimal("1500.00")


class TestTCOOperatingCostsAndMaintenance:
    def test_maintenance_cost_ice_vs_ev(self):
        """EV routine maintenance is lower than ICE routine maintenance."""
        dist = Decimal("15000.00")
        petrol_maint = TCOService.calculate_annual_maintenance_cost("PETROL", dist)
        ev_maint = TCOService.calculate_annual_maintenance_cost("ELECTRIC", dist)
        diesel_maint = TCOService.calculate_annual_maintenance_cost("DIESEL", dist)

        # Petrol: 6000 + 15000 * 0.40 = 6000 + 6000 = 12,000
        assert petrol_maint == Decimal("12000.00")
        # EV: 3500 + 15000 * 0.25 = 3500 + 3750 = 7,250
        assert ev_maint == Decimal("7250.00")
        # Diesel: 8000 + 15000 * 0.50 = 8000 + 7500 = 15,500
        assert diesel_maint == Decimal("15500.00")
        assert ev_maint < petrol_maint < diesel_maint

    def test_insurance_renewals_no_year1_double_counting(self):
        """Year 1 is covered in on-road price; renewal premiums apply for years 2..N."""
        first_year_ins = Decimal("30000.00")
        y2 = TCOService.calculate_annual_insurance_renewal(first_year_ins, 2)
        y3 = TCOService.calculate_annual_insurance_renewal(first_year_ins, 3)
        y4 = TCOService.calculate_annual_insurance_renewal(first_year_ins, 4)

        assert y2 == Decimal("19500.00")  # 65% of 30,000
        assert y3 == Decimal("18000.00")  # 60% of 30,000
        assert y4 == Decimal("22500.00")  # 75% of 30,000 (with TP renewal)


class TestTCOFinancingAndPeriods:
    def test_loan_term_shorter_than_ownership_period(self):
        """36-month loan with 60-month ownership: financing stops after month 36."""
        principal = Decimal("500000.00")
        rate = Decimal("9.00")
        tenure = 36

        amort = FinanceService.calculate_amortization_schedule(
            principal=principal,
            annual_interest_rate=rate,
            tenure_months=tenure,
        )

        p3 = TCOService.build_period_breakdown(
            period_key="3_years",
            years=3,
            months=36,
            label="3 Years",
            annual_fuel_cost=Decimal("50000.00"),
            first_year_insurance=Decimal("30000.00"),
            annual_maintenance_cost=Decimal("10000.00"),
            down_payment=Decimal("100000.00"),
            amortization_schedule=amort,
            loan_tenure_months=tenure,
            loan_processing_fees=Decimal("2500.00"),
            ex_showroom_price=Decimal("600000.00"),
            is_financed=True,
        )

        p5 = TCOService.build_period_breakdown(
            period_key="5_years",
            years=5,
            months=60,
            label="5 Years",
            annual_fuel_cost=Decimal("50000.00"),
            first_year_insurance=Decimal("30000.00"),
            annual_maintenance_cost=Decimal("10000.00"),
            down_payment=Decimal("100000.00"),
            amortization_schedule=amort,
            loan_tenure_months=tenure,
            loan_processing_fees=Decimal("2500.00"),
            ex_showroom_price=Decimal("600000.00"),
            is_financed=True,
        )

        # In both year 3 and year 5, loan principal is fully paid (₹500,000)
        assert p3.loan_principal_paid == principal
        assert p5.loan_principal_paid == principal
        assert p5.financing_interest == p3.financing_interest
        assert p5.total_loan_repayment_paid == p3.total_loan_repayment_paid

        # Operating costs continued for year 4 and 5
        assert p5.total_operating_cost > p3.total_operating_cost
        assert p5.fuel_cost == Decimal("250000.00")  # 50,000 * 5

    @pytest.mark.asyncio
    async def test_full_tco_calculation_period_progression(self, db_session: AsyncSession):
        """Verify 1-year, 3-year, and 5-year TCO progression and consistency."""
        await seed_database(db_session)

        state = (await db_session.execute(select(State).limit(1))).scalars().first()
        assert state is not None

        variant = (await db_session.execute(select(Variant).limit(1))).scalars().first()
        assert variant is not None

        req = TCOCalculationRequest(
            variant_id=variant.id,
            state_id=state.id,
            annual_driving_distance_km=Decimal("12000.00"),
            down_payment=Decimal("200000.00"),
            credit_score=750,
            preferred_loan_tenure_months=36,
            is_financed=True,
        )

        res = await TCOService.calculate_tco(db_session, req)

        assert res.data_status == "DEMO"
        assert res.initial_cost.total_on_road_price > 0
        assert res.initial_cost.down_payment == Decimal("200000.00")
        assert res.financing is not None
        assert res.financing.tenure_months == 36

        p1 = res.periods["1_year"]
        p3 = res.periods["3_years"]
        p5 = res.periods["5_years"]

        assert p1.total_operating_cost < p3.total_operating_cost < p5.total_operating_cost
        assert p3.loan_principal_paid == res.initial_cost.loan_principal
        assert p5.loan_principal_paid == p3.loan_principal_paid
        assert p5.financing_interest == p3.financing_interest
        assert p5.total_loan_repayment_paid == p3.total_loan_repayment_paid
        assert p1.total_cash_outflow < p3.total_cash_outflow < p5.total_cash_outflow
        assert p5.average_monthly_cost == round_inr(p5.total_cash_outflow / Decimal("60.0"))
        assert p5.average_annual_cost == round_inr(p5.total_cash_outflow / Decimal("5.0"))

    @pytest.mark.asyncio
    async def test_100_percent_cash_purchase_tco(self, db_session: AsyncSession):
        """100% Cash purchase has ₹0 EMI, ₹0 loan interest, and ₹0 financing fees."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State).limit(1))).scalars().first()
        variant = (await db_session.execute(select(Variant).limit(1))).scalars().first()

        req = TCOCalculationRequest(
            variant_id=variant.id,
            state_id=state.id,
            is_financed=False,
            annual_driving_distance_km=Decimal("10000.00"),
        )

        res = await TCOService.calculate_tco(db_session, req)
        assert res.initial_cost.loan_principal == Decimal("0.00")
        assert res.initial_cost.down_payment == res.initial_cost.total_on_road_price

        p5 = res.periods["5_years"]
        assert p5.financing_interest == Decimal("0.00")
        assert p5.financing_fees == Decimal("0.00")
        assert p5.total_loan_repayment_paid == Decimal("0.00")
        assert p5.total_cash_outflow == round_inr(res.initial_cost.total_on_road_price + p5.total_operating_cost)


class TestTCOComparisonAndValidation:
    @pytest.mark.asyncio
    async def test_compare_multiple_vehicles_tco(self, db_session: AsyncSession):
        """Verify side-by-side comparison across multiple variants."""
        await seed_database(db_session)
        state = (await db_session.execute(select(State).limit(1))).scalars().first()
        variants = (await db_session.execute(select(Variant).limit(3))).scalars().all()
        assert len(variants) >= 2

        req = TCOComparisonRequest(
            variant_ids=[v.id for v in variants[:3]],
            state_id=state.id,
            annual_driving_distance_km=Decimal("12000.00"),
            down_payment=Decimal("200000.00"),
        )

        res = await TCOService.compare_vehicles_tco(db_session, req)
        assert res.data_status == "DEMO"
        assert len(res.compared_vehicles) == len(variants[:3])
        for i in range(len(res.compared_vehicles) - 1):
            assert res.compared_vehicles[i].five_year_tco <= res.compared_vehicles[i + 1].five_year_tco

    @pytest.mark.asyncio
    async def test_location_validation_raises(self, db_session: AsyncSession):
        """Invalid state ID raises ResourceNotFoundException."""
        await seed_database(db_session)
        with pytest.raises(ResourceNotFoundException):
            await TCOService.validate_location_hierarchy(db_session, state_id=99999)
