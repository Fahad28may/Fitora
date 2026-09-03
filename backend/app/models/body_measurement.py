from datetime import date
from uuid import UUID

from sqlalchemy import Date, ForeignKey, Index, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class BodyMeasurement(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "body_measurements"
    __table_args__ = (
        Index("ix_body_measurements_user_id_logged_at", "user_id", "logged_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    logged_at: Mapped[date] = mapped_column(Date, nullable=False)
    waist_cm: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    chest_cm: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    arm_cm: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    leg_cm: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
    hip_cm: Mapped[float | None] = mapped_column(Numeric(5, 1), nullable=True)
