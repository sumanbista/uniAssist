"""create governed deadlines domain

Revision ID: 20260618_0009
Revises: 20260617_0008
Create Date: 2026-06-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260618_0009"
down_revision: str | None = "20260617_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create governed deadlines table and indexes."""

    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.create_table(
        "deadlines",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("university_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("term", sa.String(length=50), nullable=True),
        sa.Column("academic_year", sa.String(length=20), nullable=True),
        sa.Column(
            "deadline_type",
            sa.String(length=50),
            server_default=sa.text("'other'"),
            nullable=False,
        ),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("related_form_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "verification_status",
            sa.String(length=50),
            server_default=sa.text("'pending_review'"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'pending_review'"),
            nullable=False,
        ),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["related_form_id"],
            ["forms.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_deadlines_university_id", "deadlines", ["university_id"])
    op.create_index("idx_deadlines_term", "deadlines", ["term"])
    op.create_index("idx_deadlines_academic_year", "deadlines", ["academic_year"])
    op.create_index("idx_deadlines_deadline_type", "deadlines", ["deadline_type"])
    op.create_index("idx_deadlines_due_date", "deadlines", ["due_date"])
    op.create_index("idx_deadlines_status", "deadlines", ["status"])
    op.create_index("idx_deadlines_related_form_id", "deadlines", ["related_form_id"])


def downgrade() -> None:
    """Drop governed deadlines table."""

    op.drop_index("idx_deadlines_related_form_id", table_name="deadlines")
    op.drop_index("idx_deadlines_status", table_name="deadlines")
    op.drop_index("idx_deadlines_due_date", table_name="deadlines")
    op.drop_index("idx_deadlines_deadline_type", table_name="deadlines")
    op.drop_index("idx_deadlines_academic_year", table_name="deadlines")
    op.drop_index("idx_deadlines_term", table_name="deadlines")
    op.drop_index("idx_deadlines_university_id", table_name="deadlines")
    op.drop_table("deadlines")
