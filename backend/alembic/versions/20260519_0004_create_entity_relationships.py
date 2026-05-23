"""create entity relationships

Revision ID: 20260519_0004
Revises: 20260519_0003
Create Date: 2026-05-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260519_0004"
down_revision: str | None = "20260519_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create canonical one-hop entity relationships table."""

    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.create_table(
        "entity_relationships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("source_entity_type", sa.String(length=100), nullable=False),
        sa.Column("source_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_entity_type", sa.String(length=100), nullable=False),
        sa.Column("target_entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(length=100), nullable=False),
        sa.Column("confidence_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("provenance_type", sa.String(length=100), nullable=False),
        sa.Column("source_reference_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_entity_type",
            "source_entity_id",
            "target_entity_type",
            "target_entity_id",
            "relationship_type",
            name="uq_entity_relationships_source_target_type",
        ),
    )
    op.create_index(
        "idx_entity_relationships_source",
        "entity_relationships",
        ["source_entity_type", "source_entity_id"],
    )
    op.create_index(
        "idx_entity_relationships_target",
        "entity_relationships",
        ["target_entity_type", "target_entity_id"],
    )
    op.create_index(
        "idx_entity_relationships_relationship_type",
        "entity_relationships",
        ["relationship_type"],
    )
    op.create_index(
        "idx_entity_relationships_provenance_type",
        "entity_relationships",
        ["provenance_type"],
    )


def downgrade() -> None:
    """Drop canonical one-hop entity relationships table."""

    op.drop_index("idx_entity_relationships_provenance_type", table_name="entity_relationships")
    op.drop_index("idx_entity_relationships_relationship_type", table_name="entity_relationships")
    op.drop_index("idx_entity_relationships_target", table_name="entity_relationships")
    op.drop_index("idx_entity_relationships_source", table_name="entity_relationships")
    op.drop_table("entity_relationships")
