import asyncio
from app.core.database import AsyncSessionLocal
from app.services.data_quality_service import DataQualityService


async def main():
    print("🔎 Inspecting cross-source data conflicts...")
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


if __name__ == "__main__":
    asyncio.run(main())
