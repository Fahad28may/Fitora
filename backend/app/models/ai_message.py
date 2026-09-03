from enum import StrEnum
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin, str_enum_column


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class AIMessageRecord(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A single coach chat message. There's one running thread per user (no
    multi-conversation management) — see docs/database-schema.md."""

    __tablename__ = "ai_messages"
    __table_args__ = (Index("ix_ai_messages_user_id_created_at", "user_id", "created_at"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[MessageRole] = mapped_column(str_enum_column(MessageRole, 16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
