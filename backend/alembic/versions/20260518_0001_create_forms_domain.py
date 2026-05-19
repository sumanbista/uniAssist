"""create forms domain tables

Revision ID: 20260518_0001
Revises:
Create Date: 2026-05-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260518_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create canonical Forms domain tables and retrieval indexes."""

    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pg_trgm"')

    op.create_table(
        "forms",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("university_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("storage_path", sa.Text(), nullable=True),
        sa.Column(
            "verification_status",
            sa.String(length=50),
            server_default=sa.text("'pending_review'"),
            nullable=False,
        ),
        sa.Column("verification_score", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.String(length=50),
            server_default=sa.text("'draft'"),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_forms_university_id", "forms", ["university_id"])
    op.create_index("idx_forms_title", "forms", ["title"])
    op.create_index("idx_forms_category", "forms", ["category"])
    op.create_index("idx_forms_status", "forms", ["status"])
    op.create_index("idx_forms_verification_status", "forms", ["verification_status"])
    op.create_index(
        "idx_forms_title_trgm",
        "forms",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )

    op.create_table(
        "form_relationships",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("uuid_generate_v4()"),
            nullable=False,
        ),
        sa.Column("university_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_form_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_form_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_type", sa.String(length=100), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_form_id"], ["forms.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_form_id"], ["forms.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_form_relationships_university_id",
        "form_relationships",
        ["university_id"],
    )
    op.create_index(
        "idx_form_relationships_source_form_id",
        "form_relationships",
        ["source_form_id"],
    )
    op.create_index(
        "idx_form_relationships_target_form_id",
        "form_relationships",
        ["target_form_id"],
    )
    op.create_index(
        "idx_form_relationships_relationship_type",
        "form_relationships",
        ["relationship_type"],
    )


def downgrade() -> None:
    """Drop canonical Forms domain tables."""

    op.drop_index(
        "idx_form_relationships_relationship_type",
        table_name="form_relationships",
    )
    op.drop_index("idx_form_relationships_target_form_id", table_name="form_relationships")
    op.drop_index("idx_form_relationships_source_form_id", table_name="form_relationships")
    op.drop_index("idx_form_relationships_university_id", table_name="form_relationships")
    op.drop_table("form_relationships")

    op.drop_index("idx_forms_title_trgm", table_name="forms", postgresql_using="gin")
    op.drop_index("idx_forms_verification_status", table_name="forms")
    op.drop_index("idx_forms_status", table_name="forms")
    op.drop_index("idx_forms_category", table_name="forms")
    op.drop_index("idx_forms_title", table_name="forms")
    op.drop_index("idx_forms_university_id", table_name="forms")
    op.drop_table("forms")
