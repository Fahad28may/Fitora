from datetime import datetime
from uuid import UUID

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class IdempotencyRecord(UUIDPrimaryKeyMixin, Base):
    """Remembers the outcome of a write so replaying it is a no-op (§46).

    An offline client queues writes and flushes them when the network comes
    back. Without this, a request that actually succeeded but whose response
    was lost — the usual failure on a flaky connection — gets retried and
    logs the meal twice.

    Scoped per user as well as per key: keys are generated on the client, so
    two users could pick the same one, and a global unique key would let one
    user's write silently return another user's stored response.
    """

    __tablename__ = "idempotency_keys"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_idempotency_user_key"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    #: The route the key was first used against. A key replayed against a
    #: different endpoint is a client bug, and answering it with an unrelated
    #: stored response would be worse than failing.
    endpoint: Mapped[str] = mapped_column(String(128), nullable=False)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[object] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
