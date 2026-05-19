"""add forms governance metadata

Revision ID: 20260519_0003
Revises: 20260518_0002
Create Date: 2026-05-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260519_0003"
down_revision: str | None = "20260518_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add governance and revalidation metadata to forms."""

    op.add_column(
        "forms",
        sa.Column("verified_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("forms", sa.Column("review_notes", sa.Text(), nullable=True))
    op.add_column(
        "forms",
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "forms",
        sa.Column("next_review_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "forms",
        sa.Column("review_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.add_column(
        "forms",
        sa.Column(
            "staleness_score",
            sa.Numeric(precision=5, scale=2),
            server_default=sa.text("0"),
            nullable=True,
        ),
    )
    op.create_index("idx_forms_next_review_at", "forms", ["next_review_at"])
    op.create_index("idx_forms_expires_at", "forms", ["expires_at"])


def downgrade() -> None:
    """Remove governance and revalidation metadata from forms."""

    op.drop_index("idx_forms_expires_at", table_name="forms")
    op.drop_index("idx_forms_next_review_at", table_name="forms")
    op.drop_column("forms", "staleness_score")
    op.drop_column("forms", "review_count")
    op.drop_column("forms", "next_review_at")
    op.drop_column("forms", "expires_at")
    op.drop_column("forms", "review_notes")
    op.drop_column("forms", "verified_by")
