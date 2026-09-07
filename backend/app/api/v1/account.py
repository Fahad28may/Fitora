import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_object_storage
from app.core.policy import POLICY_VERSION
from app.core.rate_limit import account_rate_limit, limiter
from app.core.security import verify_password
from app.db.session import get_db
from app.models.audit import AuditEventType
from app.models.user import User
from app.schemas.account import (
    AccountDeleteRequest,
    AuditEventOut,
    ConsentOut,
    ConsentStateOut,
    ConsentUpdateRequest,
)
from app.services.account_service import AccountService
from app.services.audit_service import AuditService
from app.services.consent_service import ConsentService
from app.services.storage.base import ObjectStorage

router = APIRouter(prefix="/account", tags=["account"])

DELETE_CONFIRMATION_PHRASE = "DELETE MY ACCOUNT"



@router.get("/export")
@limiter.limit(account_rate_limit)
async def export_my_data(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Everything Fitora holds about the caller, as a JSON download (§29).

    Served as an attachment rather than a plain JSON body so a browser hitting
    this URL saves a file instead of rendering the user's whole history.
    """
    service = AccountService(db)
    payload: dict[str, Any] = await service.export(current_user)

    await AuditService(db).record(
        event_type=AuditEventType.ACCOUNT_EXPORTED, user_id=current_user.id
    )
    await db.commit()

    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="fitora-export.json"'},
    )


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit(account_rate_limit)
async def delete_my_account(
    request: Request,
    payload: AccountDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ObjectStorage | None = Depends(get_object_storage),
) -> Response:
    """Irreversibly delete the account and everything it owns (§29).

    Requires the current password and an explicit typed phrase. Neither is a
    formality: a valid access token alone should not be enough to destroy
    someone's entire history.
    """
    if payload.confirmation != DELETE_CONFIRMATION_PHRASE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Confirmation must be exactly "{DELETE_CONFIRMATION_PHRASE}".',
        )
    if not verify_password(payload.password, current_user.password_hash):
        # Recorded because a failed delete attempt is a security-relevant
        # event — it is what a stolen-session attack would look like.
        await AuditService(db).record(
            event_type=AuditEventType.LOGIN_FAILED,
            user_id=current_user.id,
            metadata={"context": "account_deletion"},
        )
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Password is incorrect."
        )

    await AccountService(db, storage).delete_account(current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/consents", response_model=ConsentStateOut)
async def get_consents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConsentStateOut:
    state = await ConsentService(db).current_state(current_user.id)
    return ConsentStateOut(policy_version=POLICY_VERSION, consents=state)


@router.put("/consents", response_model=ConsentOut)
async def update_consent(
    payload: ConsentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConsentOut:
    """Record a consent decision. Append-only: withdrawing adds a new row
    rather than editing the old one, so the history stays intact (§30)."""
    record = await ConsentService(db).record(
        user_id=current_user.id,
        consent_type=payload.consent_type,
        granted=payload.granted,
    )
    await db.commit()
    return ConsentOut(
        consent_type=record.consent_type,
        granted=record.granted,
        policy_version=record.policy_version,
        recorded_at=record.recorded_at,
    )


@router.get("/security-events", response_model=list[AuditEventOut])
async def list_security_events(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[AuditEventOut]:
    """The caller's own security history — logins, consent changes, exports.

    Users can see what happened on their account without an operator having to
    read it out of a log file for them.
    """
    events = await AuditService(db).list_for_user(current_user.id)
    return [
        AuditEventOut(
            id=event.id,
            event_type=event.event_type,
            metadata=event.event_metadata,
            created_at=event.created_at,
        )
        for event in events
    ]
