import hashlib
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent, AuditEventType


def hash_identifier(value: str | None) -> str | None:
    """One-way hash for anything that would otherwise be PII in the audit log.

    Used for the email on a failed login (the account may not exist, so there
    is no user id to attribute it to) and for client IPs. Lets an operator
    correlate repeated attempts from the same source without the log itself
    becoming a store of email addresses.
    """
    if not value:
        return None
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()


class AuditService:
    """Append-only security event log (§61).

    Deliberately narrow: only security-sensitive operations, never ordinary
    application activity, and never sensitive payloads. Recording an event
    does not commit -- it joins whatever transaction the caller is already in,
    so an audit row can never claim something the request then rolled back.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def record(
        self,
        *,
        event_type: AuditEventType,
        user_id: UUID | None = None,
        metadata: dict[str, object] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            user_id=user_id,
            event_type=event_type,
            event_metadata=metadata or {},
            created_at=datetime.now(UTC),
        )
        self.db.add(event)
        await self.db.flush()
        return event

    async def list_for_user(self, user_id: UUID, limit: int = 100) -> list[AuditEvent]:
        result = await self.db.execute(
            select(AuditEvent)
            .where(AuditEvent.user_id == user_id)
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def anonymize_user(self, user_id: UUID) -> int:
        """Detach a user's audit events from them, keeping the events.

        Called during account deletion. Returns the number of rows anonymized.
        """
        result = await self.db.execute(
            update(AuditEvent)
            .where(AuditEvent.user_id == user_id)
            .values(user_id=None)
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]


__all__ = ["AuditService", "hash_identifier"]
