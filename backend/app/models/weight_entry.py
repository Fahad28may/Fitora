from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WeightEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "weight_entries"
    __table_args__ = (Index("ix_weight_entries_user_id_logged_at", "user_id", "logged_at"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    logged_at: Mapped[date] = mapped_column(Date, nullable=False)
    weight_kg: Mapped[float] = mapped_column(Numeric(5, 1), nullable=False)
