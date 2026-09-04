from datetime import date
from enum import StrEnum
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum_column


class ActivityType(StrEnum):
    WALKING = "walking"
    RUNNING = "running"
    CYCLING = "cycling"
    SWIMMING = "swimming"
    STRENGTH = "strength"
    SPORT = "sport"
    OTHER = "other"


class ActivitySource(StrEnum):
    """Where an activity entry came from.

    Only ``MANUAL`` is writable today. The device sources are part of the
    architecture now so the schema/column can hold them without a migration
    when the Phase 4 Apple Health / Health Connect / wearable integrations
    land — those integrations, not the manual API, will write them.
    """

    MANUAL = "manual"
    APPLE_HEALTH = "apple_health"
    HEALTH_CONNECT = "health_connect"
    WEARABLE = "wearable"


class ActivityEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "activity_entries"
    __table_args__ = (Index("ix_activity_entries_user_id_logged_at", "user_id", "logged_at"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    logged_at: Mapped[date] = mapped_column(Date, nullable=False)
    activity_type: Mapped[ActivityType] = mapped_column(
        str_enum_column(ActivityType, 16), nullable=False
    )
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_km: Mapped[float | None] = mapped_column(Numeric(6, 2), nullable=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # User-provided estimate; the app does not compute calorie burn itself.
    calories_burned: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[ActivitySource] = mapped_column(
        str_enum_column(ActivitySource, 16), nullable=False, default=ActivitySource.MANUAL
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
