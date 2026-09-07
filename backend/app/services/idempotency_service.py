import json
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.idempotency import IdempotencyRecord

MAX_KEY_LENGTH = 128


class IdempotencyKeyReusedError(Exception):
    """The key was already used against a different endpoint."""


class IdempotencyConflictError(Exception):
    """Two requests with the same key raced, and the other one won.

    Surfaced as 409 rather than silently returning the other request's result:
    the two may not have carried the same payload, and quietly answering with
    someone else's outcome would be worse than asking the client to retry.
    """


def _jsonable(value: Any) -> Any:
    """Pydantic models to plain JSON, so a replay can be served without
    re-running the handler."""
    if isinstance(value, BaseModel):
        return json.loads(value.model_dump_json())
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    return value


class IdempotencyService:
    """Replay protection for writes (§46 "avoid duplicate entries during
    retries").

    Deliberately opt-in per request: a client that sends no key gets the old
    behaviour. Only a client that queued a write offline needs this, and it is
    the only party that can generate a stable key for it.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def replay(
        self, *, user_id: UUID, key: str, endpoint: str
    ) -> tuple[int, Any] | None:
        """The stored outcome for this key, or None if it is new."""
        result = await self.db.execute(
            select(IdempotencyRecord).where(
                IdempotencyRecord.user_id == user_id,
                IdempotencyRecord.idempotency_key == key,
            )
        )
        record = result.scalar_one_or_none()
        if record is None:
            return None
        if record.endpoint != endpoint:
            raise IdempotencyKeyReusedError(
                f"key already used for {record.endpoint}, not {endpoint}"
            )
        return record.status_code, record.response_body

    async def remember(
        self, *, user_id: UUID, key: str, endpoint: str, status_code: int, body: Any
    ) -> None:
        self.db.add(
            IdempotencyRecord(
                user_id=user_id,
                idempotency_key=key,
                endpoint=endpoint,
                status_code=status_code,
                response_body=_jsonable(body),
                created_at=datetime.now(UTC),
            )
        )
        try:
            await self.db.commit()
        except IntegrityError as exc:
            # Lost a race against a concurrent request with the same key. The
            # write itself already committed inside `produce`, so this only
            # means the replay record is the other request's.
            await self.db.rollback()
            raise IdempotencyConflictError(key) from exc


async def run_idempotent[T: BaseModel](
    db: AsyncSession,
    *,
    user_id: UUID,
    key: str | None,
    endpoint: str,
    status_code: int,
    model: type[T],
    produce: Callable[[], Awaitable[T]],
) -> T:
    """Run `produce`, or rebuild the stored result if `key` was seen before.

    The replayed body is validated back through `model` rather than returned
    as a raw dict, so a replayed response is exactly as well-typed as a fresh
    one and a schema change can't silently start serving a stale shape.

    With no key, `produce` runs unguarded and nothing is stored — the
    pre-existing behaviour for clients that don't need replay protection.
    """
    if not key:
        return await produce()

    service = IdempotencyService(db)
    existing = await service.replay(user_id=user_id, key=key, endpoint=endpoint)
    if existing is not None:
        return model.model_validate(existing[1])

    result = await produce()
    await service.remember(
        user_id=user_id,
        key=key,
        endpoint=endpoint,
        status_code=status_code,
        body=result,
    )
    return result


__all__ = [
    "MAX_KEY_LENGTH",
    "IdempotencyConflictError",
    "IdempotencyKeyReusedError",
    "IdempotencyService",
    "run_idempotent",
]
