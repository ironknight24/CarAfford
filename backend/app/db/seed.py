import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models.data_source import DataSource
from app.models.finance import Bank, InterestRateSlab, LoanProduct
from app.models.insurance import InsuranceRateRule
from app.models.location import City, State, TaxSlab
from app.models.pricing import ExShowroomPrice, PriceHistory, VehiclePrice
from app.models.vehicle import (
    CarModel,
    Manufacturer,
    Variant,
    VariantSpecification,
    VehicleMedia,
)


async def _run_seed(session: AsyncSession):
    """Seeds realistic demonstration data for Indian car manufacturers, models, variants,
    historical ex-showroom prices, state RTO tax slabs, and bank loans.

    NOTE: All data populated here is strictly DEMO / SEED data intended for development,
    testing, and architectural demonstration purposes.
    """
    # Check if already seeded
    res = await session.execute(select(Manufacturer))
    if res.scalars().first():
        print("Database already contains data, skipping seed.")
        return

    now = datetime.now(timezone.utc)
    base_past_date = datetime(2024, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    price_change_date = datetime(2024, 5, 1, 0, 0, 0, tzinfo=timezone.utc)

    # =========================================================================
    # 1. DATA SOURCES
    # =========================================================================
    print("1/6 Seeding data sources...")
    src_siam = DataSource(
        name="Society of Indian Automobile Manufacturers (SIAM)",
        slug="siam-oem-catalog",
        provider_type="oem",
        base_url="https://www.siam.in",
        description="Certified Ex-showroom retail price bulletins directly from auto manufacturers.",
        is_active=True,
        last_synced_at=now,
    )
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
    session.add_all([src_siam, src_parivahan, src_irdai, src_sbi])
    await session.flush()

    # =========================================================================
    # 2. MANUFACTURERS (10 Leading Indian Market OEMs)
    # =========================================================================
    print("2/6 Seeding 10 manufacturers...")
    manufacturers_data = [
        ("Tata Motors", "tata-motors", "India", "/logos/tata.png"),
        ("Maruti Suzuki", "maruti-suzuki", "India", "/logos/maruti.png"),
        ("Hyundai", "hyundai", "South Korea", "/logos/hyundai.png"),
        ("Mahindra", "mahindra", "India", "/logos/mahindra.png"),
        ("Kia", "kia", "South Korea", "/logos/kia.png"),
        ("Toyota", "toyota", "Japan", "/logos/toyota.png"),
        ("Honda", "honda", "Japan", "/logos/honda.png"),
        ("Volkswagen", "volkswagen", "Germany", "/logos/volkswagen.png"),
        ("Skoda", "skoda", "Czech Republic", "/logos/skoda.png"),
        ("MG Motor", "mg-motor", "United Kingdom", "/logos/mg.png"),
    ]

    mfg_map = {}
    for name, slug, country, logo in manufacturers_data:
        mfg = Manufacturer(
            name=name,
            slug=slug,
            country=country,
            active=True,
            logo_url=logo,
            source="SIAM OEM Catalog",
            source_url="https://siam.in",
            effective_date=now,
            last_verified_date=now,
        )
        session.add(mfg)
        await session.flush()
        mfg_map[slug] = mfg

    # =========================================================================
    # 3. CAR MODELS (~20 Models across Segments)
    # =========================================================================
    print("3/6 Seeding ~20 car models across segments...")
    models_data = [
        # (mfg_slug, name, slug, body_type, segment, launch_year, launch_date, disc_date, active, image_url)
        # Tata
        ("tata-motors", "Nexon", "tata-nexon", "SUV", "Compact SUV", 2024, date(2023, 9, 14), None, True, "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=800"),
        ("tata-motors", "Punch", "tata-punch", "SUV", "Micro SUV", 2024, date(2021, 10, 18), None, True, "https://images.unsplash.com/photo-1502877338535-766e1452684a?w=800"),
        ("tata-motors", "Harrier", "tata-harrier", "SUV", "Mid-Size SUV", 2024, date(2019, 1, 23), None, True, "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=800"),
        ("tata-motors", "Tiago", "tata-tiago", "Hatchback", "A-Segment", 2024, date(2016, 4, 6), None, True, "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=800"),
        # Maruti
        ("maruti-suzuki", "Swift", "maruti-swift", "Hatchback", "B-Segment", 2024, date(2024, 5, 9), None, True, "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=800"),
        ("maruti-suzuki", "Brezza", "maruti-brezza", "SUV", "Compact SUV", 2024, date(2022, 6, 30), None, True, "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=800"),
        ("maruti-suzuki", "Grand Vitara", "maruti-grand-vitara", "SUV", "Mid-Size SUV", 2024, date(2022, 9, 26), None, True, "https://images.unsplash.com/photo-1541348263662-e0c8de4259ba?w=800"),
        ("maruti-suzuki", "Ertiga", "maruti-ertiga", "MUV", "Compact MPV", 2024, date(2018, 11, 21), None, True, "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=800"),
        # Hyundai
        ("hyundai", "Creta", "hyundai-creta", "SUV", "Mid-Size SUV", 2024, date(2024, 1, 16), None, True, "https://images.unsplash.com/photo-1541348263662-e0c8de4259ba?w=800"),
        ("hyundai", "i20", "hyundai-i20", "Hatchback", "Premium Hatchback", 2024, date(2020, 11, 5), None, True, "https://images.unsplash.com/photo-1580273916550-e323be2ae537?w=800"),
        ("hyundai", "Verna", "hyundai-verna", "Sedan", "C-Segment Sedan", 2024, date(2023, 3, 21), None, True, "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=800"),
        # Mahindra
        ("mahindra", "Thar", "mahindra-thar", "SUV", "Lifestyle 4x4", 2024, date(2020, 10, 2), None, True, "https://images.unsplash.com/photo-1519641471654-76ce0107ad1b?w=800"),
        ("mahindra", "XUV700", "mahindra-xuv700", "SUV", "Mid-Size 7-Seater", 2024, date(2021, 8, 14), None, True, "https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=800"),
        ("mahindra", "Scorpio-N", "mahindra-scorpio-n", "SUV", "D-Segment SUV", 2024, date(2022, 6, 27), None, True, "https://images.unsplash.com/photo-1533473359331-0135ef1b58bf?w=800"),
        # Kia
        ("kia", "Seltos", "kia-seltos", "SUV", "Mid-Size SUV", 2024, date(2023, 7, 21), None, True, "https://images.unsplash.com/photo-1542282088-72c9c27ed0cd?w=800"),
        ("kia", "Sonet", "kia-sonet", "SUV", "Compact SUV", 2024, date(2024, 1, 12), None, True, "https://images.unsplash.com/photo-1542282088-72c9c27ed0cd?w=800"),
        # Toyota
        ("toyota", "Innova Hycross", "toyota-innova-hycross", "MUV", "Premium MPV", 2024, date(2022, 11, 25), None, True, "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=800"),
        ("toyota", "Urban Cruiser Hyryder", "toyota-hyryder", "SUV", "Mid-Size SUV", 2024, date(2022, 9, 9), None, True, "https://images.unsplash.com/photo-1541348263662-e0c8de4259ba?w=800"),
        # Honda
        ("honda", "City", "honda-city", "Sedan", "C-Segment Sedan", 2024, date(2020, 7, 15), None, True, "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=800"),
        # Volkswagen
        ("volkswagen", "Virtus", "volkswagen-virtus", "Sedan", "C-Segment Sedan", 2024, date(2022, 6, 9), None, True, "https://images.unsplash.com/photo-1552519507-da3b142c6e3d?w=800"),
        # Skoda
        ("skoda", "Kushaq", "skoda-kushaq", "SUV", "Compact SUV", 2024, date(2021, 6, 28), None, True, "https://images.unsplash.com/photo-1541348263662-e0c8de4259ba?w=800"),
        # MG Motor
        ("mg-motor", "ZS EV", "mg-zs-ev", "SUV", "Electric SUV", 2024, date(2020, 1, 27), None, True, "https://images.unsplash.com/photo-1502877338535-766e1452684a?w=800"),
    ]

    model_map = {}
    for mfg_slug, name, slug, body_type, segment, yr, l_date, d_date, active, img in models_data:
        mod = CarModel(
            manufacturer_id=mfg_map[mfg_slug].id,
            name=name,
            slug=slug,
            body_type=body_type,
            segment=segment,
            launch_year=yr,
            launch_date=l_date,
            discontinued_date=d_date,
            active=active,
            image_url=img,
            source="SIAM OEM Catalog",
            source_url="https://siam.in",
            effective_date=now,
            last_verified_date=now,
        )
        session.add(mod)
        await session.flush()
        model_map[slug] = mod

    # =========================================================================
    # 4. VARIANTS, SPECIFICATIONS & VEHICLE PRICES
    # =========================================================================
    print("4/6 Seeding variants with engine, battery, and pricing periods...")

    # Format:
    # (model_slug, name, slug, trim, fuel, trans, drive, eng_cc, bhp, nm, seats, mileage, kwh, range, active,
    #  prices_list: [(price, price_type, from_date, to_date, desc)])
    variants_catalog = [
        # --- TATA NEXON (Features MULTIPLE HISTORICAL PRICES for testing) ---
        (
            "tata-nexon", "Nexon Smart 1.2 Petrol 5MT", "nexon-smart-petrol-5mt", "Base", "Petrol", "Manual", "FWD",
            1199, Decimal("118.27"), Decimal("170.00"), 5, Decimal("17.44"), None, None, True,
            [
                # Historical price 1 (Introductory)
                (Decimal("779990.00"), "INTRODUCTORY", datetime(2023, 9, 14, 0, 0, tzinfo=timezone.utc), datetime(2023, 12, 31, 23, 59, tzinfo=timezone.utc)),
                # Historical price 2 (Jan 2024 - Apr 2024)
                (Decimal("799990.00"), "EX_SHOWROOM", datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc), datetime(2024, 4, 30, 23, 59, tzinfo=timezone.utc)),
                # Current active price (May 2024 onwards)
                (Decimal("814990.00"), "EX_SHOWROOM", datetime(2024, 5, 1, 0, 0, tzinfo=timezone.utc), None),
            ]
        ),
        (
            "tata-nexon", "Nexon Creative Plus 1.2 Petrol 6AMT", "nexon-creative-plus-amt", "Mid", "Petrol", "AMT", "FWD",
            1199, Decimal("118.27"), Decimal("170.00"), 5, Decimal("17.18"), None, None, True,
            [(Decimal("1169990.00"), "EX_SHOWROOM", base_past_date, None)],
        ),
        (
            "tata-nexon", "Nexon Fearless Plus 1.5 Diesel 6MT", "nexon-fearless-plus-diesel", "Top", "Diesel", "Manual", "FWD",
            1497, Decimal("113.42"), Decimal("260.00"), 5, Decimal("23.23"), None, None, True,
            [(Decimal("1349990.00"), "EX_SHOWROOM", base_past_date, None)],
        ),
        (
            "tata-nexon", "Nexon EV Empowered Plus 45 kWh", "nexon-ev-empowered-plus-45", "Top", "Electric", "Automatic", "FWD",
            None, Decimal("142.68"), Decimal("215.00"), 5, Decimal("15.50"), Decimal("45.00"), Decimal("489.00"), True,
            [(Decimal("1699000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- TATA PUNCH ---
        (
            "tata-punch", "Punch Pure 1.2 MT", "punch-pure-mt", "Base", "Petrol", "Manual", "FWD",
            1199, Decimal("86.63"), Decimal("115.00"), 5, Decimal("20.09"), None, None, True,
            [(Decimal("612900.00"), "EX_SHOWROOM", base_past_date, None)],
        ),
        (
            "tata-punch", "Punch Accomplished Dazzle Sunroof CNG", "punch-acc-cng", "Top", "CNG", "Manual", "FWD",
            1199, Decimal("72.40"), Decimal("103.00"), 5, Decimal("26.99"), None, None, True,
            [(Decimal("984900.00"), "EX_SHOWROOM", base_past_date, None)],
        ),
        (
            "tata-punch", "Punch EV Long Range Empowered Plus", "punch-ev-empowered-plus", "Top", "Electric", "Automatic", "FWD",
            None, Decimal("120.69"), Decimal("190.00"), 5, Decimal("14.00"), Decimal("35.00"), Decimal("421.00"), True,
            [(Decimal("1329000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- MARUTI SUZUKI SWIFT ---
        (
            "maruti-swift", "Swift LXi 1.2 5MT", "swift-lxi-5mt", "Base", "Petrol", "Manual", "FWD",
            1197, Decimal("80.46"), Decimal("111.70"), 5, Decimal("24.80"), None, None, True,
            [(Decimal("649000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),
        (
            "maruti-swift", "Swift ZXi Plus AMT", "swift-zxi-plus-amt", "Top", "Petrol", "AMT", "FWD",
            1197, Decimal("80.46"), Decimal("111.70"), 5, Decimal("25.75"), None, None, True,
            [(Decimal("959500.00"), "EX_SHOWROOM", base_past_date, None)],
        ),
        (
            "maruti-swift", "Swift VXi 1.2 CNG", "swift-vxi-cng", "Mid", "CNG", "Manual", "FWD",
            1197, Decimal("68.79"), Decimal("101.80"), 5, Decimal("32.85"), None, None, True,
            [(Decimal("819500.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- MARUTI SUZUKI BREZZA ---
        (
            "maruti-brezza", "Brezza LXi 1.5 5MT", "brezza-lxi-5mt", "Base", "Petrol", "Manual", "FWD",
            1462, Decimal("101.64"), Decimal("136.80"), 5, Decimal("17.38"), None, None, True,
            [(Decimal("834000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),
        (
            "maruti-brezza", "Brezza ZXi Plus 1.5 6AT", "brezza-zxi-plus-6at", "Top", "Petrol", "Torque Converter", "FWD",
            1462, Decimal("101.64"), Decimal("136.80"), 5, Decimal("19.80"), None, None, True,
            [(Decimal("1398000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- MARUTI GRAND VITARA ---
        (
            "maruti-grand-vitara", "Grand Vitara Zeta 1.5 Strong Hybrid e-CVT", "grand-vitara-zeta-hybrid", "Mid", "Hybrid", "CVT", "FWD",
            1490, Decimal("114.41"), Decimal("141.00"), 5, Decimal("27.97"), Decimal("0.76"), None, True,
            [(Decimal("1843000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- HYUNDAI CRETA ---
        (
            "hyundai-creta", "Creta EX 1.5 Petrol 6MT", "creta-ex-petrol-6mt", "Base", "Petrol", "Manual", "FWD",
            1497, Decimal("113.42"), Decimal("143.80"), 5, Decimal("17.40"), None, None, True,
            [(Decimal("1221000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),
        (
            "hyundai-creta", "Creta SX(O) 1.5 Turbo Petrol 7DCT", "creta-sxo-turbo-7dct", "Top", "Petrol", "DCT", "FWD",
            1482, Decimal("157.81"), Decimal("253.00"), 5, Decimal("18.40"), None, None, True,
            [(Decimal("2000000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),
        (
            "hyundai-creta", "Creta SX(O) 1.5 Diesel 6AT", "creta-sxo-diesel-6at", "Top", "Diesel", "Torque Converter", "FWD",
            1493, Decimal("114.41"), Decimal("250.00"), 5, Decimal("19.10"), None, None, True,
            [(Decimal("2014800.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- HYUNDAI i20 ---
        (
            "hyundai-i20", "i20 Sportz 1.2 Petrol IVT", "i20-sportz-ivt", "Mid", "Petrol", "CVT", "FWD",
            1197, Decimal("86.82"), Decimal("114.70"), 5, Decimal("16.00"), None, None, True,
            [(Decimal("942600.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- MAHINDRA THAR ---
        (
            "mahindra-thar", "Thar AX(O) 1.5 Diesel RWD 6MT Hard Top", "thar-axo-rwd-diesel", "Mid", "Diesel", "Manual", "RWD",
            1497, Decimal("116.93"), Decimal("300.00"), 4, Decimal("15.20"), None, None, True,
            [(Decimal("1135000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),
        (
            "mahindra-thar", "Thar LX 2.0 Turbo Petrol 4x4 6AT Hard Top", "thar-lx-4x4-petrol-at", "Top", "Petrol", "Torque Converter", "4WD",
            1997, Decimal("150.00"), Decimal("320.00"), 4, Decimal("11.50"), None, None, True,
            [(Decimal("1760000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- MAHINDRA XUV700 ---
        (
            "mahindra-xuv700", "XUV700 AX5 2.0 Turbo Petrol 6MT 5-Str", "xuv700-ax5-petrol-5str", "Mid", "Petrol", "Manual", "FWD",
            1999, Decimal("197.13"), Decimal("380.00"), 5, Decimal("13.00"), None, None, True,
            [(Decimal("1799000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),
        (
            "mahindra-xuv700", "XUV700 AX7L 2.2 Diesel AWD 6AT 7-Str", "xuv700-ax7l-diesel-awd", "Top", "Diesel", "Torque Converter", "AWD",
            2198, Decimal("182.38"), Decimal("450.00"), 7, Decimal("13.80"), None, None, True,
            [(Decimal("2699000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- KIA SONET ---
        (
            "kia-sonet", "Sonet HTX 1.0 Turbo Petrol 7DCT", "sonet-htx-10-turbo-7dct", "Mid", "Petrol", "DCT", "FWD",
            998, Decimal("118.35"), Decimal("172.00"), 5, Decimal("19.20"), None, None, True,
            [(Decimal("1229000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- TOYOTA INNOVA HYCROSS ---
        (
            "toyota-innova-hycross", "Innova Hycross VX 2.0 Strong Hybrid e-CVT 7-Str", "innova-hycross-vx-hybrid", "Mid", "Hybrid", "CVT", "FWD",
            1987, Decimal("183.72"), Decimal("206.00"), 7, Decimal("23.24"), Decimal("1.30"), None, True,
            [(Decimal("2597000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- HONDA CITY ---
        (
            "honda-city", "City V 1.5 i-VTEC 6MT", "honda-city-v-mt", "Mid", "Petrol", "Manual", "FWD",
            1498, Decimal("119.35"), Decimal("145.00"), 5, Decimal("17.80"), None, None, True,
            [(Decimal("1208000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- VOLKSWAGEN VIRTUS ---
        (
            "volkswagen-virtus", "Virtus GT Plus 1.5 TSI DSG", "virtus-gt-plus-15-dsg", "Top", "Petrol", "DCT", "FWD",
            1498, Decimal("147.51"), Decimal("250.00"), 5, Decimal("19.40"), None, None, True,
            [(Decimal("1940000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- SKODA KUSHAQ ---
        (
            "skoda-kushaq", "Kushaq Monte Carlo 1.5 TSI 7DSG", "kushaq-monte-carlo-15-dsg", "Top", "Petrol", "DCT", "FWD",
            1498, Decimal("147.51"), Decimal("250.00"), 5, Decimal("18.86"), None, None, True,
            [(Decimal("1979000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),

        # --- MG ZS EV ---
        (
            "mg-zs-ev", "MG ZS EV Exclusive Plus 50.3 kWh", "mg-zs-ev-exclusive-plus", "Top", "Electric", "Automatic", "FWD",
            None, Decimal("174.33"), Decimal("280.00"), 5, Decimal("14.50"), Decimal("50.30"), Decimal("461.00"), True,
            [(Decimal("2444000.00"), "EX_SHOWROOM", base_past_date, None)],
        ),
    ]

    for (mod_slug, vname, vslug, trim, fuel, trans, drive, eng_cc, bhp, nm, seats, mileage, kwh, rng, active, prices) in variants_catalog:
        model = model_map[mod_slug]
        var = Variant(
            model_id=model.id,
            name=vname,
            slug=vslug,
            trim_level=trim,
            fuel_type=fuel,
            transmission=trans,
            drivetrain=drive,
            engine_cc=eng_cc,
            engine_power_bhp=bhp,
            torque_nm=nm,
            seating_capacity=seats,
            mileage_claimed=mileage,
            battery_capacity_kwh=kwh,
            range_km=rng,
            active=active,
            source="SIAM OEM Catalog",
            source_url="https://siam.in",
            effective_date=now,
            last_verified_date=now,
        )
        session.add(var)
        await session.flush()

        # Seed VehiclePrice records
        for p_amt, p_type, eff_from, eff_to in prices:
            vp = VehiclePrice(
                variant_id=var.id,
                ex_showroom_price=p_amt,
                price_type=p_type,
                effective_from=eff_from,
                effective_to=eff_to,
                source_id=src_siam.id,
                source_record_id=f"OEM-{var.slug}-{p_type}",
                retrieved_at=now,
                created_at=now,
            )
            session.add(vp)

            # Legacy price mirror for backward compatibility
            if eff_to is None or eff_to >= now:
                ex_p = ExShowroomPrice(
                    variant_id=var.id,
                    state_id=None,
                    city_id=None,
                    price_inr=p_amt,
                    is_current=True,
                    source="SIAM OEM Catalog",
                    source_url="https://siam.in",
                    effective_date=now,
                    last_verified_date=now,
                )
                session.add(ex_p)

        # Seed legacy spec if needed
        spec = VariantSpecification(
            variant_id=var.id,
            engine_displacement_cc=eng_cc,
            battery_capacity_kwh=kwh,
            max_power_bhp=bhp,
            max_torque_nm=nm,
            arai_mileage_kmpl=mileage or Decimal("18.00"),
            airbags_count=6,
            safety_rating_stars=5 if "nexon" in vslug or "punch" in vslug or "virtus" in vslug or "kushaq" in vslug or "xuv700" in vslug else 4,
            source="OEM Specification Sheet",
            source_url="https://siam.in",
            effective_date=now,
            last_verified_date=now,
        )
        session.add(spec)

        # Seed VehicleMedia
        media_item = VehicleMedia(
            variant_id=var.id,
            model_id=model.id,
            media_type="IMAGE_EXTERIOR",
            url=model.image_url or "https://images.unsplash.com/photo-1549399542-7e3f8b79c341?w=800",
            alt_text=f"{model.name} {var.name} Exterior Image",
            sort_order=1,
            active=True,
        )
        session.add(media_item)

    await session.flush()

    # =========================================================================
    # 5. STATES, CITIES & RTO TAX SLABS
    # =========================================================================
    print("5/6 Seeding Indian states, cities, and RTO tax slabs...")
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
    for name, slug, st_code, tier in cities_data:
        ct = City(name=name, slug=slug, state_id=state_objs[st_code].id, tier=tier)
        session.add(ct)

    session.add_all([
        # Delhi
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Petrol", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("600000"), tax_percent=Decimal("4.00"), cess_percent=Decimal("0.00"), source="Parivahan DL RTO", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Petrol", min_ex_showroom=Decimal("600000"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("7.00"), cess_percent=Decimal("0.00"), source="Parivahan DL RTO", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Petrol", min_ex_showroom=Decimal("1000000"), max_ex_showroom=None, tax_percent=Decimal("10.00"), cess_percent=Decimal("0.00"), source="Parivahan DL RTO", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Diesel", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("8.75"), cess_percent=Decimal("0.00"), source="Parivahan DL RTO", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Diesel", min_ex_showroom=Decimal("1000000"), max_ex_showroom=None, tax_percent=Decimal("12.50"), cess_percent=Decimal("0.00"), source="Parivahan DL RTO", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="CNG", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("4.00"), cess_percent=Decimal("0.00"), source="Parivahan DL RTO", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Electric", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("0.00"), cess_percent=Decimal("0.00"), source="Delhi EV Policy 2020", source_url="https://ev.delhi.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["DL"].id, fuel_type="Hybrid", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("7.00"), cess_percent=Decimal("0.00"), source="Delhi Transport Dept", source_url="https://transport.delhi.gov.in", effective_date=now, last_verified_date=now),
        # Maharashtra
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Petrol", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("11.00"), cess_percent=Decimal("0.00"), source="Maharashtra Transport Dept", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Petrol", min_ex_showroom=Decimal("1000000"), max_ex_showroom=Decimal("2000000"), tax_percent=Decimal("12.00"), cess_percent=Decimal("0.00"), source="Maharashtra Transport Dept", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Petrol", min_ex_showroom=Decimal("2000000"), max_ex_showroom=None, tax_percent=Decimal("13.00"), cess_percent=Decimal("0.00"), source="Maharashtra Transport Dept", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Diesel", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("13.00"), cess_percent=Decimal("0.00"), source="Maharashtra Transport Dept", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Diesel", min_ex_showroom=Decimal("1000000"), max_ex_showroom=None, tax_percent=Decimal("15.00"), cess_percent=Decimal("0.00"), source="Maharashtra Transport Dept", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Electric", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("0.00"), cess_percent=Decimal("0.00"), source="Maharashtra EV Policy", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["MH"].id, fuel_type="Hybrid", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("11.00"), cess_percent=Decimal("0.00"), source="Maharashtra Transport Dept", source_url="https://transport.maharashtra.gov.in", effective_date=now, last_verified_date=now),
        # Karnataka
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Petrol", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("500000"), tax_percent=Decimal("13.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Petrol", min_ex_showroom=Decimal("500000"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("14.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Petrol", min_ex_showroom=Decimal("1000000"), max_ex_showroom=Decimal("2000000"), tax_percent=Decimal("17.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Petrol", min_ex_showroom=Decimal("2000000"), max_ex_showroom=None, tax_percent=Decimal("18.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Diesel", min_ex_showroom=Decimal("0"), max_ex_showroom=Decimal("1000000"), tax_percent=Decimal("14.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Diesel", min_ex_showroom=Decimal("1000000"), max_ex_showroom=None, tax_percent=Decimal("18.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Electric", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("0.00"), cess_percent=Decimal("0.00"), source="Karnataka EV Policy", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
        TaxSlab(state_id=state_objs["KA"].id, fuel_type="Hybrid", min_ex_showroom=Decimal("0"), max_ex_showroom=None, tax_percent=Decimal("14.00"), cess_percent=Decimal("11.00"), source="Karnataka Transport Dept", source_url="https://transport.karnataka.gov.in", effective_date=now, last_verified_date=now),
    ])
    await session.flush()

    # =========================================================================
    # 6. INSURANCE RULES & BANKS
    # =========================================================================
    print("6/6 Seeding insurance tariff rules and bank loan products...")
    session.add_all([
        InsuranceRateRule(min_engine_cc=0, max_engine_cc=999, is_ev=False, third_party_3yr_tariff_inr=Decimal("5286.00"), own_damage_base_rate_percent=Decimal("2.60"), zero_dep_addon_percent=Decimal("0.60"), engine_protect_addon_inr=Decimal("1200.00"), description="Cars under 1000cc", source="IRDAI Tariff", source_url="https://irdai.gov.in", effective_date=now, last_verified_date=now),
        InsuranceRateRule(min_engine_cc=1000, max_engine_cc=1500, is_ev=False, third_party_3yr_tariff_inr=Decimal("9534.00"), own_damage_base_rate_percent=Decimal("2.80"), zero_dep_addon_percent=Decimal("0.70"), engine_protect_addon_inr=Decimal("1500.00"), description="Cars 1000cc to 1500cc", source="IRDAI Tariff", source_url="https://irdai.gov.in", effective_date=now, last_verified_date=now),
        InsuranceRateRule(min_engine_cc=1501, max_engine_cc=5000, is_ev=False, third_party_3yr_tariff_inr=Decimal("24596.00"), own_damage_base_rate_percent=Decimal("3.20"), zero_dep_addon_percent=Decimal("0.85"), engine_protect_addon_inr=Decimal("2000.00"), description="Cars exceeding 1500cc", source="IRDAI Tariff", source_url="https://irdai.gov.in", effective_date=now, last_verified_date=now),
        InsuranceRateRule(min_engine_cc=None, max_engine_cc=None, is_ev=True, third_party_3yr_tariff_inr=Decimal("5543.00"), own_damage_base_rate_percent=Decimal("2.50"), zero_dep_addon_percent=Decimal("0.60"), engine_protect_addon_inr=Decimal("0.00"), description="Electric Vehicles (EV)", source="IRDAI EV Tariff", source_url="https://irdai.gov.in", effective_date=now, last_verified_date=now),
    ])

    sbi = Bank(name="State Bank of India (SBI)", slug="sbi", bank_type="Public", logo_url="/logos/sbi.svg", is_active=True, source="SBI Bank", source_url="https://sbi.co.in", effective_date=now, last_verified_date=now)
    hdfc = Bank(name="HDFC Bank", slug="hdfc", bank_type="Private", logo_url="/logos/hdfc.svg", is_active=True, source="HDFC Bank", source_url="https://hdfcbank.com", effective_date=now, last_verified_date=now)
    session.add_all([sbi, hdfc])
    await session.flush()

    sbi_prod = LoanProduct(
        bank_id=sbi.id, name="SBI New Car Loan Scheme", slug="sbi-new-car-loan",
        min_loan_amount=Decimal("100000"), max_loan_amount=Decimal("15000000"),
        min_tenure_months=12, max_tenure_months=84, max_ltv_percent=Decimal("90.00"),
        processing_fee_percent=Decimal("0.40"), min_processing_fee=Decimal("1500.00"), max_processing_fee=Decimal("10000.00"),
        description="Financing up to 90% of on-road price with zero prepayment penalty.",
        is_active=True, source="SBI Auto Loan Portal", source_url="https://sbi.co.in", effective_date=now, last_verified_date=now,
    )
    session.add(sbi_prod)
    await session.flush()

    session.add_all([
        InterestRateSlab(loan_product_id=sbi_prod.id, min_cibil_score=800, max_cibil_score=900, min_interest_rate=Decimal("8.65"), max_interest_rate=Decimal("8.80"), default_interest_rate=Decimal("8.65"), is_fixed=False, source="SBI Portal", source_url="https://sbi.co.in", effective_date=now, last_verified_date=now),
        InterestRateSlab(loan_product_id=sbi_prod.id, min_cibil_score=750, max_cibil_score=799, min_interest_rate=Decimal("8.75"), max_interest_rate=Decimal("8.95"), default_interest_rate=Decimal("8.75"), is_fixed=False, source="SBI Portal", source_url="https://sbi.co.in", effective_date=now, last_verified_date=now),
        InterestRateSlab(loan_product_id=sbi_prod.id, min_cibil_score=700, max_cibil_score=749, min_interest_rate=Decimal("9.15"), max_interest_rate=Decimal("9.45"), default_interest_rate=Decimal("9.25"), is_fixed=False, source="SBI Portal", source_url="https://sbi.co.in", effective_date=now, last_verified_date=now),
        InterestRateSlab(loan_product_id=sbi_prod.id, min_cibil_score=300, max_cibil_score=699, min_interest_rate=Decimal("10.25"), max_interest_rate=Decimal("11.50"), default_interest_rate=Decimal("10.50"), is_fixed=False, source="SBI Portal", source_url="https://sbi.co.in", effective_date=now, last_verified_date=now),
    ])

    await session.commit()
    print("✅ CarAfford demonstration catalogue seed successfully completed!")


async def seed_database(session: Optional[AsyncSession] = None):
    if session is not None:
        await _run_seed(session)
    else:
        async with AsyncSessionLocal() as db_sess:
            await _run_seed(db_sess)


if __name__ == "__main__":
    asyncio.run(seed_database())
