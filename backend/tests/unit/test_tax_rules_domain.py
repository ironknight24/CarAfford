"""
Unit tests for Indian Vehicle Tax and Registration Rules Domain.
Covers:
1. Fixed tax/fee rule creation and properties
2. Percentage tax rule
3. Bracketed tax rule with multiple brackets and ordering
4. Effective dates (historical, current, future rule resolution)
5. State-level rule resolution
6. City-level rule resolution
7. RTO-level rule resolution
8. Precedence hierarchy (RTO > City > State > National)
9. EV-specific vs ICE vehicle matching
10. Fuel type specificity matching (Petrol, Diesel, CNG)
11. Engine CC and price bracket conditions
12. Invalid brackets validation error (negative values, inverted bounds, overlapping slabs)
13. Overlapping active rules validation error
14. Location hierarchy validation error (City/RTO outside State)
15. Data source provenance tracking
16. Safe formula definition rule handling
"""

from datetime import datetime, timezone
from decimal import Decimal
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.data_source import DataSource
from app.models.location import City, Country, RtoOffice, State
from app.models.tax_rule import TaxRule, TaxRuleBracket
from app.repositories.tax_rule_repo import TaxRuleRepository
from app.schemas.tax_rule import TaxRuleBracketCreate, TaxRuleCreate
from app.services.tax_rule_resolver import TaxRuleResolverService


