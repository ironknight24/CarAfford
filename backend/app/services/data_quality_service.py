from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ingestion_constants import (
    ConflictStatus,
    VerificationStatus,
)
from app.models.ingestion import (
    DataConflictRecord,
    DataQualityReviewItem,
    RawIngestionRecord,
)
from app.schemas.ingestion import (
    DataConflictRead,
    DataQualityReviewItemRead,
)


class DataQualityService:
    """Manages the manual review queue, approving/rejecting staged items, and conflict resolution."""

    @classmethod
    async def get_review_queue(
        cls,
        db: AsyncSession,
        status: Optional[str] = VerificationStatus.PENDING_REVIEW.value,
        limit: int = 50,
    ) -> List[DataQualityReviewItem]:
        """Fetches items requiring human verification/approval."""
        query = select(DataQualityReviewItem)
        if status:
            query = query.where(DataQualityReviewItem.status == status)
        query = query.order_by(DataQualityReviewItem.created_at.desc()).limit(limit)
        res = await db.execute(query)
        return list(res.scalars().all())

    @classmethod
    async def approve_review_item(
        cls,
        db: AsyncSession,
        item_id: int,
        reviewer_name: str = "Admin",
        notes: Optional[str] = None,
    ) -> Optional[DataQualityReviewItem]:
        """Approves a review item, promoting its status to VERIFIED."""
        res = await db.execute(
            select(DataQualityReviewItem).where(DataQualityReviewItem.id == item_id)
        )
        item = res.scalars().first()
        if not item:
            return None

        item.status = VerificationStatus.VERIFIED.value
        item.reviewed_by = reviewer_name
        item.reviewed_at = datetime.now(timezone.utc)
        item.reviewer_notes = notes or "Approved during manual data governance review"
        await db.commit()
        await db.refresh(item)
        return item

    @classmethod
    async def reject_review_item(
        cls,
        db: AsyncSession,
        item_id: int,
        reviewer_name: str = "Admin",
        notes: Optional[str] = None,
    ) -> Optional[DataQualityReviewItem]:
        """Rejects a review item, marking its status as REJECTED."""
        res = await db.execute(
            select(DataQualityReviewItem).where(DataQualityReviewItem.id == item_id)
        )
        item = res.scalars().first()
        if not item:
            return None

        item.status = VerificationStatus.REJECTED.value
        item.reviewed_by = reviewer_name
        item.reviewed_at = datetime.now(timezone.utc)
        item.reviewer_notes = notes or "Rejected during data validation review"
        await db.commit()
        await db.refresh(item)
        return item

    @classmethod
    async def get_unresolved_conflicts(
        cls,
        db: AsyncSession,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[DataConflictRecord]:
        """Fetches active cross-source data discrepancies."""
        query = select(DataConflictRecord)
        if status:
            query = query.where(DataConflictRecord.status == status)
        else:
            query = query.where(DataConflictRecord.status == ConflictStatus.UNRESOLVED.value)
        query = query.order_by(DataConflictRecord.detected_at.desc()).limit(limit)
        res = await db.execute(query)
        return list(res.scalars().all())

    @classmethod
    async def resolve_conflict(
        cls,
        db: AsyncSession,
        conflict_id: int,
        accepted_source_id: int,
        notes: str,
    ) -> Optional[DataConflictRecord]:
        """Resolves a conflict by adopting one source's value."""
        res = await db.execute(
            select(DataConflictRecord).where(DataConflictRecord.id == conflict_id)
        )
        conflict = res.scalars().first()
        if not conflict:
            return None

        conflict.status = ConflictStatus.RESOLVED.value
        conflict.resolution_notes = f"Adopted Source #{accepted_source_id}: {notes}"
        conflict.resolved_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(conflict)
        return conflict
