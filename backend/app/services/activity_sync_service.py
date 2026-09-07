from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.activity_entry import ActivityEntry, ActivitySource
from app.models.audit import ConsentType
from app.schemas.activity_sync import ActivitySyncResult, DeviceActivityEntry
from app.services.consent_service import ConsentService

DeviceSource = Literal["apple_health", "health_connect", "wearable"]

# Device sources only. A sync must never be able to write `manual` entries:
# "the user typed this" and "a device reported this" are different claims, and
# the user should be able to tell them apart in their own history.
DEVICE_SOURCES: frozenset[str] = frozenset(
    {
        ActivitySource.APPLE_HEALTH.value,
        ActivitySource.HEALTH_CONNECT.value,
        ActivitySource.WEARABLE.value,
    }
)


class WearableConsentRequiredError(Exception):
    """The user has not granted wearable-access consent.

    §30 requires consent before accessing health/wearable data. The device
    grants OS-level permission, but that is the *device's* consent to hand data
    over — this is the user's consent for Fitora to store it, which is a
    separate decision they can withdraw here without uninstalling anything.
    """


class ActivitySyncService:
    """Ingests activity reported by a health app or wearable (§15, Phase 4).

    Idempotent by `external_id`: a health app re-reports the same workout on
    every sync, so entries are matched on `(user_id, source, external_id)` and
    updated in place rather than appended. Syncing the same window twice is a
    no-op, which matters because that is the normal case, not the exception.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.consent = ConsentService(db)

    async def sync(
        self,
        *,
        user_id: UUID,
        source: DeviceSource,
        entries: list[DeviceActivityEntry],
    ) -> ActivitySyncResult:
        state = await self.consent.current_state(user_id)
        if not state.get(ConsentType.WEARABLE_ACCESS, False):
            raise WearableConsentRequiredError

        source_value = ActivitySource(source)
        created = 0
        updated = 0

        for entry in entries:
            existing = await self._find(
                user_id=user_id, source=source_value, external_id=entry.external_id
            )
            if existing is None:
                self.db.add(
                    ActivityEntry(
                        user_id=user_id,
                        logged_at=entry.logged_at,
                        activity_type=entry.activity_type,
                        duration_min=entry.duration_min,
                        distance_km=entry.distance_km,
                        steps=entry.steps,
                        calories_burned=entry.calories_burned,
                        source=source_value,
                        notes=entry.notes,
                        external_id=entry.external_id,
                    )
                )
                created += 1
                continue

            # A device can revise a record after the fact (a workout gets its
            # final distance once processing finishes), so an existing row is
            # refreshed rather than skipped.
            existing.logged_at = entry.logged_at
            existing.activity_type = entry.activity_type
            existing.duration_min = entry.duration_min
            existing.distance_km = entry.distance_km
            existing.steps = entry.steps
            existing.calories_burned = entry.calories_burned
            existing.notes = entry.notes
            updated += 1

        await self.db.commit()
        return ActivitySyncResult(
            source=source_value, created=created, updated=updated, received=len(entries)
        )

    async def _find(
        self, *, user_id: UUID, source: ActivitySource, external_id: str
    ) -> ActivityEntry | None:
        result = await self.db.execute(
            select(ActivityEntry).where(
                ActivityEntry.user_id == user_id,
                ActivityEntry.source == source,
                ActivityEntry.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()


__all__ = ["DEVICE_SOURCES", "ActivitySyncService", "WearableConsentRequiredError"]
