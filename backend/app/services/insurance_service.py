from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from app.models.insurance import InsuranceRateRule


def round_inr(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class InsuranceEstimateResult:
    def __init__(
        self,
        estimated_idv: Decimal,
        third_party_3yr: Decimal,
        own_damage_1yr: Decimal,
        zero_dep_addon: Decimal,
        total_insurance_premium: Decimal,
    ):
        self.estimated_idv = round_inr(estimated_idv)
        self.third_party_3yr = round_inr(third_party_3yr)
        self.own_damage_1yr = round_inr(own_damage_1yr)
        self.zero_dep_addon = round_inr(zero_dep_addon)
        self.total_insurance_premium = round_inr(total_insurance_premium)


class InsuranceService:
    """Calculates comprehensive 1-Year Own Damage + 3-Year Third-Party Indian motor insurance."""

    @staticmethod
    def calculate_idv(ex_showroom_price: Decimal) -> Decimal:
        """New vehicle Insured Declared Value (IDV) is benchmarked at 95% of ex-showroom price (5% initial depreciation)."""
        return round_inr(ex_showroom_price * Decimal("0.95"))

    @classmethod
    def estimate_insurance(
        cls,
        ex_showroom_price: Decimal,
        engine_cc: Optional[int] = 1199,
        is_ev: bool = False,
        include_zero_dep: bool = True,
        rate_rule: Optional[InsuranceRateRule] = None,
    ) -> InsuranceEstimateResult:
        idv = cls.calculate_idv(ex_showroom_price)

        # 1. Statutory 3-Year Third-Party Tariff (IRDAI)
        if rate_rule:
            tp_tariff = rate_rule.third_party_3yr_tariff_inr
            od_rate = rate_rule.own_damage_base_rate_percent / Decimal("100.0")
            zero_dep_rate = rate_rule.zero_dep_addon_percent / Decimal("100.0")
        else:
            if is_ev:
                tp_tariff = Decimal("5543.00")  # Standard 3-yr EV tariff
                od_rate = Decimal("0.025")  # 2.5% of IDV
                zero_dep_rate = Decimal("0.006")  # 0.6% of IDV
            elif engine_cc and engine_cc < 1000:
                tp_tariff = Decimal("5286.00")  # ~₹2094/yr * 3 minus bundle discount
                od_rate = Decimal("0.026")
                zero_dep_rate = Decimal("0.006")
            elif engine_cc and engine_cc <= 1500:
                tp_tariff = Decimal("9534.00")  # ~₹3416/yr * 3
                od_rate = Decimal("0.028")
                zero_dep_rate = Decimal("0.007")
            else:
                tp_tariff = Decimal("24596.00")  # >1500cc (₹7897/yr * 3)
                od_rate = Decimal("0.032")
                zero_dep_rate = Decimal("0.008")

        # 2. 1-Year Comprehensive Own Damage (OD)
        own_damage = idv * od_rate

        # 3. Zero-Depreciation Add-on
        zero_dep = (idv * zero_dep_rate) if include_zero_dep else Decimal("0.00")

        # 4. GST 18% on Insurance
        subtotal = tp_tariff + own_damage + zero_dep
        gst = subtotal * Decimal("0.18")
        total_premium = subtotal + gst

        return InsuranceEstimateResult(
            estimated_idv=idv,
            third_party_3yr=tp_tariff,
            own_damage_1yr=round_inr(own_damage + (own_damage * Decimal("0.18"))),
            zero_dep_addon=round_inr(zero_dep + (zero_dep * Decimal("0.18"))),
            total_insurance_premium=total_premium,
        )
