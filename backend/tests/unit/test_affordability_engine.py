from decimal import Decimal
from app.schemas.affordability import AffordabilityCategory
from app.services.affordability_engine import AffordabilityEngine


def test_affordability_budget_summary():
    # User with ₹1,00,000 monthly take-home, ₹10,000 existing EMIs, ₹2,00,000 down payment
    income = Decimal("100000.00")
    existing_emi = Decimal("10000.00")
    down_payment = Decimal("200000.00")
    tenure = 60
    cibil = 750

    summary = AffordabilityEngine.calculate_budget_summary(
        monthly_take_home_income=income,
        existing_monthly_emis=existing_emi,
        available_down_payment=down_payment,
        desired_tenure_months=tenure,
        cibil_score=cibil,
    )

    # 40% FOIR = ₹40,000 max total EMI allowed
    assert summary.max_total_emi_allowed == Decimal("40000.00")
    # Available car EMI = 40,000 - 10,000 = ₹30,000
    assert summary.available_car_emi_budget == Decimal("30000.00")
    assert summary.estimated_interest_rate == Decimal("8.75")
    # Max loan at ~30k/mo for 5 yrs is ~ ₹14.53 Lakhs
    assert summary.max_affordable_loan > Decimal("1400000.00")
    # Max on-road = loan + down payment
    assert summary.max_affordable_on_road_price == summary.max_affordable_loan + down_payment
    assert summary.recommended_on_road_budget < summary.max_affordable_on_road_price


def test_fuel_cost_estimation_petrol():
    commute_km = 1000
    fuel_type = "Petrol"
    arai_mileage = Decimal("20.0")  # Real world = 16 km/l

    monthly_fuel = AffordabilityEngine.estimate_monthly_fuel_cost(commute_km, fuel_type, arai_mileage)
    # 1000 / 16 = 62.5 liters * ₹96.50 = ₹6031.25
    assert monthly_fuel == Decimal("6031.25")


def test_fuel_cost_estimation_ev():
    commute_km = 1000
    fuel_type = "Electric"
    arai_mileage = Decimal("15.0")

    monthly_fuel = AffordabilityEngine.estimate_monthly_fuel_cost(commute_km, fuel_type, arai_mileage)
    # EV driving 1000 km is approx ₹1105
    assert monthly_fuel == Decimal("1105.00")


def test_affordability_scoring_categories():
    income = Decimal("100000.00")
    existing_emis = Decimal("0.00")

    # Case 1: Low TCO (15% of income) -> Comfortable
    tco_breakdown = AffordabilityEngine.calculate_ownership_breakdown(
        monthly_emi=Decimal("10000.00"),
        annual_insurance_estimate=Decimal("24000.00"),
        ex_showroom_price=Decimal("600000.00"),
        monthly_commute_km=500,
        fuel_type="Petrol",
        arai_mileage_kmpl=Decimal("20.0"),
        monthly_income=income,
    )
    score, category, rationale = AffordabilityEngine.score_affordability(tco_breakdown, income, existing_emis)
    assert category == AffordabilityCategory.COMFORTABLE
    assert score >= 80

    # Case 2: High TCO (45% of income) -> Risky
    tco_risky = AffordabilityEngine.calculate_ownership_breakdown(
        monthly_emi=Decimal("38000.00"),
        annual_insurance_estimate=Decimal("60000.00"),
        ex_showroom_price=Decimal("2000000.00"),
        monthly_commute_km=1500,
        fuel_type="Petrol",
        arai_mileage_kmpl=Decimal("12.0"),
        monthly_income=income,
    )
    score_risky, category_risky, _ = AffordabilityEngine.score_affordability(tco_risky, income, existing_emis)
    assert category_risky == AffordabilityCategory.RISKY
    assert score_risky < 40
