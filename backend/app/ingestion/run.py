import argparse
import asyncio
from app.core.database import AsyncSessionLocal
from app.ingestion.adapters.demo_adapter import DemoDataSourceAdapter
from app.ingestion.adapters.government_location_adapter import GovernmentLocationDataSourceAdapter
from app.services.ingestion_service import IngestionService


async def main():
    parser = argparse.ArgumentParser(description="CarAfford Ingestion Runner")
    parser.add_argument("--source", type=str, default="government_location", choices=["demo", "government_location"], help="Source adapter to execute")
    parser.add_argument("--notes", type=str, default="Manual CLI ingestion run", help="Optional notes for run")
    args = parser.parse_args()

    print(f"🚀 Initializing CarAfford Ingestion for source: {args.source.upper()}...")
    if args.source == "government_location":
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
