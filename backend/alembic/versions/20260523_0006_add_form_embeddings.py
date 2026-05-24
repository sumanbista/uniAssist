"""add form embeddings

Revision ID: 20260523_0006
Revises: 20260523_0005
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260523_0006"
down_revision: str | None = "20260523_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


class Vector(sa.types.UserDefinedType):
    """PostgreSQL pgvector type for migrations."""

    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: object) -> str:
        """Return pgvector column specification."""

        return f"vector({self.dimensions})"


def upgrade() -> None:
    """Enable pgvector and add nullable Forms embedding columns."""

    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')
    op.add_column("forms", sa.Column("embedding", Vector(384), nullable=True))
    op.add_column(
        "forms",
        sa.Column("embedding_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "idx_forms_embedding",
        "forms",
        ["embedding"],
        postgresql_using="ivfflat",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    """Remove Forms embedding columns."""

    op.drop_index("idx_forms_embedding", table_name="forms")
    op.drop_column("forms", "embedding_updated_at")
    op.drop_column("forms", "embedding")
