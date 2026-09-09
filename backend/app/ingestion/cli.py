import argparse
import asyncio
from decimal import Decimal

from app.core.database import AsyncSessionLocal
from app.ingestion.adapters.demo_adapter import DemoDataSourceAdapter
from app.ingestion.adapters.government_location_adapter import GovernmentLocationDataSourceAdapter
from app.ingestion.adapters.manufacturer_vehicle_adapter import (
    TataMotorsVehicleDataSourceAdapter,
    MarutiSuzukiVehicleDataSourceAdapter,
    HyundaiVehicleDataSourceAdapter,
)
from app.ingestion.adapters.bank_finance_adapter import (
    SbiCarLoanAdapter,
    HdfcCarLoanAdapter,
    IciciCarLoanAdapter,
    AxisCarLoanAdapter,
    BankOfBarodaCarLoanAdapter,
    KotakCarLoanAdapter,
)
from app.ingestion.adapters.government_tax_adapter import (
    KarnatakaTaxRuleAdapter,
    MaharashtraTaxRuleAdapter,
    DelhiTaxRuleAdapter,
    TamilNaduTaxRuleAdapter,
    TelanganaTaxRuleAdapter,
)
from app.ingestion.adapters.tco_data_adapter import (
    PPACFuelPriceAdapter,
    StateDiscomTariffAdapter,
    IndustryMaintenanceBenchmarkAdapter,
    IRDAIInsuranceRenewalAdapter,
    FADADepreciationBenchmarkAdapter,
)
from app.ingestion.validators.finance_validator import FinanceDataValidator
from app.ingestion.validators.location_validator import LocationDataValidator
from app.ingestion.validators.pricing_validator import PriceDataValidator
from app.ingestion.validators.tax_validator import TaxRuleDataValidator
from app.ingestion.validators.vehicle_validator import VehicleDataValidator
from app.ingestion.validators.tco_validator import TCOValidator
from app.services.data_quality_service import DataQualityService
from app.services.ingestion_service import IngestionService


async def handle_run(args):
    print(f"🚀 Running CarAfford Ingestion for source: {args.source.upper()}...")
    if args.source in {"fuel_prices", "ppac_fuel_prices", "fuel"}:
        adapter = PPACFuelPriceAdapter()
    elif args.source in {"electricity_tariffs", "electricity", "ev_tariffs"}:
        adapter = StateDiscomTariffAdapter()
    elif args.source in {"maintenance_costs", "maintenance", "service_costs"}:
        adapter = IndustryMaintenanceBenchmarkAdapter()
    elif args.source in {"insurance_data", "insurance_renewals", "insurance"}:
        adapter = IRDAIInsuranceRenewalAdapter()
    elif args.source in {"depreciation_data", "depreciation", "resale_curves"}:
        adapter = FADADepreciationBenchmarkAdapter()
    elif args.source in {"karnataka_tax_rules", "karnataka_taxes", "ka_tax_rules", "ka_tax"}:
        adapter = KarnatakaTaxRuleAdapter()
    elif args.source in {"maharashtra_tax_rules", "maharashtra_taxes", "mh_tax_rules", "mh_tax"}:
        adapter = MaharashtraTaxRuleAdapter()
    elif args.source in {"delhi_tax_rules", "delhi_taxes", "dl_tax_rules", "dl_tax"}:
        adapter = DelhiTaxRuleAdapter()
    elif args.source in {"tamilnadu_tax_rules", "tamilnadu_taxes", "tn_tax_rules", "tn_tax"}:
        adapter = TamilNaduTaxRuleAdapter()
    elif args.source in {"telangana_tax_rules", "telangana_taxes", "ts_tax_rules", "ts_tax", "tg_tax"}:
        adapter = TelanganaTaxRuleAdapter()
    elif args.source in {"sbi_car_loans", "sbi"}:
        adapter = SbiCarLoanAdapter()
    elif args.source in {"hdfc_car_loans", "hdfc"}:
        adapter = HdfcCarLoanAdapter()
    elif args.source in {"icici_car_loans", "icici"}:
        adapter = IciciCarLoanAdapter()
    elif args.source in {"axis_car_loans", "axis"}:
        adapter = AxisCarLoanAdapter()
    elif args.source in {"bob_car_loans", "bob", "bank_of_baroda"}:
        adapter = BankOfBarodaCarLoanAdapter()
    elif args.source in {"kotak_car_loans", "kotak"}:
        adapter = KotakCarLoanAdapter()
    elif args.source in {"tata_vehicles", "tata", "tata_motors"}:
        adapter = TataMotorsVehicleDataSourceAdapter()
    elif args.source in {"maruti_vehicles", "maruti", "maruti_suzuki"}:
        adapter = MarutiSuzukiVehicleDataSourceAdapter()
    elif args.source in {"hyundai_vehicles", "hyundai"}:
        adapter = HyundaiVehicleDataSourceAdapter()
    elif args.source in {"government_location", "locations", "rto"}:
        adapter = GovernmentLocationDataSourceAdapter()
    else:
        adapter = DemoDataSourceAdapter()

    async with AsyncSessionLocal() as session:
        run = await IngestionService.run_adapter(session, adapter, notes=args.notes)
        print(f"✅ Ingestion Run Completed!")
        print(f"   Run ID: {run.id} | Dataset: {run.dataset_name} | Status: {run.status}")
        print(f"   Records: Seen={run.records_seen}, Created={run.records_created}, Updated={run.records_updated}, Rejected={run.records_rejected}")
        print(f"   Errors: {run.error_count + run.validation_error_count}")


