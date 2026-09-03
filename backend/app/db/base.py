from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def str_enum_column[E: StrEnum](enum_cls: type[E], length: int) -> Enum:
    """Enum column that stores/reads the member *value* (e.g. "beginner"),
    not the member *name* (e.g. "BEGINNER") that SQLAlchemy's Enum type uses
    by default. Every enum in this codebase is a StrEnum whose value is the
    lowercase wire format used by the API and any raw seed data — using the
    default name-based storage silently breaks anything inserted outside the
    ORM's bind processor (e.g. an Alembic data migration's bulk_insert)."""
    return Enum(
        enum_cls,
        native_enum=False,
        length=length,
        values_callable=lambda x: [e.value for e in x],
    )


class UUIDPrimaryKeyMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
