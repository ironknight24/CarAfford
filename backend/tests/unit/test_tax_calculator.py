from decimal import Decimal
from app.models.location import TaxSlab
from app.services.tax_calculator import TaxCalculator


def test_tcs_under_10_lakhs():
    # Car under 10L: No TCS
    ex_showroom = Decimal("999999.00")
    tcs = TaxCalculator.calculate_tcs(ex_showroom)
    assert tcs == Decimal("0.00")


def test_tcs_above_10_lakhs():
    # Car above 10L: 1% TCS
    ex_showroom = Decimal("1500000.00")
    tcs = TaxCalculator.calculate_tcs(ex_showroom)
    assert tcs == Decimal("15000.00")


def test_bh_series_tax_petrol_under_10l():
    # ₹8,00,000 petrol car under BH series:
    # Base rate 8%. Total 15-yr tax = (800000 * 0.08 * 1.25) = ₹80,000
    # 2-yr tax = (80000 / 15) * 2 = ₹10,666.67
    ex_showroom = Decimal("800000.00")
    tax = TaxCalculator.calculate_bh_series_tax(ex_showroom, "Petrol")
    assert tax == Decimal("10666.67")


def test_bh_series_tax_diesel_between_10l_and_20l():
    # ₹15,00,000 diesel car under BH series:
    # Base rate 10% + 2% diesel = 12%
    # Total 15-yr tax = 1500000 * 0.12 * 1.25 = ₹2,25,000
    # 2-yr tax = (225000 / 15) * 2 = ₹30,000
    ex_showroom = Decimal("1500000.00")
    tax = TaxCalculator.calculate_bh_series_tax(ex_showroom, "Diesel")
    assert tax == Decimal("30000.00")


def test_state_rto_tax_calculation_with_slab():
    slab = TaxSlab(
        state_id=1,
        fuel_type="Petrol",
        min_ex_showroom=Decimal("600000"),
        max_ex_showroom=Decimal("1000000"),
        tax_percent=Decimal("7.00"),
        cess_percent=Decimal("10.00"),  # 10% cess on tax
        flat_registration_fee=Decimal("600.00"),
        fastag_fee=Decimal("600.00"),
        green_cess_amount=Decimal("0.00"),
        is_bh_series=False,
    )

    ex_price = Decimal("800000.00")
    result = TaxCalculator.calculate_state_rto_tax(
        ex_showroom_price=ex_price,
        tax_slab=slab,
        fuel_type="Petrol",
        is_bh_series=False,
        is_financed=True,
    )

    # 7% tax on 8L = 56,000
    assert result.rto_tax == Decimal("56000.00")
    # 10% cess on 56,000 = 5,600
    assert result.cess_amount == Decimal("5600.00")
    # Registration + fastag + hypothecation (1500)
    assert result.registration_fee == Decimal("600.00")
    assert result.fastag_fee == Decimal("600.00")
    assert result.hypothecation_fee == Decimal("1500.00")
    assert result.tcs_amount == Decimal("0.00")
    # Total govt charges = 56000 + 5600 + 600 + 600 + 1500 = 64300
    assert result.total_rto_and_govt_charges == Decimal("64300.00")