def handle_validate(args):
    print(f"🔍 Validating sample data for dataset: {args.dataset}...")
    if args.dataset == "vehicles":
        v = VehicleDataValidator()
        sample = {
            "manufacturer_name": "Tata Motors",
            "model_name": "Punch",
            "variant_name": "Punch Pure 1.2 MT",
            "fuel_type": "Petrol",
            "transmission": "Manual",
            "body_type": "SUV",
            "seating_capacity": 5,
            "arai_mileage_kmpl": Decimal("20.09"),
            "safety_rating_stars": 5,
            "airbags_count": 2,
        }
        is_valid, errors = v.validate(sample)
    elif args.dataset == "prices":
        v = PriceDataValidator()
        sample = {
            "ex_showroom_price": Decimal("612900.00"),
            "effective_from": "2026-01-01T00:00:00Z",
        }
        is_valid, errors = v.validate(sample)
    elif args.dataset == "taxes":
        v = TaxRuleDataValidator()
        sample = {
            "name": "Karnataka Motor Vehicle Tax",
            "state_code": "KA",
            "state_name": "Karnataka",
            "rule_category": "TAX",
            "tax_type": "ROAD_TAX",
            "calculation_method": "BRACKETED",
            "effective_from": "2024-01-01T00:00:00Z",
            "brackets": [
                {"bracket_order": 1, "minimum_value": "0.00", "maximum_value": "500000.00", "rate": "13.0000", "calculation_method": "PERCENTAGE"},
                {"bracket_order": 2, "minimum_value": "500000.00", "maximum_value": "1000000.00", "rate": "14.0000", "calculation_method": "PERCENTAGE"},
            ],
        }
        is_valid, errors = v.validate(sample)
    elif args.dataset == "tco":
        v = TCOValidator()
        sample = {
            "tco_category": "fuel_price",
            "fuel_type": "PETROL",
            "state_code": "KA",
            "city_name": "Bengaluru",
            "price_per_unit": Decimal("102.86"),
            "unit": "Litre",
            "currency": "INR",
            "observed_date": "2026-03-01T00:00:00Z",
        }
        is_valid, errors = v.validate(sample)
    elif args.dataset == "locations":
        v = LocationDataValidator()
        sample = {
            "state_code": "KA",
            "state_name": "Karnataka",
            "city_name": "Bengaluru",
            "tier": "Tier 1",
            "rto_code": "KA-01",
            "rto_name": "Bangalore Central (Koramangala)",
            "jurisdiction": "Koramangala, BTM Layout, HSR Layout",
        }
        is_valid, errors = v.validate(sample)
    else:
        v = FinanceDataValidator()
        sample = {
            "bank_name": "State Bank of India",
            "product_name": "SBI Car Loan",
            "vehicle_type": "CAR",
            "vehicle_condition": "NEW",
            "product_category": "STANDARD",
            "min_loan_amount": Decimal("100000.00"),
            "max_loan_amount": Decimal("100000000.00"),
            "min_tenure_months": 12,
            "max_tenure_months": 84,
            "annual_interest_rate": Decimal("8.65"),
            "rates": [
                {
                    "annual_interest_rate": Decimal("8.65"),
                    "rate_type": "FLOATING",
                    "min_credit_score": 750,
                    "max_credit_score": 900,
                }
            ],
            "eligibility_rules": [
                {
                    "rule_name": "Salaried Criteria",
                    "min_monthly_income": Decimal("25000.00"),
                    "min_age_years": 21,
                    "max_age_years": 67,
                }
            ],
            "fees": [
                {
                    "fee_name": "Processing Fee",
                    "fee_type": "PROCESSING_FEE",
                    "calculation_method": "CAPPED_PERCENTAGE",
                    "percentage": Decimal("0.40"),
                }
            ],
        }
        is_valid, errors = v.validate(sample)

    if is_valid:
        print(f"✅ Validation passed for '{args.dataset}' sample!")
    else:
        print(f"❌ Validation errors for '{args.dataset}': {errors}")


