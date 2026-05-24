"""create event store

Revision ID: 20260523_0005
Revises: 20260519_0004
Create Date: 2026-05-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260523_0005"
down_revision: str | None = "20260519_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create append-only internal event store table."""

    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.create_table(
        "event_store",
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=200), nullable=False),
        sa.Column("aggregate_type", sa.String(length=100), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("university_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("correlation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index("idx_event_store_aggregate_id", "event_store", ["aggregate_id"])
    op.create_index("idx_event_store_event_type", "event_store", ["event_type"])
    op.create_index("idx_event_store_occurred_at", "event_store", ["occurred_at"])
    op.create_index("idx_event_store_university_id", "event_store", ["university_id"])


def downgrade() -> None:
    """Drop append-only internal event store table."""

    op.drop_index("idx_event_store_university_id", table_name="event_store")
    op.drop_index("idx_event_store_occurred_at", table_name="event_store")
    op.drop_index("idx_event_store_event_type", table_name="event_store")
    op.drop_index("idx_event_store_aggregate_id", table_name="event_store")
    op.drop_table("event_store")