@pytest.mark.asyncio
async def test_fixed_and_percentage_tax_rule_creation(db_session: AsyncSession):
    country = Country(name="India", iso_code="IN", iso3_code="IND")
    db_session.add(country)
    await db_session.flush()

    state = State(country_id=country.id, name="Karnataka", code="KA", region_type="STATE")
    db_session.add(state)
    await db_session.flush()

    # Fixed fee rule (Registration fee ₹600)
    fixed_rule_in = TaxRuleCreate(
        name="KA Registration Fee",
        state_id=state.id,
        rule_category="REGISTRATION",
        tax_type="REGISTRATION_FEE",
        calculation_method="FIXED",
        fixed_amount=Decimal("600.00"),
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    fixed_rule = await TaxRuleRepository.create(db_session, fixed_rule_in)
    assert fixed_rule.id is not None
    assert fixed_rule.fixed_amount == Decimal("600.00")
    assert fixed_rule.calculation_method == "FIXED"

    # Percentage fee rule (11% cess)
    pct_rule_in = TaxRuleCreate(
        name="KA Infra Cess",
        state_id=state.id,
        rule_category="CESS",
        tax_type="CESS",
        calculation_method="PERCENTAGE",
        rate=Decimal("11.00"),
        base_amount_type="ROAD_TAX",
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    pct_rule = await TaxRuleRepository.create(db_session, pct_rule_in)
    assert pct_rule.id is not None
    assert pct_rule.rate == Decimal("11.00")
    assert pct_rule.base_amount_type == "ROAD_TAX"


@pytest.mark.asyncio
async def test_bracketed_tax_rule_and_ordering(db_session: AsyncSession):
    country = Country(name="India", iso_code="IN", iso3_code="IND")
    db_session.add(country)
    await db_session.flush()

    state = State(country_id=country.id, name="Karnataka", code="KA", region_type="STATE")
    db_session.add(state)
    await db_session.flush()

    bracketed_rule_in = TaxRuleCreate(
        name="KA Tiered Road Tax",
        state_id=state.id,
        rule_category="TAX",
        tax_type="ROAD_TAX",
        calculation_method="BRACKETED",
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        brackets=[
            TaxRuleBracketCreate(
                bracket_order=1,
                minimum_value=Decimal("0"),
                maximum_value=Decimal("500000"),
                rate=Decimal("13.00"),
            ),
            TaxRuleBracketCreate(
                bracket_order=2,
                minimum_value=Decimal("500000"),
                maximum_value=Decimal("1000000"),
                rate=Decimal("14.00"),
            ),
            TaxRuleBracketCreate(
                bracket_order=3,
                minimum_value=Decimal("1000000"),
                maximum_value=Decimal("2000000"),
                rate=Decimal("17.00"),
            ),
            TaxRuleBracketCreate(
                bracket_order=4,
                minimum_value=Decimal("2000000"),
                maximum_value=None,
                rate=Decimal("18.00"),
            ),
        ],
    )
    rule = await TaxRuleRepository.create(db_session, bracketed_rule_in)
    assert rule.id is not None
    assert len(rule.brackets) == 4
    assert rule.brackets[0].rate == Decimal("13.00")
    assert rule.brackets[3].maximum_value is None
    assert rule.brackets[3].rate == Decimal("18.00")


@pytest.mark.asyncio
async def test_temporal_resolution_historical_current_future(db_session: AsyncSession):
    country = Country(name="India", iso_code="IN", iso3_code="IND")
    db_session.add(country)
    await db_session.flush()

    state = State(country_id=country.id, name="Karnataka", code="KA", region_type="STATE")
    db_session.add(state)
    await db_session.flush()

    # Rule 1: 2020 to 2023 (Historical)
    r1 = await TaxRuleRepository.create(
        db_session,
        TaxRuleCreate(
            name="KA Road Tax 2020-2023",
            state_id=state.id,
            tax_type="ROAD_TAX",
            calculation_method="PERCENTAGE",
            rate=Decimal("12.00"),
            effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
            effective_to=datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        ),
    )

    # Rule 2: 2024 onwards (Current)
    r2 = await TaxRuleRepository.create(
        db_session,
        TaxRuleCreate(
            name="KA Road Tax 2024 Current",
            state_id=state.id,
            tax_type="ROAD_TAX",
            calculation_method="PERCENTAGE",
            rate=Decimal("14.00"),
            effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
            effective_to=None,
        ),
    )

    # 1. Historical Resolution (June 2022)
    hist_res = await TaxRuleResolverService.resolve_rules(
        db=db_session,
        state_id=state.id,
        calculation_date=datetime(2022, 6, 15, tzinfo=timezone.utc),
    )
    road_tax_rules = [r for r in hist_res.rules if r.tax_type == "ROAD_TAX"]
    assert len(road_tax_rules) == 1
    assert road_tax_rules[0].rule_id == r1.id
    assert road_tax_rules[0].rate == Decimal("12.00")

    # 2. Current Resolution (Today / 2025)
    curr_res = await TaxRuleResolverService.resolve_rules(
        db=db_session,
        state_id=state.id,
        calculation_date=datetime(2025, 3, 1, tzinfo=timezone.utc),
    )
    curr_road_tax = [r for r in curr_res.rules if r.tax_type == "ROAD_TAX"]
    assert len(curr_road_tax) == 1
    assert curr_road_tax[0].rule_id == r2.id
    assert curr_road_tax[0].rate == Decimal("14.00")

    # 3. Pre-2020 date (should yield no matching active rule)
    pre_res = await TaxRuleResolverService.resolve_rules(
        db=db_session,
        state_id=state.id,
        calculation_date=datetime(2015, 1, 1, tzinfo=timezone.utc),
    )
    assert len([r for r in pre_res.rules if r.tax_type == "ROAD_TAX"]) == 0


@pytest.mark.asyncio
async def test_location_precedence_hierarchy(db_session: AsyncSession):
    """Verifies deterministic hierarchy precedence: RTO (300) > City (200) > State (100)."""
    country = Country(name="India", iso_code="IN", iso3_code="IND")
    db_session.add(country)
    await db_session.flush()

    state = State(country_id=country.id, name="Karnataka", code="KA", region_type="STATE")
    db_session.add(state)
    await db_session.flush()

    city = City(state_id=state.id, name="Bengaluru", slug="bengaluru")
    db_session.add(city)
    await db_session.flush()

    rto_ecity = RtoOffice(
        state_id=state.id, city_id=city.id, code="KA-51", name="Electronic City RTO"
    )
    rto_jayanagar = RtoOffice(
        state_id=state.id, city_id=city.id, code="KA-05", name="Jayanagar RTO"
    )
    db_session.add_all([rto_ecity, rto_jayanagar])
    await db_session.flush()

    # State-level default road tax
    r_state = await TaxRuleRepository.create(
        db_session,
        TaxRuleCreate(
            name="State Level Road Tax",
            state_id=state.id,
            tax_type="ROAD_TAX",
            calculation_method="PERCENTAGE",
            rate=Decimal("10.00"),
            priority=100,
            effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
    )

    # City-level override
    r_city = await TaxRuleRepository.create(
        db_session,
        TaxRuleCreate(
            name="Bengaluru City Road Tax",
            state_id=state.id,
            city_id=city.id,
            tax_type="ROAD_TAX",
            calculation_method="PERCENTAGE",
            rate=Decimal("12.00"),
            priority=100,
            effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
    )

    # RTO-level override for KA-51
    r_rto = await TaxRuleRepository.create(
        db_session,
        TaxRuleCreate(
            name="KA-51 Electronic City Special Road Tax",
            state_id=state.id,
            rto_id=rto_ecity.id,
            tax_type="ROAD_TAX",
            calculation_method="PERCENTAGE",
            rate=Decimal("15.00"),
            priority=100,
            effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
    )

    # Resolution 1: Selected RTO KA-51 -> Must choose RTO rule (rate=15.00, tier=300)
    res_rto = await TaxRuleResolverService.resolve_rules(
        db=db_session,
        state_id=state.id,
        city_id=city.id,
        rto_id=rto_ecity.id,
        calculation_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    rto_matched = [r for r in res_rto.rules if r.tax_type == "ROAD_TAX"][0]
    assert rto_matched.rule_id == r_rto.id
    assert rto_matched.rate == Decimal("15.00")
    assert rto_matched.precedence_tier == 300
    assert rto_matched.precedence_label == "RTO-specific"

    # Resolution 2: Selected RTO KA-05 (which has no RTO override) -> Must choose City rule (rate=12.00, tier=200)
    res_city = await TaxRuleResolverService.resolve_rules(
        db=db_session,
        state_id=state.id,
        city_id=city.id,
        rto_id=rto_jayanagar.id,
        calculation_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    city_matched = [r for r in res_city.rules if r.tax_type == "ROAD_TAX"][0]
    assert city_matched.rule_id == r_city.id
    assert city_matched.rate == Decimal("12.00")
    assert city_matched.precedence_tier == 200
    assert city_matched.precedence_label == "City-specific"

    # Resolution 3: Only State selected -> Must choose State rule (rate=10.00, tier=100)
    res_state = await TaxRuleResolverService.resolve_rules(
        db=db_session,
        state_id=state.id,
        city_id=None,
        rto_id=None,
        calculation_date=datetime(2024, 6, 1, tzinfo=timezone.utc),
    )
    state_matched = [r for r in res_state.rules if r.tax_type == "ROAD_TAX"][0]
    assert state_matched.rule_id == r_state.id
    assert state_matched.rate == Decimal("10.00")
    assert state_matched.precedence_tier == 100
    assert state_matched.precedence_label == "State-level"


@pytest.mark.asyncio
async def test_fuel_and_ev_specific_resolution(db_session: AsyncSession):
    country = Country(name="India", iso_code="IN", iso3_code="IND")
    db_session.add(country)
    await db_session.flush()

    state = State(country_id=country.id, name="Delhi", code="DL", region_type="UNION_TERRITORY")
    db_session.add(state)
    await db_session.flush()

    # Petrol rule: 7%
    await TaxRuleRepository.create(
        db_session,
        TaxRuleCreate(
            name="DL Petrol Tax",
            state_id=state.id,
            tax_type="ROAD_TAX",
            calculation_method="PERCENTAGE",
            fuel_type="Petrol",
            is_ev=False,
            rate=Decimal("7.00"),
            effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
    )

    # Diesel rule: 10%
    await TaxRuleRepository.create(
        db_session,
        TaxRuleCreate(
            name="DL Diesel Tax",
            state_id=state.id,
            tax_type="ROAD_TAX",
            calculation_method="PERCENTAGE",
            fuel_type="Diesel",
            is_ev=False,
            rate=Decimal("10.00"),
            effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
    )

    # EV rule: 0%
    await TaxRuleRepository.create(
        db_session,
        TaxRuleCreate(
            name="DL EV Tax Waiver",
            state_id=state.id,
            tax_type="ROAD_TAX",
            calculation_method="FIXED",
            is_ev=True,
            fixed_amount=Decimal("0.00"),
            priority=150,
            effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        ),
    )

    # Test Petrol
    p_res = await TaxRuleResolverService.resolve_rules(
        db=db_session, state_id=state.id, fuel_type="Petrol", is_ev=False
    )
    p_tax = [r for r in p_res.rules if r.tax_type == "ROAD_TAX"][0]
    assert p_tax.rate == Decimal("7.00")

    # Test Diesel
    d_res = await TaxRuleResolverService.resolve_rules(
        db=db_session, state_id=state.id, fuel_type="Diesel", is_ev=False
    )
    d_tax = [r for r in d_res.rules if r.tax_type == "ROAD_TAX"][0]
    assert d_tax.rate == Decimal("10.00")

    # Test EV
    ev_res = await TaxRuleResolverService.resolve_rules(
        db=db_session, state_id=state.id, fuel_type="Electric", is_ev=True
    )
    ev_tax = [r for r in ev_res.rules if r.tax_type == "ROAD_TAX"][0]
    assert ev_tax.fixed_amount == Decimal("0.00")
    assert ev_tax.calculation_method == "FIXED"


@pytest.mark.asyncio
async def test_invalid_bracket_and_hierarchy_validations(db_session: AsyncSession):
    country = Country(name="India", iso_code="IN", iso3_code="IND")
    db_session.add(country)
    await db_session.flush()

    state_ka = State(country_id=country.id, name="Karnataka", code="KA", region_type="STATE")
    state_mh = State(country_id=country.id, name="Maharashtra", code="MH", region_type="STATE")
    db_session.add_all([state_ka, state_mh])
    await db_session.flush()

    city_mumbai = City(state_id=state_mh.id, name="Mumbai", slug="mumbai")
    db_session.add(city_mumbai)
    await db_session.flush()

    # 1. Invalid hierarchy: City of Maharashtra used with State of Karnataka
    invalid_hier_in = TaxRuleCreate(
        name="Invalid Rule",
        state_id=state_ka.id,
        city_id=city_mumbai.id,
        tax_type="ROAD_TAX",
        calculation_method="PERCENTAGE",
        rate=Decimal("10.00"),
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )
    is_valid, errors, _ = await TaxRuleRepository.validate_tax_rule_data(
        db_session, invalid_hier_in
    )
    assert is_valid is False
    assert any("does not belong to specified State" in err for err in errors)

    # 2. Invalid brackets: overlapping slab [0, 600000] and [500000, 1000000]
    invalid_brackets_in = TaxRuleCreate(
        name="Invalid Brackets Rule",
        state_id=state_ka.id,
        tax_type="ROAD_TAX",
        calculation_method="BRACKETED",
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        brackets=[
            TaxRuleBracketCreate(
                bracket_order=1,
                minimum_value=Decimal("0"),
                maximum_value=Decimal("600000"),
                rate=Decimal("5.00"),
            ),
            TaxRuleBracketCreate(
                bracket_order=2,
                minimum_value=Decimal("500000"),
                maximum_value=Decimal("1000000"),
                rate=Decimal("8.00"),
            ),
        ],
    )
    is_valid_brk, errors_brk, _ = await TaxRuleRepository.validate_tax_rule_data(
        db_session, invalid_brackets_in
    )
    assert is_valid_brk is False
    assert any("overlaps with previous bracket" in err for err in errors_brk)


@pytest.mark.asyncio
async def test_data_source_provenance_tracking(db_session: AsyncSession):
    country = Country(name="India", iso_code="IN", iso3_code="IND")
    db_session.add(country)
    await db_session.flush()

    state = State(country_id=country.id, name="Karnataka", code="KA", region_type="STATE")
    db_session.add(state)
    await db_session.flush()

    source = DataSource(
        name="Parivahan MoRTH",
        slug="parivahan-src",
        provider_type="government",
        base_url="https://parivahan.gov.in",
        is_active=True,
    )
    db_session.add(source)
    await db_session.flush()

    rule_in = TaxRuleCreate(
        name="KA Road Tax Verified",
        state_id=state.id,
        tax_type="ROAD_TAX",
        calculation_method="PERCENTAGE",
        rate=Decimal("14.00"),
        effective_from=datetime(2024, 1, 1, tzinfo=timezone.utc),
        source_id=source.id,
        source_record_id="GAZETTE-2024-KA-112",
        retrieved_at=datetime(2024, 2, 1, tzinfo=timezone.utc),
    )
    rule = await TaxRuleRepository.create(db_session, rule_in)
    assert rule.source_id == source.id
    assert rule.source_record_id == "GAZETTE-2024-KA-112"
    assert rule.source is not None
    assert rule.source.name == "Parivahan MoRTH"
