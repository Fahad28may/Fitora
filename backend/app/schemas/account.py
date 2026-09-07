from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.audit import AuditEventType, ConsentType


class ConsentUpdateRequest(BaseModel):
    consent_type: ConsentType
    granted: bool


class ConsentOut(BaseModel):
    consent_type: ConsentType
    granted: bool
    policy_version: str
    recorded_at: datetime


class ConsentStateOut(BaseModel):
    """Current decision for every consent type, plus the policy version those
    decisions should be checked against. A type the user has never answered
    reports `granted=false` — nothing is ever pre-selected (§30)."""

    policy_version: str
    consents: dict[ConsentType, bool]


class AuditEventOut(BaseModel):
    id: UUID
    event_type: AuditEventType
    metadata: dict[str, object]
    created_at: datetime


class AccountDeleteRequest(BaseModel):
    """Deleting an account is irreversible, so it takes the current password
    (proving the person at the keyboard is the account holder, not someone who
    walked up to an unlocked phone) plus a typed confirmation."""

    password: str = Field(min_length=1, max_length=256)
    confirmation: str = Field(description='Must be exactly "DELETE MY ACCOUNT"')
