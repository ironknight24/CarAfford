from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List, Optional, Tuple

from app.models.finance import LoanFee, LoanProduct
from app.schemas.finance import FeeBreakdownItem


def round_inr(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class LoanFeeCalculatorService:
    """Calculates processing fees, documentation fees, and statutory bank charges for loan products."""

    @classmethod
    def calculate_product_fees(
        cls,
        loan_product: LoanProduct,
        loan_amount: Decimal,
        calculation_date: Optional[datetime] = None,
    ) -> Tuple[Decimal, List[FeeBreakdownItem]]:
        calc_date = calculation_date or datetime.now(timezone.utc)
        if calc_date.tzinfo is None:
            calc_date = calc_date.replace(tzinfo=timezone.utc)

        fee_items: List[FeeBreakdownItem] = []
        total_fee = Decimal("0.00")
        custom_fees = loan_product.fees or []

        # 1. Filter valid fee records
        valid_fees: List[LoanFee] = []
        for fee in custom_fees:
            if not fee.active:
                continue
            eff_from = (
                fee.effective_from.replace(tzinfo=timezone.utc)
                if fee.effective_from.tzinfo is None
                else fee.effective_from
            )
            if eff_from > calc_date:
                continue
            if fee.effective_to is not None:
                eff_to = (
                    fee.effective_to.replace(tzinfo=timezone.utc)
                    if fee.effective_to.tzinfo is None
                    else fee.effective_to
                )
                if eff_to < calc_date:
                    continue
            valid_fees.append(fee)

        # 2. Evaluate fees
        if valid_fees:
            for fee in valid_fees:
                calculated_amt = Decimal("0.00")
                method = fee.calculation_method.upper()

                if method == "FIXED":
                    calculated_amt = fee.fixed_amount or Decimal("0.00")
                elif method == "PERCENTAGE":
                    pct = fee.percentage or Decimal("0.00")
                    calculated_amt = round_inr(loan_amount * (pct / Decimal("100.0")))
                elif method == "CAPPED_PERCENTAGE":
                    pct = fee.percentage or Decimal("0.00")
                    raw_amt = round_inr(loan_amount * (pct / Decimal("100.0")))
                    min_amt = fee.minimum_amount or Decimal("0.00")
                    max_amt = fee.maximum_amount or raw_amt
                    calculated_amt = max(min_amt, min(raw_amt, max_amt))
                elif method == "WAIVED":
                    calculated_amt = Decimal("0.00")

                calculated_amt = round_inr(calculated_amt)
                total_fee += calculated_amt

                fee_items.append(
                    FeeBreakdownItem(
                        fee_name=fee.fee_name,
                        fee_type=fee.fee_type,
                        calculation_method=fee.calculation_method,
                        rate_or_amount=(
                            fee.percentage
                            if method in ["PERCENTAGE", "CAPPED_PERCENTAGE"]
                            else fee.fixed_amount
                        ),
                        calculated_amount=calculated_amt,
                    )
                )
        else:
            # 3. Fallback to product default processing fee attributes
            pct = loan_product.processing_fee_percent or Decimal("0.50")
            raw_fee = round_inr(loan_amount * (pct / Decimal("100.0")))
            min_fee = loan_product.min_processing_fee or Decimal("1500.00")
            max_fee = loan_product.max_processing_fee or Decimal("10000.00")
            calculated_amt = round_inr(max(min_fee, min(raw_fee, max_fee)))
            total_fee += calculated_amt

            fee_items.append(
                FeeBreakdownItem(
                    fee_name="Standard Processing Fee",
                    fee_type="PROCESSING_FEE",
                    calculation_method="CAPPED_PERCENTAGE",
                    rate_or_amount=pct,
                    calculated_amount=calculated_amt,
                )
            )

        return round_inr(total_fee), fee_items
