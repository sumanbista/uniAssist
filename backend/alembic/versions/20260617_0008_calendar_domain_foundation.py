"""extend academic calendar entries for calendar domain

Revision ID: 20260617_0008
Revises: 20260528_0007
Create Date: 2026-06-17
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260617_0008"
down_revision: str | None = "20260528_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Safely extend existing academic calendar entries without dropping data."""

    op.execute(
        "ALTER TABLE academic_calendar_entries "
        "ADD COLUMN IF NOT EXISTS term VARCHAR(50)"
    )
    op.execute(
        "ALTER TABLE academic_calendar_entries "
        "ADD COLUMN IF NOT EXISTS academic_year VARCHAR(20)"
    )
    op.execute(
        "ALTER TABLE academic_calendar_entries "
        "ADD COLUMN IF NOT EXISTS entry_type VARCHAR(50) NOT NULL DEFAULT 'other'"
    )
    op.execute(
        "ALTER TABLE academic_calendar_entries "
        "ADD COLUMN IF NOT EXISTS start_date DATE"
    )
    op.execute(
        "ALTER TABLE academic_calendar_entries "
        "ADD COLUMN IF NOT EXISTS end_date DATE"
    )
    op.execute(
        "ALTER TABLE academic_calendar_entries "
        "ADD COLUMN IF NOT EXISTS last_verified_at TIMESTAMP WITH TIME ZONE"
    )
    op.alter_column(
        "academic_calendar_entries",
        "source_url",
        existing_type=sa.Text(),
        nullable=True,
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_academic_calendar_entries_term "
        "ON academic_calendar_entries (term)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_academic_calendar_entries_academic_year "
        "ON academic_calendar_entries (academic_year)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_academic_calendar_entries_entry_type "
        "ON academic_calendar_entries (entry_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_academic_calendar_entries_start_date "
        "ON academic_calendar_entries (start_date)"
    )


def downgrade() -> None:
    """Remove Calendar domain extensions."""

    op.execute("DROP INDEX IF EXISTS idx_academic_calendar_entries_start_date")
    op.execute("DROP INDEX IF EXISTS idx_academic_calendar_entries_entry_type")
    op.execute("DROP INDEX IF EXISTS idx_academic_calendar_entries_academic_year")
    op.execute("DROP INDEX IF EXISTS idx_academic_calendar_entries_term")
    op.alter_column(
        "academic_calendar_entries",
        "source_url",
        existing_type=sa.Text(),
        nullable=False,
    )
    op.drop_column("academic_calendar_entries", "last_verified_at")
    op.drop_column("academic_calendar_entries", "end_date")
    op.drop_column("academic_calendar_entries", "start_date")
    op.drop_column("academic_calendar_entries", "entry_type")
    op.drop_column("academic_calendar_entries", "academic_year")
    op.drop_column("academic_calendar_entries", "term")
