from datetime import datetime, timezone
import logging
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit_log import AuditLog
from app.models.user import User

logger = logging.getLogger(__name__)


class AuditService:
    """Service to create immutable append-only audit trail logs for administrative and sensitive operations."""

    @staticmethod
    async def log_action(
        session: AsyncSession,
        action: str,
        entity_type: str,
        entity_id: Optional[str] = None,
        user: Optional[User] = None,
        previous_value: Optional[Dict[str, Any]] = None,
        new_value: Optional[Dict[str, Any]] = None,
        justification: Optional[str] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        try:
            audit_entry = AuditLog(
                user_id=user.id if user else None,
                user_email=user.email if user else "SYSTEM",
                action=action,
                entity_type=entity_type,
                entity_id=str(entity_id) if entity_id is not None else None,
                previous_value=previous_value,
                new_value=new_value,
                justification=justification,
                request_id=request_id,
                ip_address=ip_address,
                created_at=datetime.now(timezone.utc),
            )
            session.add(audit_entry)
            await session.flush()
            logger.info(
                f"[AUDIT] action={action} entity={entity_type}:{entity_id} user={audit_entry.user_email} req={request_id}"
            )
            return audit_entry
        except Exception as e:
            logger.error(f"Failed to record audit log: {e}")
            # Audit recording failure should not crash the primary transaction if non-critical
            return None  # type: ignore
