"""create ingestion foundation tables

Revision ID: 20260528_0007
Revises: 20260523_0006
Create Date: 2026-05-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260528_0007"
down_revision: str | None = "20260523_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create governed calendar entries and raw page capture tables."""

    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.create_table(
        "raw_pages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("html_content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "content_hash", name="uq_raw_pages_source_hash"),
    )
    op.create_index("idx_raw_pages_source_id", "raw_pages", ["source_id"])
    op.create_index("idx_raw_pages_content_hash", "raw_pages", ["content_hash"])

    op.create_table(
        "academic_calendar_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("university_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'pending_review'"),
            nullable=False,
        ),
        sa.Column(
            "verification_status",
            sa.String(length=50),
            server_default=sa.text("'pending_review'"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "is_active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "university_id",
            "source_hash",
            name="uq_academic_calendar_entries_university_source_hash",
        ),
    )
    op.create_index(
        "idx_academic_calendar_entries_university_id",
        "academic_calendar_entries",
        ["university_id"],
    )
    op.create_index(
        "idx_academic_calendar_entries_status",
        "academic_calendar_entries",
        ["status"],
    )
    op.create_index(
        "idx_academic_calendar_entries_source_hash",
        "academic_calendar_entries",
        ["source_hash"],
    )


def downgrade() -> None:
    """Drop ingestion foundation tables."""

    op.drop_index(
        "idx_academic_calendar_entries_source_hash",
        table_name="academic_calendar_entries",
    )
    op.drop_index(
        "idx_academic_calendar_entries_status",
        table_name="academic_calendar_entries",
    )
    op.drop_index(
        "idx_academic_calendar_entries_university_id",
        table_name="academic_calendar_entries",
    )
    op.drop_table("academic_calendar_entries")
    op.drop_index("idx_raw_pages_content_hash", table_name="raw_pages")
    op.drop_index("idx_raw_pages_source_id", table_name="raw_pages")
    op.drop_table("raw_pages")
