from decimal import Decimal
from app.services.insurance_service import InsuranceService


def test_idv_calculation():
    ex_showroom = Decimal("1000000.00")
    idv = InsuranceService.calculate_idv(ex_showroom)
    # 95% of 10L = 9.5L
    assert idv == Decimal("950000.00")


def test_insurance_estimate_sub_1500cc():
    ex_showroom = Decimal("800000.00")
    res = InsuranceService.estimate_insurance(
        ex_showroom_price=ex_showroom,
        engine_cc=1199,
        is_ev=False,
        include_zero_dep=True,
    )

    assert res.estimated_idv == Decimal("760000.00")
    assert res.third_party_3yr == Decimal("9534.00")
    assert res.own_damage_1yr > Decimal("0.00")
    assert res.zero_dep_addon > Decimal("0.00")
    assert res.total_insurance_premium > (res.third_party_3yr + res.own_damage_1yr)


def test_insurance_estimate_ev():
    ex_showroom = Decimal("1500000.00")
    res = InsuranceService.estimate_insurance(
        ex_showroom_price=ex_showroom,
        engine_cc=None,
        is_ev=True,
        include_zero_dep=True,
    )

    assert res.estimated_idv == Decimal("1425000.00")
    assert res.third_party_3yr == Decimal("5543.00")
    assert res.total_insurance_premium > Decimal("0.00")
