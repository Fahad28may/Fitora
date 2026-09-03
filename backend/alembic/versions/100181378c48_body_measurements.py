"""body measurements

Revision ID: 100181378c48
Revises: 9b225f5fbee5
Create Date: 2026-09-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "100181378c48"
down_revision: str | None = "9b225f5fbee5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "body_measurements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("logged_at", sa.Date(), nullable=False),
        sa.Column("waist_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("chest_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("arm_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("leg_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column("hip_cm", sa.Numeric(5, 1), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_body_measurements_user_id_logged_at", "body_measurements", ["user_id", "logged_at"]
    )


def downgrade() -> None:
    op.drop_table("body_measurements")
