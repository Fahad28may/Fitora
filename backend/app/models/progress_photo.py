from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ProgressPhoto(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "progress_photos"
    __table_args__ = (Index("ix_progress_photos_user_id_taken_at", "user_id", "taken_at"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    taken_at: Mapped[date] = mapped_column(Date, nullable=False)
    # Opaque object key in the private bucket. Access is authorized via this
    # row's ownership, never by key guessability; reads use presigned URLs.
    storage_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    content_type: Mapped[str] = mapped_column(String(64), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
