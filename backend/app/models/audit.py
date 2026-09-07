from datetime import datetime
from enum import StrEnum
from uuid import UUID

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin, str_enum_column


class AuditEventType(StrEnum):
    USER_REGISTERED = "user_registered"
    LOGIN_SUCCEEDED = "login_succeeded"
    LOGIN_FAILED = "login_failed"
    LOGGED_OUT = "logged_out"
    CONSENT_CHANGED = "consent_changed"
    ACCOUNT_EXPORTED = "account_exported"
    ACCOUNT_DELETED = "account_deleted"


class ConsentType(StrEnum):
    """The optional processing a user can say yes or no to.

    `HEALTH_DATA` is the one consent core functionality depends on -- Fitora is
    a health app, so refusing it means the app cannot do its job. The rest are
    genuinely optional and default to not-granted.
    """

    HEALTH_DATA = "health_data"
    AI_PROCESSING = "ai_processing"
    WEARABLE_ACCESS = "wearable_access"
    ANALYTICS = "analytics"


class AuditEvent(UUIDPrimaryKeyMixin, Base):
    """Append-only record of security-sensitive operations (§61).

    `user_id` is nullable and set to NULL rather than cascade-deleted when an
    account is removed: the security trail has to survive the account it
    describes, but must stop identifying the person. It is also genuinely
    unknown for a failed login against an address that was never registered.

    `event_metadata` must never carry passwords, tokens, raw email addresses,
    or health data -- only non-reversible identifiers and coarse facts.
    """

    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_events_user_id_created_at", "user_id", "created_at"),)

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[AuditEventType] = mapped_column(
        str_enum_column(AuditEventType, 48), nullable=False
    )
    # Attribute renamed because `metadata` is reserved on a declarative class;
    # the column keeps the name used in docs/database-schema.md.
    event_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConsentRecord(UUIDPrimaryKeyMixin, Base):
    """Append-only consent decisions (§30).

    One row per decision, never updated in place -- withdrawing consent adds a
    `granted=False` row, so the history of what someone agreed to, and when,
    stays intact. `policy_version` records which wording they saw.

    Like audit events, these are anonymized rather than deleted on account
    deletion: proving a consent decision was recorded is exactly the kind of
    thing that has to outlive the account.
    """

    __tablename__ = "consent_records"
    __table_args__ = (
        Index("ix_consent_records_user_id_recorded_at", "user_id", "recorded_at"),
    )

    user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    consent_type: Mapped[ConsentType] = mapped_column(
        str_enum_column(ConsentType, 32), nullable=False
    )
    granted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
