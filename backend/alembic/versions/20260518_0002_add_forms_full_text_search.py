"""add forms full text search

Revision ID: 20260518_0002
Revises: 20260518_0001
Create Date: 2026-05-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260518_0002"
down_revision: str | None = "20260518_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add generated FTS vector and GIN index for Forms retrieval."""

    op.add_column(
        "forms",
        sa.Column(
            "searchable_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english', "
                "coalesce(title, '') || ' ' || "
                "coalesce(description, '') || ' ' || "
                "coalesce(category, ''))",
                persisted=True,
            ),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_forms_searchable_vector",
        "forms",
        ["searchable_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    """Remove generated FTS vector and GIN index."""

    op.drop_index("idx_forms_searchable_vector", table_name="forms")
    op.drop_column("forms", "searchable_vector")
