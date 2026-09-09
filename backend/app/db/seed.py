import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal, engine
from app.models.base import Base
from app.models.data_source import DataSource
from app.models.finance import Bank, InterestRateSlab, LoanProduct
from app.models.insurance import InsuranceRateRule
from app.models.location import City, RtoOffice, State, TaxSlab
from app.models.pricing import ExShowroomPrice
from app.models.vehicle import (
    CarModel,
    Manufacturer,
    Variant,
    VariantSpecification,
)


async def _run_seed(session: AsyncSession):
    # Check if already seeded
    res = await session.execute(select(Manufacturer))
    if res.scalars().first():
        print("Database already contains data, skipping seed.")
        return

    now = datetime.now(timezone.utc)

    # 1. Data Sources
    print("Seeding data sources...")
    src_parivahan = DataSource(
        name="Parivahan Sewa (MoRTH)",
        slug="parivahan-morth",
        provider_type="government",
        base_url="https://parivahan.gov.in",
        description="Ministry of Road Transport and Highways official portal for state motor vehicle taxation, registration, and BH series regulations.",
        is_active=True,
        last_synced_at=now,
    )
    src_irdai = DataSource(
        name="IRDAI Motor Insurance Tariff Board",
        slug="irdai-motor",
        provider_type="government",
        base_url="https://irdai.gov.in",
        description="Insurance Regulatory and Development Authority of India third-party motor insurance fixed tariffs.",
        is_active=True,
        last_synced_at=now,
    )
    src_sbi = DataSource(
        name="State Bank of India Auto Loan Portal",
        slug="sbi-car-loans",
        provider_type="bank",
        base_url="https://sbi.co.in/web/personal-banking/loans/auto-loans",
        description="SBI official interest rate slabs and margin guidelines for retail car loans.",
        is_active=True,
        last_synced_at=now,
    )
    src_oem = DataSource(
        name="OEM Official Price Lists (SIAM)",
        slug="siam-oem-catalog",
        provider_type="oem",
        base_url="https://www.siam.in",
        description="Certified Ex-showroom retail price bulletins directly from auto manufacturers.",
        is_active=True,
        last_synced_at=now,
    )
    session.add_all([src_parivahan, src_irdai, src_sbi, src_oem])
    await session.flush()

    # 2. States & Cities
    print("Seeding Indian states and cities...")
    states_data = [
        ("Delhi", "DL", True),
        ("Maharashtra", "MH", False),
        ("Karnataka", "KA", False),
        ("Tamil Nadu", "TN", False),
        ("Telangana", "TS", False),
        ("Uttar Pradesh", "UP", False),
        ("Haryana", "HR", False),
        ("Gujarat", "GJ", False),
    ]
    state_objs = {}
    for name, code, is_ut in states_data:
        st = State(name=name, code=code, is_ut=is_ut)
        session.add(st)
        await session.flush()
        state_objs[code] = st

    cities_data = [
        ("New Delhi", "new-delhi", "DL", "Tier 1"),
        ("Mumbai", "mumbai", "MH", "Tier 1"),
        ("Pune", "pune", "MH", "Tier 1"),
        ("Bengaluru", "bengaluru", "KA", "Tier 1"),
        ("Chennai", "chennai", "TN", "Tier 1"),
        ("Hyderabad", "hyderabad", "TS", "Tier 1"),
        ("Noida", "noida", "UP", "Tier 1"),
        ("Gurugram", "gurugram", "HR", "Tier 1"),
        ("Ahmedabad", "ahmedabad", "GJ", "Tier 1"),
    ]
    city_objs = {}
    for name, slug, st_code, tier in cities_data:
        ct = City(name=name, slug=slug, state_id=state_objs[st_code].id, tier=tier)
        session.add(ct)
        await session.flush()
        city_objs[slug] = ct

    # 3. Tax Slabs
    print("Seeding state RTO tax slabs...")
    session.add_all([
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Petrol", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("600000"), tax_percent=Decimal("4.00"), cess_percent=Decimal("0.00"), source="Parivahan DL RTO", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Petrol", min_ex_showroom=Decimal("600000"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("7.00"), cess_percent=Decimal("0.00"), source="Parivahan DL RTO", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Petrol", min_ex_showroom=Decimal("1000000"), max_ex_showroom=None, tax_percent=Decimal("10.00"), cess_percent=Decimal("0.00"), source="Parivahan DL RTO", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Diesel", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("8.75"), cess_percent=Decimal("0.00"), source="Parivahan DL RTO", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Diesel", min_ex_showroom=Decimal("1000000"), max_ex_showroom=None, tax_percent=Decimal("12.50"), cess_percent=Decimal("0.00"), source="Parivahan DL RTO", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="CNG", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("4.00"), cess_percent=Decimal("0.00"), source="Parivahan DL RTO", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Electric", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("0.00"), cess_percent=Decimal("0.00"), source="Delhi EV Policy 2020", source_url="https://ev.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Petrol", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("11.00"), cess_percent=Decimal("0.00"), source="Maharashtra Motor Vehicles Dept", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Petrol", min_ex_showroom=Decimal("1000000"), max_ex_showroom=Decimal("2000000"), tax_percent=Decimal("12.00"), cess_percent=Decimal("0.00"), source="Maharashtra Motor Vehicles Dept", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Petrol", min_ex_showroom=Decimal("2000000"), max_ex_showroom=None, tax_percent=Decimal("13.00"), cess_percent=Decimal("0.00"), source="Maharashtra Motor Vehicles Dept", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Diesel", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("13.00"), cess_percent=Decimal("0.00"), source="Maharashtra Motor Vehicles Dept", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Diesel", min_ex_showroom=Decimal("1000000"), max_ex_showroom=None, tax_percent=Decimal("15.00"), cess_percent=Decimal("0.00"), source="Maharashtra Motor Vehicles Dept", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="CNG", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("7.00"), cess_percent=Decimal("0.00"), source="Maharashtra Motor Vehicles Dept", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Electric", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("0.00"), cess_percent=Decimal("0.00"), source="Maharashtra EV Policy", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Petrol", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("500000"), tax_percent=Decimal("13.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Petrol", min_ex_showroom=Decimal("500000"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("14.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Petrol", min_ex_showroom=Decimal("1000000"), max_ex_showroom=Decimal("2000000"), tax_percent=Decimal("17.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Petrol", min_ex_showroom=Decimal("2000000"), max_ex_showroom=None, tax_percent=Decimal("18.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Diesel", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("14.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Diesel", min_ex_showroom=Decimal("1000000"), max_ex_showroom=None, tax_percent=Decimal("18.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Electric", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("0.00"), cess_percent=Decimal("0.00"), source="Karnataka EV Policy", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["TN"].id, fuel_type="Petrol", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("12.00"), cess_percent=Decimal("0.00"), source="Tamil Nadu Transport Dept", source_url="https://tnsta.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["TN"].id, fuel_type="Petrol", min_ex_showroom=Decimal("1000000"), max_ex_showroom=None, tax_percent=Decimal("15.00"), cess_percent=Decimal("0.00"), source="Tamil Nadu Transport Dept", source_url="https://tnsta.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["TN"].id, fuel_type="Diesel", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("15.00"), cess_percent=Decimal("0.00"), source="Tamil Nadu Transport Dept", source_url="https://tnsta.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["TN"].id, fuel_type="Electric", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("0.00"), cess_percent=Decimal("0.00"), source="TN EV Policy", source_url="https://tnsta.gov.in", effective_date=now, last_verified_date=now),
    ])
    await session.flush()

    # 4. Insurance Rate Rules
    print("Seeding insurance rate rules...")
    session.add_all([
        InsuranceRateRule(min_engine_cc=0, max_engine_cc=999, is_ev=False, third_party_3yr_tariff_inr=Decimal("5286.00"), own_damage_base_rate_percent=Decimal("2.60"), zero_dep_addon_percent=Decimal("0.60"), engine_protect_addon_inr=Decimal("1200.00"), description="Cars under 1000cc", source="IRDAI Tariff", source_url="https://irdai.gov.in", effective_date=now, last_verified_date=now),
        InsuranceRateRule(min_engine_cc=1000, max_engine_cc=1500, is_ev=False, third_party_3yr_tariff_inr=Decimal("9534.00"), own_damage_base_rate_percent=Decimal("2.80"), zero_dep_addon_percent=Decimal("0.70"), engine_protect_addon_inr=Decimal("1500.00"), description="Cars 1000cc to 1500cc", source="IRDAI Tariff", source_url="https://irdai.gov.in", effective_date=now, last_verified_date=now),
        InsuranceRateRule(min_engine_cc=1501, max_engine_cc=5000, is_ev=False, third_party_3yr_tariff_inr=Decimal("24596.00"), own_damage_base_rate_percent=Decimal("3.20"), zero_dep_addon_percent=Decimal("0.85"), engine_protect_addon_inr=Decimal("2000.00"), description="Cars exceeding 1500cc", source="IRDAI Tariff", source_url="https://irdai.gov.in", effective_date=now, last_verified_date=now),
        InsuranceRateRule(min_engine_cc=None, max_engine_cc=None, is_ev=True, third_party_3yr_tariff_inr=Decimal("5543.00"), own_damage_base_rate_percent=Decimal("2.50"), zero_dep_addon_percent=Decimal("0.60"), engine_protect_addon_inr=Decimal("0.00"), description="Electric Vehicles (EV)", source="IRDAI EV Tariff", source_url="https://irdai.gov.in", effective_date=now, last_verified_date=now),
    ])
    await session.flush()

    # 5. Banks & Loan Products
    print("Seeding banks and auto loan schemes...")
    sbi = Bank(name="State Bank of India (SBI)", slug="sbi", bank_type="Public", logo_url="/logos/sbi.svg", is_active=True, source="SBI Bank", source_url="https://sbi.co.in", effective_date=now, last_verified_date=now)
    hdfc = Bank(name="HDFC Bank", slug="hdfc", bank_type="Private", logo_url="/logos/hdfc.svg", is_active=True, source="HDFC Bank", source_url="https://hdfcbank.com", effective_date=now, last_verified_date=now)
    icici = Bank(name="ICICI Bank", slug="icici", bank_type="Private", logo_url="/logos/icici.svg", is_active=True, source="ICICI Bank", source_url="https://icicibank.com", effective_date=now, last_verified_date=now)
    bob = Bank(name="Bank of Baroda", slug="bob", bank_type="Public", logo_url="/logos/bob.svg", is_active=True, source="BOB Bank", source_url="https://bankofbaroda.in", effective_date=now, last_verified_date=now)
    session.add_all([sbi, hdfc, icici, bob])
    await session.flush()

    sbi_prod = LoanProduct(
        bank_id=sbi.id, name="SBI New Car Loan Scheme", slug="sbi-new-car-loan",
        min_loan_amount=Decimal("100000"), max_loan_amount=Decimal("15000000"),
        min_tenure_months=12, max_tenure_months=84, max_ltv_percent=Decimal("90.00"),
        processing_fee_percent=Decimal("0.40"), min_processing_fee=Decimal("1500.00"), max_processing_fee=Decimal("10000.00"),
        description="Financing up to 90% of on-road price with zero prepayment penalty.",
        is_active=True, source="SBI Auto Loan Portal", source_url="https://sbi.co.in", effective_date=now, last_verified_date=now,
    )
    hdfc_prod = LoanProduct(
        bank_id=hdfc.id, name="HDFC Custom-Fit Car Loan", slug="hdfc-custom-car-loan",
        min_loan_amount=Decimal("100000"), max_loan_amount=Decimal("30000000"),
        min_tenure_months=12, max_tenure_months=84, max_ltv_percent=Decimal("90.00"),
        processing_fee_percent=Decimal("0.50"), min_processing_fee=Decimal("2500.00"), max_processing_fee=Decimal("10000.00"),
        description="Instant approval for pre-approved customers with flexible tenures.",
        is_active=True, source="HDFC Bank Portal", source_url="https://hdfcbank.com", effective_date=now, last_verified_date=now,
    )
    session.add_all([sbi_prod, hdfc_prod])
    await session.flush()

    session.add_all([
        InterestRateSlab(loan_product_id=sbi_prod.id, min_cibil_score=800, max_cibil_score=900, min_interest_rate=Decimal("8.65"), max_interest_rate=Decimal("8.80"), default_interest_rate=Decimal("8.65"), is_fixed=False, source="SBI Portal", source_url="https://sbi.co.in", effective_date=now, last_verified_date=now),
        InterestRateSlab(loan_product_id=sbi_prod.id, min_cibil_score=750, max_cibil_score=799, min_interest_rate=Decimal("8.75"), max_interest_rate=Decimal("8.95"), default_interest_rate=Decimal("8.75"), is_fixed=False, source="SBI Portal", source_url="https://sbi.co.in", effective_date=now, last_verified_date=now),
        InterestRateSlab(loan_product_id=sbi_prod.id, min_cibil_score=700, max_cibil_score=749, min_interest_rate=Decimal("9.15"), max_interest_rate=Decimal("9.45"), default_interest_rate=Decimal("9.25"), is_fixed=False, source="SBI Portal", source_url="https://sbi.co.in", effective_date=now, last_verified_date=now),
        InterestRateSlab(loan_product_id=sbi_prod.id, min_cibil_score=300, max_cibil_score=699, min_interest_rate=Decimal("10.25"), max_interest_rate=Decimal("11.50"), default_interest_rate=Decimal("10.50"), is_fixed=False, source="SBI Portal", source_url="https://sbi.co.in", effective_date=now, last_verified_date=now),
        InterestRateSlab(loan_product_id=hdfc_prod.id, min_cibil_score=750, max_cibil_score=900, min_interest_rate=Decimal("8.85"), max_interest_rate=Decimal("9.10"), default_interest_rate=Decimal("8.90"), is_fixed=False, source="HDFC Portal", source_url="https://hdfcbank.com", effective_date=now, last_verified_date=now),
        InterestRateSlab(loan_product_id=hdfc_prod.id, min_cibil_score=300, max_cibil_score=749, min_interest_rate=Decimal("9.35"), max_interest_rate=Decimal("11.75"), default_interest_rate=Decimal("9.50"), is_fixed=False, source="HDFC Portal", source_url="https://hdfcbank.com", effective_date=now, last_verified_date=now),
    ])
    await session.flush()

    # 6. Manufacturers, Models, Variants, Specs & Ex-Showroom Prices
    print("Seeding vehicle catalog...")
    m_tata = Manufacturer(name="Tata Motors", slug="tata-motors", country_of_origin="India", logo_url="/logos/tata.png", is_active=True, source="SIAM", source_url="https://siam.in", effective_date=now, last_verified_date=now)
    m_maruti = Manufacturer(name="Maruti Suzuki", slug="maruti-suzuki", country_of_origin="India", logo_url="/logos/maruti.png", is_active=True, source="SIAM", source_url="https://siam.in", effective_date=now, last_verified_date=now)
    m_hyundai = Manufacturer(name="Hyundai", slug="hyundai", country_of_origin="South Korea", logo_url="/logos/hyundai.png", is_active=True, source="SIAM", source_url="https://siam.in", effective_date=now, last_verified_date=now)
    m_mahindra = Manufacturer(name="Mahindra", slug="mahindra", country_of_origin="India", logo_url="/logos/mahindra.png", is_active=True, source="SIAM", source_url="https://siam.in", effective_date=now, last_verified_date=now)
    m_kia = Manufacturer(name="Kia", slug="kia", country_of_origin="South Korea", logo_url="/logos/kia.png", is_active=True, source="SIAM", source_url="https://siam.in", effective_date=now, last_verified_date=now)
    session.add_all([m_tata, m_maruti, m_hyundai, m_mahindra, m_kia])
    await session.flush()

    mod_nexon = CarModel(manufacturer_id=m_tata.id, name="Nexon", slug="tata-nexon", body_type="SUV", launch_year=2024, description="India's popular 5-star B-NCAP compact SUV.", image_url="https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=800&auto=format&fit=crop&q=60", source="Tata Motors", source_url="https://cars.tatamotors.com", effective_date=now, last_verified_date=now)
    mod_punch = CarModel(manufacturer_id=m_tata.id, name="Punch", slug="tata-punch", body_type="SUV", launch_year=2024, description="Micro-SUV with 5-star safety rating.", image_url="https://images.unsplash.com/photo-1502877338535-766e1452684a?w=800&auto=format&fit=crop&q=60", source="Tata Motors", source_url="https://cars.tatamotors.com", effective_date=now, last_verified_date=now)
    mod_swift = CarModel(manufacturer_id=m_maruti.id, name="Swift", slug="maruti-swift", body_type="Hatchback", launch_year=2024, description="India's highest selling sporty hatchback with Z-series engine.", image_url="https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=800&auto=format&fit=crop&q=60", source="Maruti Suzuki", source_url="https://marutisuzuki.com", effective_date=now, last_verified_date=now)
    mod_brezza = CarModel(manufacturer_id=m_maruti.id, name="Brezza", slug="maruti-brezza", body_type="SUV", launch_year=2024, description="Reliable urban SUV powered by 1.5L Smart Hybrid engine.", image_url="https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=800&auto=format&fit=crop&q=60", source="Maruti Suzuki", source_url="https://marutisuzuki.com", effective_date=now, last_verified_date=now)
    mod_creta = CarModel(manufacturer_id=m_hyundai.id, name="Creta", slug="hyundai-creta", body_type="SUV", launch_year=2024, description="Segment-leading mid-size SUV with ADAS Level 2.", image_url="https://images.unsplash.com/photo-1541348263662-e0c8de4259ba?w=800&auto=format&fit=crop&q=60", source="Hyundai India", source_url="https://hyundai.com/in", effective_date=now, last_verified_date=now)
    mod_i20 = CarModel(manufacturer_id=m_hyundai.id, name="i20", slug="hyundai-i20", body_type="Hatchback", launch_year=2024, description="Premium European-styled hatchback with connected tech.", image_url="https://images.unsplash.com/photo-1580273916550-e323be2ae537?w=800&auto=format&fit=crop&q=60", source="Hyundai India", source_url="https://hyundai.com/in", effective_date=now, last_verified_date=now)
    mod_thar = CarModel(manufacturer_id=m_mahindra.id, name="Thar", slug="mahindra-thar", body_type="SUV", launch_year=2024, description="Iconic 4x4 lifestyle off-roader with aggressive road presence.", image_url="https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=800&auto=format&fit=crop&q=60", source="Mahindra Auto", source_url="https://auto.mahindra.com", effective_date=now, last_verified_date=now)
    mod_xuv700 = CarModel(manufacturer_id=m_mahindra.id, name="XUV700", slug="mahindra-xuv700", body_type="SUV", launch_year=2024, description="Flagship 7-seater SUV with class-leading performance and ADAS.", image_url="https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=800&auto=format&fit=crop&q=60", source="Mahindra Auto", source_url="https://auto.mahindra.com", effective_date=now, last_verified_date=now)
    mod_sonet = CarModel(manufacturer_id=m_kia.id, name="Sonet", slug="kia-sonet", body_type="SUV", launch_year=2024, description="Feature-loaded compact SUV with ventilated seats and 360-cam.", image_url="https://images.unsplash.com/photo-1542282088-72c9c27ed0cd?w=800&auto=format&fit=crop&q=60", source="Kia India", source_url="https://kia.com/in", effective_date=now, last_verified_date=now)
    session.add_all([mod_nexon, mod_punch, mod_swift, mod_brezza, mod_creta, mod_i20, mod_thar, mod_xuv700, mod_sonet])
    await session.flush()

    variants_catalog = [
        (mod_swift, "Swift LXi 1.2 MT", "swift-lxi-mt", "Base", "Petrol", "Manual", 5, Decimal("649000.00"), 1197, Decimal("24.80"), 4, 6, None),
        (mod_swift, "Swift VXi 1.2 AMT", "swift-vxi-amt", "Mid", "Petrol", "AMT", 5, Decimal("779500.00"), 1197, Decimal("25.75"), 4, 6, None),
        (mod_swift, "Swift ZXi Plus AMT", "swift-zxi-plus-amt", "Top", "Petrol", "AMT", 5, Decimal("959500.00"), 1197, Decimal("25.75"), 4, 6, None),
        (mod_swift, "Swift VXi 1.2 CNG", "swift-vxi-cng", "Mid", "CNG", "Manual", 5, Decimal("819500.00"), 1197, Decimal("32.85"), 4, 6, None),
        (mod_punch, "Punch Pure 1.2 MT", "punch-pure-mt", "Base", "Petrol", "Manual", 5, Decimal("612900.00"), 1199, Decimal("20.09"), 5, 2, None),
        (mod_punch, "Punch Adventure Rhythm AMT", "punch-adv-rhythm-amt", "Mid", "Petrol", "AMT", 5, Decimal("784900.00"), 1199, Decimal("18.80"), 5, 2, None),
        (mod_punch, "Punch Accomplished Dazzle Sunroof CNG", "punch-acc-cng", "Top", "CNG", "Manual", 5, Decimal("984900.00"), 1199, Decimal("26.99"), 5, 2, None),
        (mod_punch, "Punch EV Long Range Empowered", "punch-ev-empowered", "Top", "Electric", "Automatic", 5, Decimal("1329000.00"), None, Decimal("14.00"), 5, 6, Decimal("35.0")),
        (mod_nexon, "Nexon Smart 1.2 Petrol MT", "nexon-smart-petrol-mt", "Base", "Petrol", "Manual", 5, Decimal("799990.00"), 1199, Decimal("17.44"), 5, 6, None),
        (mod_nexon, "Nexon Creative Plus 1.2 Petrol AMT", "nexon-creative-plus-amt", "Mid", "Petrol", "AMT", 5, Decimal("1169990.00"), 1199, Decimal("17.18"), 5, 6, None),
        (mod_nexon, "Nexon Fearless Plus 1.5 Diesel MT", "nexon-fearless-plus-diesel", "Top", "Diesel", "Manual", 5, Decimal("1349990.00"), 1497, Decimal("23.23"), 5, 6, None),
        (mod_nexon, "Nexon EV Empowered Plus 45 kWh", "nexon-ev-empowered-plus-45", "Top", "Electric", "Automatic", 5, Decimal("1699000.00"), None, Decimal("15.50"), 5, 6, Decimal("45.0")),
        (mod_brezza, "Brezza LXi 1.5 MT", "brezza-lxi-mt", "Base", "Petrol", "Manual", 5, Decimal("834000.00"), 1462, Decimal("17.38"), 4, 2, None),
        (mod_brezza, "Brezza ZXi 1.5 AT Sunroof", "brezza-zxi-at", "Mid", "Petrol", "Automatic", 5, Decimal("1254500.00"), 1462, Decimal("19.80"), 4, 6, None),
        (mod_brezza, "Brezza ZXi Plus 1.5 AT Dual Tone", "brezza-zxi-plus-at", "Top", "Petrol", "Automatic", 5, Decimal("1398000.00"), 1462, Decimal("19.80"), 4, 6, None),
        (mod_brezza, "Brezza VXi 1.5 CNG", "brezza-vxi-cng", "Mid", "CNG", "Manual", 5, Decimal("1064500.00"), 1462, Decimal("25.51"), 4, 2, None),
        (mod_i20, "i20 Era 1.2 Petrol MT", "i20-era-mt", "Base", "Petrol", "Manual", 5, Decimal("704400.00"), 1197, Decimal("16.00"), 3, 6, None),
        (mod_i20, "i20 Sportz 1.2 IVT Automatic", "i20-sportz-ivt", "Mid", "Petrol", "CVT", 5, Decimal("942600.00"), 1197, Decimal("16.00"), 3, 6, None),
        (mod_i20, "i20 Asta(O) 1.2 MT Sunroof", "i20-asta-o-mt", "Top", "Petrol", "Manual", 5, Decimal("1000600.00"), 1197, Decimal("16.00"), 3, 6, None),
        (mod_sonet, "Sonet HTE 1.2 Petrol MT", "sonet-hte-mt", "Base", "Petrol", "Manual", 5, Decimal("799000.00"), 1197, Decimal("18.83"), 3, 6, None),
        (mod_sonet, "Sonet HTX 1.0 Turbo Petrol DCT", "sonet-htx-dct", "Mid", "Petrol", "DCT", 5, Decimal("1229000.00"), 998, Decimal("19.20"), 3, 6, None),
        (mod_sonet, "Sonet GTX Plus 1.5 Diesel AT", "sonet-gtx-plus-diesel-at", "Top", "Diesel", "Automatic", 5, Decimal("1575000.00"), 1493, Decimal("18.60"), 3, 6, None),
        (mod_thar, "Thar AX(O) 1.5 Diesel RWD MT", "thar-axo-rwd-diesel", "Mid", "Diesel", "Manual", 4, Decimal("1135000.00"), 1497, Decimal("15.20"), 4, 2, None),
        (mod_thar, "Thar LX 2.0 Petrol 4x4 AT Hard Top", "thar-lx-4x4-petrol-at", "Top", "Petrol", "Automatic", 4, Decimal("1760000.00"), 1997, Decimal("11.50"), 4, 2, None),
        (mod_creta, "Creta E 1.5 Petrol MT", "creta-e-petrol-mt", "Base", "Petrol", "Manual", 5, Decimal("1099900.00"), 1497, Decimal("17.40"), 3, 6, None),
        (mod_creta, "Creta SX 1.5 Petrol IVT", "creta-sx-petrol-ivt", "Mid", "Petrol", "CVT", 5, Decimal("1705800.00"), 1497, Decimal("17.70"), 3, 6, None),
        (mod_creta, "Creta SX(O) 1.5 Turbo Petrol DCT ADAS", "creta-sxo-turbo-dct", "Top", "Petrol", "DCT", 5, Decimal("2000000.00"), 1482, Decimal("18.40"), 3, 6, None),
        (mod_creta, "Creta SX(O) 1.5 Diesel AT", "creta-sxo-diesel-at", "Top", "Diesel", "Automatic", 5, Decimal("2014800.00"), 1493, Decimal("19.10"), 3, 6, None),
        (mod_xuv700, "XUV700 MX 2.0 Turbo Petrol MT 5-Str", "xuv700-mx-petrol-mt", "Base", "Petrol", "Manual", 5, Decimal("1399000.00"), 1999, Decimal("13.00"), 5, 2, None),
        (mod_xuv700, "XUV700 AX5 2.2 Diesel AT 7-Str", "xuv700-ax5-diesel-at", "Mid", "Diesel", "Automatic", 7, Decimal("1979000.00"), 2198, Decimal("14.50"), 5, 4, None),
        (mod_xuv700, "XUV700 AX7L 2.2 Diesel AWD AT 7-Str", "xuv700-ax7l-diesel-awd-at", "Top", "Diesel", "Automatic", 7, Decimal("2699000.00"), 2198, Decimal("13.80"), 5, 7, None),
    ]

    for model, vname, vslug, trim, fuel, trans, seats, price, eng_cc, arai_kmpl, safety, airbags, ev_kwh in variants_catalog:
        var = Variant(
            model_id=model.id,
            name=vname,
            slug=vslug,
            trim_level=trim,
            fuel_type=fuel,
            transmission=trans,
            seating_capacity=seats,
            is_active=True,
            source="OEM Catalog",
            source_url="https://siam.in",
            effective_date=now,
            last_verified_date=now,
        )
        session.add(var)
        await session.flush()

        spec = VariantSpecification(
            variant_id=var.id,
            engine_displacement_cc=eng_cc,
            battery_capacity_kwh=ev_kwh,
            arai_mileage_kmpl=arai_kmpl,
            airbags_count=airbags,
            safety_rating_stars=safety,
            source="OEM Specification Sheet",
            source_url="https://siam.in",
            effective_date=now,
            last_verified_date=now,
        )
        session.add(spec)

        ex_price = ExShowroomPrice(
            variant_id=var.id,
            state_id=None,
            city_id=None,
            price_inr=price,
            is_current=True,
            source="SIAM Price List 2024",
            source_url="https://siam.in",
            effective_date=now,
            last_verified_date=now,
        )
        session.add(ex_price)

    await session.commit()
    print("CarAfford seed successfully completed!")


async def seed_database(session: Optional[AsyncSession] = None):
    if session is not None:
        await _run_seed(session)
    else:
        async with AsyncSessionLocal() as db_sess:
            await _run_seed(db_sess)


if __name__ == "__main__":
    asyncio.run(seed_database())
