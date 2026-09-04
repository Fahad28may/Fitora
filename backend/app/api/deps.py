from collections.abc import AsyncGenerator

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.ai.client import AIClient, OpenRouterClient
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
