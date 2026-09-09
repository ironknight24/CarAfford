from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from app.core.config import settings
from app.models.location import TaxSlab


def round_inr(amount: Decimal) -> Decimal:
    """Rounds a monetary INR value to 2 decimal places using standard ROUND_HALF_UP."""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class TaxCalculationResult:
    def __init__(
        self,
        ex_showroom_price: Decimal,
        rto_tax: Decimal,
        tax_percent: Decimal,
        cess_amount: Decimal,
        registration_fee: Decimal,
        fastag_fee: Decimal,
        green_cess: Decimal,
        hypothecation_fee: Decimal,
        tcs_amount: Decimal,
        total_rto_and_govt_charges: Decimal,
    ):
        self.ex_showroom_price = round_inr(ex_showroom_price)
        self.rto_tax = round_inr(rto_tax)
        self.tax_percent = tax_percent
        self.cess_amount = round_inr(cess_amount)
        self.registration_fee = round_inr(registration_fee)
        self.fastag_fee = round_inr(fastag_fee)
        self.green_cess = round_inr(green_cess)
        self.hypothecation_fee = round_inr(hypothecation_fee)
        self.tcs_amount = round_inr(tcs_amount)
        self.total_rto_and_govt_charges = round_inr(total_rto_and_govt_charges)


class TaxCalculator:
    """Pure domain tax calculation engine for Indian motor vehicle taxation."""

    @staticmethod
    def calculate_tcs(ex_showroom_price: Decimal) -> Decimal:
        """Calculates 1% Tax Collected at Source (TCS) under Section 206C(1F) if ex-showroom > ₹10,00,000."""
        threshold = Decimal(str(settings.TCS_THRESHOLD_INR))
        if ex_showroom_price > threshold:
            rate = Decimal(str(settings.TCS_PERCENT)) / Decimal("100.0")
            return round_inr(ex_showroom_price * rate)
        return Decimal("0.00")

    @classmethod
    def calculate_bh_series_tax(cls, ex_showroom_price: Decimal, fuel_type: str) -> Decimal:
        """Calculates Bharat (BH) Series road tax (payable for 2 years initially in 14-year cycle).
        BH Tax Slabs (MoRTH Gazette):
        - Up to ₹10 Lakh: 8%
        - ₹10 Lakh to ₹20 Lakh: 10%
        - Above ₹20 Lakh: 12%
        Adjustments: Diesel +2%, Electric -2%
        Initial payment is for 2 years (i.e. (Total Tax / 15) * 2 * 1.25).
        """
        if ex_showroom_price <= Decimal("1000000"):
            base_rate = Decimal("8.0")
        elif ex_showroom_price <= Decimal("2000000"):
            base_rate = Decimal("10.0")
        else:
            base_rate = Decimal("12.0")

        fuel_upper = fuel_type.upper()
        if "DIESEL" in fuel_upper:
            base_rate += Decimal("2.0")
        elif "ELECTRIC" in fuel_upper or "EV" in fuel_upper:
            base_rate = max(Decimal("0.0"), base_rate - Decimal("2.0"))

        # BH tax formula for 2 years: (ExShowroom * base_rate% * 1.25 * 2) / 15
        total_15_yr_tax = (ex_showroom_price * (base_rate / Decimal("100.0"))) * Decimal("1.25")
        two_year_tax = (total_15_yr_tax / Decimal("15.0")) * Decimal("2.0")
        return round_inr(two_year_tax)

    @classmethod
    def calculate_state_rto_tax(
        cls,
        ex_showroom_price: Decimal,
        tax_slab: Optional[TaxSlab] = None,
        fuel_type: str = "Petrol",
        is_bh_series: bool = False,
        is_financed: bool = True,
    ) -> TaxCalculationResult:
        """Computes comprehensive State / RTO tax and statutory fees."""
        # 1. TCS
        tcs = cls.calculate_tcs(ex_showroom_price)

        # 2. Registration and Fastag
        reg_fee = Decimal(str(tax_slab.flat_registration_fee if tax_slab else settings.REGISTRATION_BASE_FEE_INR))
        fastag_fee = Decimal(str(tax_slab.fastag_fee if tax_slab else settings.FASTAG_FEE_INR))
        hypothecation_fee = Decimal(str(settings.HYPOTHECATION_FEE_INR)) if is_financed else Decimal("0.00")
        green_cess = Decimal(str(tax_slab.green_cess_amount if tax_slab else "0.00"))

        # 3. RTO Road Tax & Cess
        if is_bh_series:
            rto_tax = cls.calculate_bh_series_tax(ex_showroom_price, fuel_type)
            tax_percent = round_inr((rto_tax / ex_showroom_price) * Decimal("100.0")) if ex_showroom_price > 0 else Decimal("0.00")
            cess_amount = Decimal("0.00")
        elif tax_slab:
            tax_percent = tax_slab.tax_percent
            rto_tax = (ex_showroom_price * (tax_percent / Decimal("100.0")))
            cess_percent = tax_slab.cess_percent
            cess_amount = (rto_tax * (cess_percent / Decimal("100.0")))
        else:
            # Fallback standard Delhi/Central average rate (approx 10% petrol, 12% diesel, 0% EV)
            fuel_upper = fuel_type.upper()
            if "ELECTRIC" in fuel_upper or "EV" in fuel_upper:
                tax_percent = Decimal("0.00")
            elif "DIESEL" in fuel_upper:
                tax_percent = Decimal("12.00")
            else:
                tax_percent = Decimal("10.00")

            rto_tax = (ex_showroom_price * (tax_percent / Decimal("100.0")))
            cess_amount = Decimal("0.00")

        total_govt = rto_tax + cess_amount + reg_fee + fastag_fee + green_cess + hypothecation_fee + tcs

        return TaxCalculationResult(
            ex_showroom_price=ex_showroom_price,
            rto_tax=rto_tax,
            tax_percent=tax_percent,
            cess_amount=cess_amount,
            registration_fee=reg_fee,
            fastag_fee=fastag_fee,
            green_cess=green_cess,
            hypothecation_fee=hypothecation_fee,
            tcs_amount=tcs,
            total_rto_and_govt_charges=total_govt,
        )
