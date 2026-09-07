"""activity external id for device sync

Revision ID: d9e4a2c81f56
Revises: c5d8b0a13e77
Create Date: 2026-09-07

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d9e4a2c81f56"
down_revision: str | None = "c5d8b0a13e77"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table, not a bare create_unique_constraint: SQLite has no
    # ALTER for constraints, and SQLite is the documented dev/test database.
    # Batch mode does copy-and-move there and a plain ALTER on Postgres.
    with op.batch_alter_table("activity_entries") as batch:
        batch.add_column(sa.Column("external_id", sa.String(length=128), nullable=True))
        # A health app re-reports the same workout on every sync; without this,
        # syncing twice would double the user's activity totals. NULL
        # external_id (manual entries) is exempt, so a user can still log the
        # same thing twice by hand if they mean to.
        batch.create_unique_constraint(
            "uq_activity_user_source_external", ["user_id", "source", "external_id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("activity_entries") as batch:
        batch.drop_constraint("uq_activity_user_source_external", type_="unique")
        batch.drop_column("external_id")
