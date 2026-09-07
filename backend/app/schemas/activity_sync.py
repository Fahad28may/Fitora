from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from app.models.activity_entry import ActivitySource, ActivityType
from app.schemas.activity import (
    MAX_CALORIES_BURNED,
    MAX_DISTANCE_KM,
    MAX_DURATION_MIN,
    MAX_NOTES_LEN,
    MAX_STEPS,
)

# One sync covers a window, not a lifetime. A device that has been offline for
# weeks pages through rather than sending everything at once, which keeps the
# request bounded and the transaction short.
MAX_ENTRIES_PER_SYNC = 500


class DeviceActivityEntry(BaseModel):
    """One activity record as reported by a health app or wearable.

    Bounds are identical to the manual endpoint's on purpose: data arriving
    from a device is no more trustworthy than data typed by a user. A health
    app reporting a 40-hour run is a bug somewhere, and it should be rejected
    at the boundary rather than stored and shown back as fact.
    """

    #: The device's own id for this record — how a re-sync of the same
    #: workout is recognised instead of duplicated.
    external_id: str = Field(min_length=1, max_length=128)
    logged_at: date
    activity_type: ActivityType
    duration_min: int = Field(gt=0, le=MAX_DURATION_MIN)
    distance_km: float | None = Field(default=None, ge=0, le=MAX_DISTANCE_KM)
    steps: int | None = Field(default=None, ge=0, le=MAX_STEPS)
    calories_burned: int | None = Field(default=None, ge=0, le=MAX_CALORIES_BURNED)
    notes: str | None = Field(default=None, max_length=MAX_NOTES_LEN)


class ActivitySyncRequest(BaseModel):
    #: Device sources only — a sync cannot write `manual`, because "the user
    #: typed this" and "a device reported this" are different claims.
    source: Literal["apple_health", "health_connect", "wearable"]
    entries: list[DeviceActivityEntry] = Field(
        min_length=1, max_length=MAX_ENTRIES_PER_SYNC
    )


class ActivitySyncResult(BaseModel):
    source: ActivitySource
    received: int
    created: int
    updated: int
