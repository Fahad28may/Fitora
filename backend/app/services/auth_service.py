import hashlib
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expiry,
    verify_password,
)
from app.models.audit import AuditEventType
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse
from app.services.audit_service import AuditService, hash_identifier


class InvalidCredentialsError(Exception):
    pass


class EmailAlreadyRegisteredError(Exception):
    pass


class InvalidRefreshTokenError(Exception):
    pass


def _ip_hash(ip: str | None) -> str | None:
    if not ip:
        return None
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)
        self.audit = AuditService(db)

    async def register(
        self, email: str, password: str, user_agent: str | None, ip: str | None
    ) -> tuple[User, TokenResponse]:
        existing = await self.users.get_by_email(email)
        if existing is not None:
            raise EmailAlreadyRegisteredError

        user = await self.users.create(email=email, password_hash=hash_password(password))
        tokens = await self._issue_tokens(user, user_agent, ip)
        await self.audit.record(
            event_type=AuditEventType.USER_REGISTERED,
            user_id=user.id,
            metadata={"ip_hash": hash_identifier(ip)},
        )
        await self.db.commit()
        return user, tokens

    async def login(
        self, email: str, password: str, user_agent: str | None, ip: str | None
    ) -> tuple[User, TokenResponse]:
        user = await self.users.get_by_email(email)
        if user is None or not verify_password(password, user.password_hash):
            # Recorded even when the address is unknown -- repeated failures
            # against non-existent accounts are exactly the pattern worth
            # spotting. The address itself is hashed, never stored raw.
            await self._record_failed_login(email, ip, user_id=user.id if user else None)
            raise InvalidCredentialsError
        if user.status.value != "active":
            await self._record_failed_login(email, ip, user_id=user.id)
            raise InvalidCredentialsError

        tokens = await self._issue_tokens(user, user_agent, ip)
        await self.audit.record(
            event_type=AuditEventType.LOGIN_SUCCEEDED,
            user_id=user.id,
            metadata={"ip_hash": hash_identifier(ip)},
        )
        await self.db.commit()
        return user, tokens

    async def _record_failed_login(
        self, email: str, ip: str | None, *, user_id: UUID | None
    ) -> None:
        await self.audit.record(
            event_type=AuditEventType.LOGIN_FAILED,
            user_id=user_id,
            metadata={
                "email_hash": hash_identifier(email),
                "ip_hash": hash_identifier(ip),
            },
        )
        # Committed on its own: the caller raises straight after, so without
        # this the record of the failure would roll back with the request.
        await self.db.commit()

    async def refresh(
        self, raw_refresh_token: str, user_agent: str | None, ip: str | None
    ) -> TokenResponse:
        token_hash = hash_refresh_token(raw_refresh_token)
        session = await self.users.get_session_by_token_hash(token_hash)
        if session is None or not session.is_active:
            raise InvalidRefreshTokenError

        user = await self.users.get_by_id(session.user_id)
        if user is None or user.status.value != "active":
            raise InvalidRefreshTokenError

        # Rotation: revoke the presented refresh token before issuing a new one.
        await self.users.revoke_session(session)
        tokens = await self._issue_tokens(user, user_agent, ip)
        await self.db.commit()
        return tokens

    async def logout(self, raw_refresh_token: str) -> None:
        token_hash = hash_refresh_token(raw_refresh_token)
        session = await self.users.get_session_by_token_hash(token_hash)
        if session is not None and session.is_active:
            await self.users.revoke_session(session)
            await self.audit.record(
                event_type=AuditEventType.LOGGED_OUT, user_id=session.user_id
            )
            await self.db.commit()

    async def _issue_tokens(
        self, user: User, user_agent: str | None, ip: str | None
    ) -> TokenResponse:
        access_token, expires_in = create_access_token(user.id)
        raw_refresh_token = generate_refresh_token()
        await self.users.create_session(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(raw_refresh_token),
            expires_at=refresh_token_expiry(),
            user_agent=user_agent,
            ip_hash=_ip_hash(ip),
        )
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_in=expires_in,
        )
