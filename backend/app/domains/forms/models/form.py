"""Canonical Forms domain database models."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.database.base import Base


class Form(Base):
    """Workflow-aware institutional form."""

    __tablename__ = "forms"
    __table_args__ = (
        Index("idx_forms_university_id", "university_id"),
        Index("idx_forms_title", "title"),
        Index("idx_forms_category", "category"),
        Index("idx_forms_status", "status"),
        Index("idx_forms_verification_status", "verification_status"),
        Index("idx_forms_next_review_at", "next_review_at"),
        Index("idx_forms_expires_at", "expires_at"),
        Index(
            "idx_forms_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "idx_forms_searchable_vector",
            "searchable_vector",
            postgresql_using="gin",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    university_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    source_url: Mapped[str | None] = mapped_column(Text)
    storage_path: Mapped[str | None] = mapped_column(Text)
    searchable_vector: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', "
            "coalesce(title, '') || ' ' || "
            "coalesce(description, '') || ' ' || "
            "coalesce(category, ''))",
            persisted=True,
        ),
    )
    verification_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'pending_review'"),
    )
    verification_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True))
    review_notes: Mapped[str | None] = mapped_column(Text)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_count: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    staleness_score: Mapped[float | None] = mapped_column(
        Numeric(5, 2),
        server_default=text("0"),
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'draft'"),
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    is_active: Mapped[bool] = mapped_column(nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    outgoing_relationships: Mapped[list["FormRelationship"]] = relationship(
        "FormRelationship",
        back_populates="source_form",
        cascade="all, delete-orphan",
        foreign_keys="FormRelationship.source_form_id",
    )
    incoming_relationships: Mapped[list["FormRelationship"]] = relationship(
        "FormRelationship",
        back_populates="target_form",
        foreign_keys="FormRelationship.target_form_id",
    )


class FormRelationship(Base):
    """Placeholder for future workflow-aware form relationships."""

    __tablename__ = "form_relationships"
    __table_args__ = (
        Index("idx_form_relationships_university_id", "university_id"),
        Index("idx_form_relationships_source_form_id", "source_form_id"),
        Index("idx_form_relationships_target_form_id", "target_form_id"),
        Index("idx_form_relationships_relationship_type", "relationship_type"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    university_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    source_form_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("forms.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_form_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("forms.id", ondelete="CASCADE"),
        nullable=False,
    )
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
