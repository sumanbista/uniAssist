"""create contacts domain

Revision ID: 20260618_0010
Revises: 20260618_0009
Create Date: 2026-06-18 00:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260618_0010"
down_revision: str | None = "20260618_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create governed contacts table."""

    op.create_table(
        "contacts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("university_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("department", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("phone", sa.String(length=50), nullable=True),
        sa.Column("office_location", sa.String(length=255), nullable=True),
        sa.Column("office_hours", sa.Text(), nullable=True),
        sa.Column("contact_type", sa.String(length=50), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_contacts_university_id", "contacts", ["university_id"])
    op.create_index("idx_contacts_department", "contacts", ["department"])
    op.create_index("idx_contacts_contact_type", "contacts", ["contact_type"])
    op.create_index("idx_contacts_email", "contacts", ["email"])
    op.create_index("idx_contacts_status", "contacts", ["status"])


def downgrade() -> None:
    """Drop governed contacts table."""

    op.drop_index("idx_contacts_status", table_name="contacts")
    op.drop_index("idx_contacts_email", table_name="contacts")
    op.drop_index("idx_contacts_contact_type", table_name="contacts")
    op.drop_index("idx_contacts_department", table_name="contacts")
    op.drop_index("idx_contacts_university_id", table_name="contacts")
    op.drop_table("contacts")
