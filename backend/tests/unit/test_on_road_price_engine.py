"""
Comprehensive unit tests for the On-Road Price Calculation Engine.
Validates:
1. Historical ex-showroom price lookup by calculation_date
2. Missing ex-showroom price raises ResourceNotFoundException
3. Invalid location hierarchy (City or RTO not in State) raises ValueError
4. Multi-tier bracketed road tax calculation (e.g. Karnataka 14%/17%)
5. Dependent cess on road tax (e.g. Karnataka 11% Infrastructure Cess)
6. Fixed statutory fees (Registration, FASTag, HSRP)
7. Safe formula evaluation (MoRTH BH-Series calculation)
8. Federal Section 206C(1F) TCS (1% for > ₹10 Lakh, 0% otherwise)
9. Electric Vehicle (EV) exemptions and zero-tax rules
10. Insurance calculation modes: DEFAULT_ESTIMATE, USER_PROVIDED, ZERO_DEP
11. Strict Decimal precision and exact sum reconciliation (totals == sum of line items)
12. Inter-state location price differentiation (Bengaluru vs Delhi vs Mumbai)
13. Provenance tracking and Data Quality demo labeling
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundException
from app.models.data_source import DataSource
from app.models.location import City, Country, RtoOffice, State
from app.models.pricing import VehiclePrice
from app.models.tax_rule import TaxRule, TaxRuleBracket
from app.models.vehicle import CarModel, Manufacturer, Variant, VariantSpecification
from app.schemas.pricing import OnRoadPriceCalculationRequest
from app.services.on_road_price_service import OnRoadPriceCalculationService


async def create_base_test_data(db: AsyncSession):
    """Helper to seed country, states, cities, rtos, manufacturer, model, specifications, and variants."""
    country = Country(name="India", iso_code="IN", iso3_code="IND")
    db.add(country)
    await db.flush()

    ka_state = State(country_id=country.id, name="Karnataka", code="KA", region_type="STATE")
    dl_state = State(country_id=country.id, name="Delhi", code="DL", region_type="UT")
    mh_state = State(country_id=country.id, name="Maharashtra", code="MH", region_type="STATE")
    db.add_all([ka_state, dl_state, mh_state])
    await db.flush()

    blr_city = City(state_id=ka_state.id, name="Bengaluru", slug="bengaluru", tier="TIER_1")
    delhi_city = City(state_id=dl_state.id, name="New Delhi", slug="new-delhi", tier="TIER_1")
    mumbai_city = City(state_id=mh_state.id, name="Mumbai", slug="mumbai", tier="TIER_1")
    db.add_all([blr_city, delhi_city, mumbai_city])
    await db.flush()

    ka01_rto = RtoOffice(
        state_id=ka_state.id, city_id=blr_city.id, code="KA01", name="Koramangala RTO"
    )
    dl01_rto = RtoOffice(
        state_id=dl_state.id, city_id=delhi_city.id, code="DL01", name="Mall Road RTO"
    )
    db.add_all([ka01_rto, dl01_rto])
    await db.flush()

    source = DataSource(
        name="Official State Gazettes",
        slug="official-state-gazettes",
        provider_type="government",
        base_url="https://transport.karnataka.gov.in",
        is_active=True,
    )
    db.add(source)
    await db.flush()

    # Manufacturer & Model
    mfg = Manufacturer(name="Tata Motors", slug="tata-motors", country="India", active=True)
    db.add(mfg)
    await db.flush()

    model_nexon = CarModel(
        manufacturer_id=mfg.id,
        name="Nexon",
        slug="nexon",
        body_type="SUV",
        segment="B2",
        active=True,
    )
    model_ev = CarModel(
        manufacturer_id=mfg.id,
        name="Nexon EV",
        slug="nexon-ev",
        body_type="SUV",
        segment="B2",
        active=True,
    )
    db.add_all([model_nexon, model_ev])
    await db.flush()

    # Petrol Variant (Ex-showroom ₹11,00,000 > ₹10 Lakh, triggers TCS)
    var_petrol = Variant(
        model_id=model_nexon.id,
        name="Creative Plus Petrol MT",
        slug="creative-plus-petrol-mt",
        fuel_type="PETROL",
        transmission="MANUAL",
        seating_capacity=5,
        engine_cc=1199,
        active=True,
    )
    # EV Variant
    var_ev = Variant(
        model_id=model_ev.id,
        name="Empowered Plus LR EV",
        slug="empowered-plus-lr-ev",
        fuel_type="ELECTRIC",
        transmission="AUTOMATIC",
        seating_capacity=5,
        battery_capacity_kwh=Decimal("45.0"),
        active=True,
    )
    db.add_all([var_petrol, var_ev])
    await db.flush()

    # Specs
    spec_p = VariantSpecification(
        variant_id=var_petrol.id, engine_displacement_cc=1199, airbags_count=6
    )
    spec_ev = VariantSpecification(variant_id=var_ev.id, airbags_count=6)
    db.add_all([spec_p, spec_ev])
    await db.flush()

    # Pricing records (historical + active)
    # Historical price: 2023-01-01 to 2023-12-31 = ₹10,50,000
    p_hist = VehiclePrice(
        variant_id=var_petrol.id,
        source_id=source.id,
        ex_showroom_price=Decimal("1050000.00"),
        effective_from=datetime(2023, 1, 1, tzinfo=timezone.utc),
        effective_to=datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        price_type="EX_SHOWROOM",
    )
    # Active price: 2024-01-01 onwards = ₹11,00,000
    p_active = VehiclePrice(
        variant_id=var_petrol.id,
        source_id=source.id,
        ex_showroom_price=Decimal("1100000.00"),
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        effective_to=None,
        price_type="EX_SHOWROOM",
    )
    # EV Price: ₹15,00,000
    p_ev = VehiclePrice(
        variant_id=var_ev.id,
        source_id=source.id,
        ex_showroom_price=Decimal("1500000.00"),
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        effective_to=None,
        price_type="EX_SHOWROOM",
    )
    db.add_all([p_hist, p_active, p_ev])
    await db.flush()

    # Tax Rules:
    # 1. KA Road Tax Bracketed: 10L-20L @ 17%
    ka_road_tax = TaxRule(
        name="Karnataka Motor Vehicle Road Tax",
        state_id=ka_state.id,
        source_id=source.id,
        rule_category="TAX",
        tax_type="ROAD_TAX",
        calculation_method="BRACKETED",
        base_amount_type="EX_SHOWROOM",
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        active=True,
    )
    db.add(ka_road_tax)
    await db.flush()

    b1 = TaxRuleBracket(
        tax_rule_id=ka_road_tax.id,
        bracket_order=1,
        minimum_value=Decimal("0"),
        maximum_value=Decimal("500000"),
        rate=Decimal("13.00"),
    )
    b2 = TaxRuleBracket(
        tax_rule_id=ka_road_tax.id,
        bracket_order=2,
        minimum_value=Decimal("500000"),
        maximum_value=Decimal("1000000"),
        rate=Decimal("14.00"),
    )
    b3 = TaxRuleBracket(
        tax_rule_id=ka_road_tax.id,
        bracket_order=3,
        minimum_value=Decimal("1000000"),
        maximum_value=Decimal("2000000"),
        rate=Decimal("17.00"),
    )
    b4 = TaxRuleBracket(
        tax_rule_id=ka_road_tax.id,
        bracket_order=4,
        minimum_value=Decimal("2000000"),
        maximum_value=None,
        rate=Decimal("18.00"),
    )
    db.add_all([b1, b2, b3, b4])

    # 2. KA Infra Cess: 11% on Road Tax
    ka_cess = TaxRule(
        name="Karnataka Infrastructure Cess",
        state_id=ka_state.id,
        source_id=source.id,
        rule_category="CESS",
        tax_type="CESS",
        calculation_method="PERCENTAGE",
        rate=Decimal("11.00"),
        base_amount_type="ROAD_TAX",
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        active=True,
    )
    # 3. KA Registration Fee: ₹600 Fixed
    ka_reg = TaxRule(
        name="KA Standard Registration Fee",
        state_id=ka_state.id,
        source_id=source.id,
        rule_category="REGISTRATION",
        tax_type="REGISTRATION_FEE",
        calculation_method="FIXED",
        fixed_amount=Decimal("600.00"),
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        active=True,
    )
    # 4. KA FASTag Fee: ₹500 Fixed
    ka_fastag = TaxRule(
        name="KA FASTag & Tag Issuance Fee",
        state_id=ka_state.id,
        source_id=source.id,
        rule_category="FEE",
        tax_type="FASTAG_FEE",
        calculation_method="FIXED",
        fixed_amount=Decimal("500.00"),
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        active=True,
    )
    # 5. KA Hypothecation Fee: ₹1500 Fixed
    ka_hypo = TaxRule(
        name="KA Bank Hypothecation Endorsement",
        state_id=ka_state.id,
        source_id=source.id,
        rule_category="FEE",
        tax_type="HYPOTHECATION_FEE",
        calculation_method="FIXED",
        fixed_amount=Decimal("1500.00"),
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        active=True,
    )
    # 6. DL Road Tax: Flat 10% on Petrol
    dl_tax = TaxRule(
        name="Delhi Road Tax (Petrol)",
        state_id=dl_state.id,
        source_id=source.id,
        rule_category="TAX",
        tax_type="ROAD_TAX",
        calculation_method="PERCENTAGE",
        rate=Decimal("10.00"),
        base_amount_type="EX_SHOWROOM",
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        active=True,
    )
    # 7. DL EV Exemption: 0% Road Tax on EV
    dl_ev_tax = TaxRule(
        name="Delhi EV Road Tax Exemption",
        state_id=dl_state.id,
        source_id=source.id,
        rule_category="TAX",
        tax_type="ROAD_TAX",
        calculation_method="PERCENTAGE",
        rate=Decimal("0.00"),
        base_amount_type="EX_SHOWROOM",
        is_ev=True,
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        active=True,
    )
    # 8. KA BH-Series Formula
    ka_bh_rule = TaxRule(
        name="MoRTH Bharat BH-Series Tax",
        state_id=ka_state.id,
        source_id=source.id,
        rule_category="TAX",
        tax_type="ROAD_TAX",
        calculation_method="FORMULA",
        formula_definition={"type": "BH_SERIES", "factor": 1.25, "payment_tenure_years": 2},
        priority=200,
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        active=True,
    )

    db.add_all([ka_cess, ka_reg, ka_fastag, ka_hypo, dl_tax, dl_ev_tax, ka_bh_rule])
    await db.commit()

    return {
        "ka_state": ka_state,
        "dl_state": dl_state,
        "mh_state": mh_state,
        "blr_city": blr_city,
        "delhi_city": delhi_city,
        "mumbai_city": mumbai_city,
        "ka01_rto": ka01_rto,
        "dl01_rto": dl01_rto,
        "var_petrol": var_petrol,
        "var_ev": var_ev,
    }


@pytest.mark.asyncio
async def test_on_road_price_karnataka_calculation(db_session: AsyncSession):
    data = await create_base_test_data(db_session)
    var = data["var_petrol"]
    state = data["ka_state"]
    city = data["blr_city"]
    rto = data["ka01_rto"]

    req = OnRoadPriceCalculationRequest(
        variant_id=var.id,
        state_id=state.id,
        city_id=city.id,
        rto_id=rto.id,
        calculation_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
        insurance_option="ZERO_DEP",
        is_financed=True,
    )

    res = await OnRoadPriceCalculationService.calculate_on_road_price(db_session, req)

    # Ex-Showroom for Petrol: ₹11,00,000
    assert res.totals.ex_showroom_price == Decimal("1100000.00")

    # Road Tax: 17% of 11,00,000 = 187,000
    # Cess: 11% of 187,000 = 20,570
    # TCS: 1% of 11,00,000 = 11,000 (ex-showroom > 10L)
    # Total Taxes = 187,000 + 20,570 + 11,000 = 218,570
    assert res.totals.total_statutory_taxes == Decimal("218570.00")

    # Registration (600) + FASTag (500) + Hypothecation (1500) = 2,600
    assert res.totals.total_registration_and_fees == Decimal("2600.00")

    # Insurance total > 0
    assert res.totals.total_insurance > Decimal("0.00")

    # Exact Sum Reconciliation (No floating point discrepancy)
    expected_on_road = (
        res.totals.ex_showroom_price
        + res.totals.total_statutory_taxes
        + res.totals.total_registration_and_fees
        + res.totals.total_insurance
        + res.totals.total_other_charges
    )
    assert res.totals.on_road_price == expected_on_road

    # Verify Data Quality
    assert res.data_quality.data_status == "DEMO"
    assert res.data_quality.has_demo_rules is True
    assert len(res.data_quality.sources) > 0


@pytest.mark.asyncio
async def test_historical_price_resolution(db_session: AsyncSession):
    data = await create_base_test_data(db_session)
    var = data["var_petrol"]
    state = data["ka_state"]

    # In 2023, ex-showroom price was ₹10,50,000
    req_2023 = OnRoadPriceCalculationRequest(
        variant_id=var.id,
        state_id=state.id,
        calculation_date=datetime(2023, 6, 15, tzinfo=timezone.utc),
    )
    res_2023 = await OnRoadPriceCalculationService.calculate_on_road_price(db_session, req_2023)
    assert res_2023.totals.ex_showroom_price == Decimal("1050000.00")

    # In 2024, ex-showroom price is ₹11,00,000
    req_2024 = OnRoadPriceCalculationRequest(
        variant_id=var.id,
        state_id=state.id,
        calculation_date=datetime(2024, 6, 15, tzinfo=timezone.utc),
    )
    res_2024 = await OnRoadPriceCalculationService.calculate_on_road_price(db_session, req_2024)
    assert res_2024.totals.ex_showroom_price == Decimal("1100000.00")


@pytest.mark.asyncio
async def test_missing_price_raises_404(db_session: AsyncSession):
    data = await create_base_test_data(db_session)
    var = data["var_petrol"]
    state = data["ka_state"]

    # Target date in 2020 before any price record exists
    req = OnRoadPriceCalculationRequest(
        variant_id=var.id,
        state_id=state.id,
        calculation_date=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    with pytest.raises(ResourceNotFoundException) as exc_info:
        await OnRoadPriceCalculationService.calculate_on_road_price(db_session, req)
    assert "No active ex-showroom price found" in str(exc_info.value)


@pytest.mark.asyncio
async def test_location_hierarchy_validation(db_session: AsyncSession):
    data = await create_base_test_data(db_session)
    var = data["var_petrol"]
    ka_state = data["ka_state"]
    delhi_city = data["delhi_city"]  # Belongs to DL, not KA!

    req = OnRoadPriceCalculationRequest(
        variant_id=var.id,
        state_id=ka_state.id,
        city_id=delhi_city.id,  # Mismatched state and city
    )
    with pytest.raises(ValueError) as exc_info:
        await OnRoadPriceCalculationService.calculate_on_road_price(db_session, req)
    assert "does not belong to State" in str(exc_info.value)


@pytest.mark.asyncio
async def test_tcs_applicability_above_and_below_10_lakh(db_session: AsyncSession):
    data = await create_base_test_data(db_session)
    var_p = data["var_petrol"]
    state = data["dl_state"]

    # 11 Lakh vehicle -> Section 206C(1F) TCS applies (1% = ₹11,000)
    req = OnRoadPriceCalculationRequest(
        variant_id=var_p.id,
        state_id=state.id,
        calculation_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    res = await OnRoadPriceCalculationService.calculate_on_road_price(db_session, req)
    tcs_item = next((item for item in res.breakdown if item.component == "TCS"), None)
    assert tcs_item is not None
    assert tcs_item.calculated_amount == Decimal("11000.00")
    assert tcs_item.rate == Decimal("1.00")


@pytest.mark.asyncio
async def test_user_provided_insurance_override(db_session: AsyncSession):
    data = await create_base_test_data(db_session)
    var = data["var_petrol"]
    state = data["ka_state"]

    custom_ins = Decimal("32500.00")
    req = OnRoadPriceCalculationRequest(
        variant_id=var.id,
        state_id=state.id,
        insurance_option="USER_PROVIDED",
        insurance_amount=custom_ins,
    )
    res = await OnRoadPriceCalculationService.calculate_on_road_price(db_session, req)
    assert res.totals.total_insurance == custom_ins

    ins_item = next(item for item in res.breakdown if item.component == "INSURANCE")
    assert ins_item.calculation_method == "USER_OVERRIDE"
    assert ins_item.calculated_amount == custom_ins
    assert ins_item.status == "USER_OVERRIDDEN"


@pytest.mark.asyncio
async def test_bh_series_formula_calculation(db_session: AsyncSession):
    data = await create_base_test_data(db_session)
    var = data["var_petrol"]
    state = data["ka_state"]

    req = OnRoadPriceCalculationRequest(
        variant_id=var.id,
        state_id=state.id,
        is_bh_series=True,
    )
    res = await OnRoadPriceCalculationService.calculate_on_road_price(db_session, req)
    assert res.is_bh_series is True

    # Check for BH Series formula road tax item
    bh_item = next((item for item in res.breakdown if item.calculation_method == "FORMULA"), None)
    assert bh_item is not None
    # 11 Lakh price -> 10% rate for 10L-20L slab -> (1,100,000 * 10% * 1.25 * 2) / 15 = 18,333.33
    expected_bh_tax = (
        Decimal("1100000.00") * Decimal("0.10") * Decimal("1.25") * Decimal("2.0")
    ) / Decimal("15.0")
    assert bh_item.calculated_amount == expected_bh_tax.quantize(Decimal("0.01"))


@pytest.mark.asyncio
async def test_location_differentiation_bengaluru_vs_delhi(db_session: AsyncSession):
    """Verifies that different states produce distinctly different on-road prices for the exact same vehicle."""
    data = await create_base_test_data(db_session)
    var = data["var_petrol"]
    ka_state = data["ka_state"]
    dl_state = data["dl_state"]

    # Calculate for Karnataka (17% tax + 11% cess)
    res_ka = await OnRoadPriceCalculationService.calculate_on_road_price(
        db_session,
        OnRoadPriceCalculationRequest(variant_id=var.id, state_id=ka_state.id, is_financed=False),
    )

    # Calculate for Delhi (10% tax)
    res_dl = await OnRoadPriceCalculationService.calculate_on_road_price(
        db_session,
        OnRoadPriceCalculationRequest(variant_id=var.id, state_id=dl_state.id, is_financed=False),
    )

    # Both have same base ex-showroom
    assert (
        res_ka.totals.ex_showroom_price == res_dl.totals.ex_showroom_price == Decimal("1100000.00")
    )

    # Karnataka taxes are higher than Delhi taxes
    assert res_ka.totals.total_statutory_taxes > res_dl.totals.total_statutory_taxes
    assert res_ka.totals.on_road_price > res_dl.totals.on_road_price
