from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.policy import POLICY_VERSION
from app.models.audit import AuditEventType, ConsentRecord, ConsentType
from app.services.audit_service import AuditService

# Optional consents default to NOT granted and are never pre-selected (§30).
# `health_data` is listed here too: it is required for the app to function at
# all, but it is still recorded as an explicit decision rather than assumed.
DEFAULT_GRANTED = False


class ConsentService:
    """Append-only consent ledger (§30).

    Nothing is ever updated in place: withdrawing consent appends a
    `granted=False` row. The current state is the most recent row per consent
    type, so the full history of what someone agreed to and when survives.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.audit = AuditService(db)

    async def record(
        self,
        *,
        user_id: UUID,
        consent_type: ConsentType,
        granted: bool,
    ) -> ConsentRecord:
        record = ConsentRecord(
            user_id=user_id,
            consent_type=consent_type,
            granted=granted,
            policy_version=POLICY_VERSION,
            recorded_at=datetime.now(UTC),
        )
        self.db.add(record)
        await self.audit.record(
            event_type=AuditEventType.CONSENT_CHANGED,
            user_id=user_id,
            metadata={
                "consent_type": consent_type.value,
                "granted": granted,
                "policy_version": POLICY_VERSION,
            },
        )
        await self.db.flush()
        return record

    async def current_state(self, user_id: UUID) -> dict[ConsentType, bool]:
        """The latest decision per consent type, defaulting to not-granted.

        Reads the whole (small, per-user) history rather than doing a windowed
        query, because it has to work identically on SQLite and Postgres.
        """
        result = await self.db.execute(
            select(ConsentRecord)
            .where(ConsentRecord.user_id == user_id)
            .order_by(ConsentRecord.recorded_at.asc())
        )
        state: dict[ConsentType, bool] = dict.fromkeys(ConsentType, DEFAULT_GRANTED)
        for record in result.scalars().all():
            state[record.consent_type] = record.granted
        return state

    async def history(self, user_id: UUID) -> list[ConsentRecord]:
        result = await self.db.execute(
            select(ConsentRecord)
            .where(ConsentRecord.user_id == user_id)
            .order_by(ConsentRecord.recorded_at.asc())
        )
        return list(result.scalars().all())

    async def anonymize_user(self, user_id: UUID) -> int:
        """Detach consent records from a deleted user, keeping the records.

        Being able to show that a consent decision was recorded is exactly the
        kind of thing that has to outlive the account it belonged to.
        """
        result = await self.db.execute(
            update(ConsentRecord)
            .where(ConsentRecord.user_id == user_id)
            .values(user_id=None)
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]


__all__ = ["ConsentService", "DEFAULT_GRANTED"]