async def handle_conflicts(args):
    print("🔎 Checking cross-source data conflicts...")
    async with AsyncSessionLocal() as session:
        conflicts = await DataQualityService.get_unresolved_conflicts(session)
        if not conflicts:
            print("✅ No unresolved data conflicts found across ingested sources.")
        else:
            print(f"⚠️ Found {len(conflicts)} unresolved cross-source conflict(s):")
            for c in conflicts:
                print(f"   - [ID #{c.id}] {c.entity_identifier} | Field: {c.field_name}")
                print(f"     Source A (#{c.source_a_id}): {c.source_a_value}")
                print(f"     Source B (#{c.source_b_id}): {c.source_b_value}")


async def handle_quality(args):
    print("📊 Computing transparent Data Quality & Governance score...")
    async with AsyncSessionLocal() as session:
        overview = await IngestionService.get_data_quality_overview(session)
        print(f"✅ Overall Quality Score: {overview.overall_quality_score}/100 [Status: {overview.data_status}]")
        print(f"   Source Trust: {overview.breakdown.source_trust_score}/100 | Freshness: {overview.breakdown.freshness_score}/100")
        print(f"   Completeness: {overview.breakdown.completeness_score}/100 | Validation: {overview.breakdown.validation_score}/100")
        print(f"   Active Sources: {overview.active_sources}/{overview.total_sources} | Total Runs: {overview.total_ingestion_runs}")
        print(f"   Unresolved Conflicts: {overview.unresolved_conflicts_count} | Items in Review: {overview.pending_review_items_count}")


async def handle_freshness(args):
    print("⏱️ Checking Dataset Freshness & SLA statuses...")
    async with AsyncSessionLocal() as session:
        reports = await IngestionService.get_freshness_report(session)
        for item in reports:
            print(f"   - {item.dataset_name}: Status={item.status.value} | SLA={item.sla_days} days | Age={item.age_days} days")


def main():
    parser = argparse.ArgumentParser(description="CarAfford Data Ingestion & Governance CLI")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # run command
    run_parser = subparsers.add_parser("run", help="Run ingestion adapter")
    run_parser.add_argument(
        "--source",
        type=str,
        default="government_location",
        choices=[
            "demo",
            "government_location",
            "tata_vehicles",
            "maruti_vehicles",
            "hyundai_vehicles",
            "sbi_car_loans",
            "hdfc_car_loans",
            "icici_car_loans",
            "axis_car_loans",
            "bob_car_loans",
            "kotak_car_loans",
            "karnataka_tax_rules",
            "maharashtra_tax_rules",
            "delhi_tax_rules",
            "tamilnadu_tax_rules",
            "telangana_tax_rules",
            "fuel_prices",
            "ppac_fuel_prices",
            "electricity_tariffs",
            "maintenance_costs",
            "insurance_data",
            "depreciation_data",
        ],
        help="Source adapter name",
    )
    run_parser.add_argument("--notes", type=str, default="CLI manual execution", help="Run notes")

    # validate command
    val_parser = subparsers.add_parser("validate", help="Validate dataset payload")
    val_parser.add_argument("--dataset", type=str, required=True, choices=["vehicles", "prices", "taxes", "finance", "locations", "tco"], help="Dataset to validate")

    # conflicts command
    subparsers.add_parser("conflicts", help="Inspect cross-source data conflicts")

    # quality command
    subparsers.add_parser("quality", help="Display composite data quality score & metrics")

    # freshness command
    subparsers.add_parser("freshness", help="Display dataset freshness status and SLAs")

    args = parser.parse_args()

    if args.command == "run":
        asyncio.run(handle_run(args))
    elif args.command == "validate":
        handle_validate(args)
    elif args.command == "conflicts":
        asyncio.run(handle_conflicts(args))
    elif args.command == "quality":
        asyncio.run(handle_quality(args))
    elif args.command == "freshness":
        asyncio.run(handle_freshness(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
