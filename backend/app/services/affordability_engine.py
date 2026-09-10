from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Tuple
from app.core.config import settings
from app.schemas.affordability import (
    AffordabilityBudgetSummary,
    AffordabilityCategory,
    OwnershipCostBreakdown,
)
from app.services.finance_service import FinanceService


def round_inr(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class AffordabilityEngine:
    """Core domain intelligence engine for evaluating Indian car affordability, FOIR, and Total Cost of Ownership (TCO)."""

    @classmethod
    def calculate_budget_summary(
        cls,
        monthly_take_home_income: Decimal,
        existing_monthly_emis: Decimal = Decimal("0.00"),
        available_down_payment: Decimal = Decimal("0.00"),
        desired_tenure_months: int = 60,
        cibil_score: int = 750,
        foir_limit_ratio: Optional[Decimal] = None,
    ) -> AffordabilityBudgetSummary:
        foir_ratio = (
            foir_limit_ratio
            if foir_limit_ratio is not None
            else Decimal(str(settings.DEFAULT_FOIR_LIMIT))
        )
        max_total_emi = round_inr(monthly_take_home_income * foir_ratio)
        available_car_emi = max(Decimal("0.00"), round_inr(max_total_emi - existing_monthly_emis))

        interest_rate = FinanceService.resolve_interest_rate_by_cibil(cibil_score)
        max_loan = FinanceService.calculate_max_loan_from_emi_budget(
            available_monthly_emi=available_car_emi,
            annual_interest_rate=interest_rate,
            tenure_months=desired_tenure_months,
        )

        # Max On-road budget = Loan + Down payment
        max_on_road = max_loan + available_down_payment
        # Recommended comfortable budget is ~80% of upper limit to leave room for unexpected fuel/maintenance inflation
        recommended_budget = round_inr(max_on_road * Decimal("0.80"))

        return AffordabilityBudgetSummary(
            monthly_take_home_income=monthly_take_home_income,
            existing_monthly_emis=existing_monthly_emis,
            max_total_emi_allowed=max_total_emi,
            available_car_emi_budget=available_car_emi,
            available_down_payment=available_down_payment,
            max_affordable_loan=max_loan,
            max_affordable_on_road_price=max_on_road,
            recommended_on_road_budget=recommended_budget,
            estimated_interest_rate=interest_rate,
            tenure_months=desired_tenure_months,
            cibil_score=cibil_score,
            foir_used_percent=round_inr(foir_ratio * Decimal("100.0")),
        )

    @classmethod
    def estimate_monthly_fuel_cost(
        cls,
        monthly_commute_km: int,
        fuel_type: str,
        arai_mileage_kmpl: Decimal,
    ) -> Decimal:
        """Estimates monthly fuel expenses based on commute distance and real-world fuel prices in India."""
        if arai_mileage_kmpl <= 0:
            arai_mileage_kmpl = Decimal("15.0")

        # In real-world Indian city driving, mileage is ~80% of ARAI lab rating
        real_world_mileage = max(Decimal("5.0"), arai_mileage_kmpl * Decimal("0.80"))

        fuel_upper = fuel_type.upper()
        if "ELECTRIC" in fuel_upper or "EV" in fuel_upper:
            # EV efficiency ~ 7-8 km per kWh, cost ~ ₹8.50/kWh
            units_per_km = Decimal("0.13")  # ~1 kWh per 7.7 km
            cost_per_km = units_per_km * Decimal(str(settings.DEFAULT_EV_PER_KWH_INR))
            monthly_cost = Decimal(str(monthly_commute_km)) * cost_per_km
        elif "DIESEL" in fuel_upper:
            liters_needed = Decimal(str(monthly_commute_km)) / real_world_mileage
            monthly_cost = liters_needed * Decimal(str(settings.DEFAULT_DIESEL_PRICE_INR))
        elif "CNG" in fuel_upper:
            kg_needed = Decimal(str(monthly_commute_km)) / real_world_mileage
            monthly_cost = kg_needed * Decimal(str(settings.DEFAULT_CNG_PRICE_INR))
        else:
            # Petrol default
            liters_needed = Decimal(str(monthly_commute_km)) / real_world_mileage
            monthly_cost = liters_needed * Decimal(str(settings.DEFAULT_PETROL_PRICE_INR))

        return round_inr(monthly_cost)

    @classmethod
    def calculate_ownership_breakdown(
        cls,
        monthly_emi: Decimal,
        annual_insurance_estimate: Decimal,
        ex_showroom_price: Decimal,
        monthly_commute_km: int,
        fuel_type: str,
        arai_mileage_kmpl: Decimal,
        monthly_income: Decimal,
    ) -> OwnershipCostBreakdown:
        monthly_fuel = cls.estimate_monthly_fuel_cost(
            monthly_commute_km, fuel_type, arai_mileage_kmpl
        )
        monthly_insurance = round_inr(annual_insurance_estimate / Decimal("12.0"))

        # Maintenance benchmark: 1.5% of ex-showroom annually in India
        annual_maint = ex_showroom_price * Decimal(str(settings.DEFAULT_ANNUAL_MAINTENANCE_RATE))
        monthly_maint = round_inr(annual_maint / Decimal("12.0"))

        total_tco = monthly_emi + monthly_fuel + monthly_insurance + monthly_maint
        tco_percent = (
            round_inr((total_tco / monthly_income) * Decimal("100.0"))
            if monthly_income > 0
            else Decimal("0.00")
        )

        return OwnershipCostBreakdown(
            monthly_emi=monthly_emi,
            monthly_fuel_cost=monthly_fuel,
            monthly_insurance_cost=monthly_insurance,
            monthly_maintenance_cost=monthly_maint,
            total_monthly_tco=total_tco,
            tco_percentage_of_income=tco_percent,
        )

    @classmethod
    def score_affordability(
        cls,
        tco: OwnershipCostBreakdown,
        monthly_income: Decimal,
        existing_emis: Decimal,
    ) -> Tuple[int, AffordabilityCategory, str]:
        tco_pct = tco.tco_percentage_of_income
        total_obligations_pct = (
            ((existing_emis + tco.monthly_emi) / monthly_income) * Decimal("100.0")
            if monthly_income > 0
            else Decimal("100.0")
        )

        if tco_pct <= Decimal("20.0") and total_obligations_pct <= Decimal("40.0"):
            category = AffordabilityCategory.COMFORTABLE
            score = int(100 - (float(tco_pct) * 1.0))
            score = max(80, min(100, score))
            rationale = f"Highly affordable. Car ownership requires only {tco_pct}% of your monthly income, leaving ample surplus for investments and savings."
        elif tco_pct <= Decimal("30.0") and total_obligations_pct <= Decimal("50.0"):
            category = AffordabilityCategory.BALANCED
            score = int(79 - ((float(tco_pct) - 20.0) * 1.9))
            score = max(60, min(79, score))
            rationale = f"Balanced choice. Ownership cost is {tco_pct}% of your net income, well aligned with standard Indian personal finance benchmarks."
        elif tco_pct <= Decimal("40.0"):
            category = AffordabilityCategory.STRETCH
            score = int(59 - ((float(tco_pct) - 30.0) * 1.9))
            score = max(40, min(59, score))
            rationale = f"Stretch budget. Car ownership consumes {tco_pct}% of take-home pay. Maintain an emergency fund for repairs/fuel."
        else:
            category = AffordabilityCategory.RISKY
            score = int(max(5.0, 39.0 - ((float(tco_pct) - 40.0) * 1.5)))
            rationale = f"High financial risk. Total ownership cost is {tco_pct}% of your monthly income, which significantly exceeds recommended safety limits."

        return score, category, rationale
