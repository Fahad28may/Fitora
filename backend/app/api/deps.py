from collections.abc import AsyncGenerator

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.ai.client import AIClient, OpenRouterClient
from app.services.food_db.client import FoodDbClient, OpenFoodFactsClient
from app.services.idempotency_service import MAX_KEY_LENGTH
from app.services.storage.base import ObjectStorage

_bearer_scheme = HTTPBearer(auto_error=True)

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    try:
        user_id = decode_access_token(credentials.credentials)
    except jwt.PyJWTError as exc:
        raise _CREDENTIALS_ERROR from exc

    user = await UserRepository(db).get_by_id(user_id)
    if user is None or user.status.value != "active":
        raise _CREDENTIALS_ERROR
    return user


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    async for session in get_db():
        yield session


def get_ai_client() -> AIClient | None:
    """Returns None when no AI provider is configured — callers must handle
    that explicitly (§51: core app functionality never depends on AI)."""
    settings = get_settings()
    if not settings.ai_enabled:
        return None
    return OpenRouterClient(
        api_key=settings.ai_api_key,
        base_url=settings.ai_api_base_url,
        timeout=settings.ai_request_timeout_seconds,
    )


def get_food_db_client() -> FoodDbClient | None:
    """Returns None when no food database is configured -- barcode endpoints
    turn that into a 503, and manual/custom food entry still works.

    Opt-in by design: a lookup sends the scanned barcode to a third party, so
    it stays off until an operator sets FOOD_DB_PROVIDER."""
    settings = get_settings()
    if not settings.food_db_enabled:
        return None
    return OpenFoodFactsClient(
        base_url=settings.food_db_base_url,
        timeout=settings.food_db_request_timeout_seconds,
        user_agent=settings.food_db_user_agent,
    )


def get_object_storage() -> ObjectStorage | None:
    """Returns None when object storage isn't configured — photo endpoints
    turn that into a 503, and the rest of the app is unaffected. The MinIO
    client is imported lazily so the dependency is only required when storage
    is actually enabled."""
    settings = get_settings()
    if not settings.storage_enabled:
        return None
    from app.services.storage.minio_storage import MinioStorage

    return MinioStorage(
        endpoint_url=settings.s3_endpoint_url,
        bucket=settings.s3_bucket,
        access_key=settings.s3_access_key_id,
        secret_key=settings.s3_secret_access_key,
        presigned_expiry_seconds=settings.s3_presigned_url_expiry_seconds,
    )


def get_idempotency_key(
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> str | None:
    """Optional client-supplied replay key for write endpoints (§46).

    Only a client that queued a write while offline can generate a stable key
    for it, so this is opt-in: absent header, absent replay protection.
    """
    if idempotency_key is None:
        return None
    key = idempotency_key.strip()
    if not key:
        return None
    if len(key) > MAX_KEY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Idempotency-Key must be at most {MAX_KEY_LENGTH} characters.",
        )
    return key
