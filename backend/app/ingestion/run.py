import argparse
import asyncio
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
from app.services.ingestion_service import IngestionService


async def main():
    parser = argparse.ArgumentParser(description="CarAfford Ingestion Runner")
    parser.add_argument(
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
        ],
        help="Source adapter to execute",
    )
    parser.add_argument("--notes", type=str, default="Manual CLI ingestion run", help="Optional notes for run")
    args = parser.parse_args()

    print(f"🚀 Initializing CarAfford Ingestion for source: {args.source.upper()}...")
    if args.source in {"sbi_car_loans", "sbi"}:
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
        print(f"   Run ID: {run.id}")
        print(f"   Dataset: {run.dataset_name}")
        print(f"   Status: {run.status}")
        print(f"   Records Seen: {run.records_seen}")
        print(f"   Records Created: {run.records_created}")
        print(f"   Records Updated: {run.records_updated}")
        print(f"   Records Rejected: {run.records_rejected}")
        print(f"   Errors: {run.error_count + run.validation_error_count}")


if __name__ == "__main__":
    asyncio.run(main())
