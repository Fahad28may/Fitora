from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WaterEntry(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "water_entries"
    __table_args__ = (Index("ix_water_entries_user_id_logged_at", "user_id", "logged_at"),)

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    logged_at: Mapped[date] = mapped_column(Date, nullable=False)
    amount_ml: Mapped[int] = mapped_column(Integer, nullable=False)
