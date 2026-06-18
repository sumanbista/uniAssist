"""Canonical Deadline domain database model."""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, ForeignKey, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base


class Deadline(Base):
    """Governed institutional deadline scoped to one university."""

    __tablename__ = "deadlines"
    __table_args__ = (
        Index("idx_deadlines_university_id", "university_id"),
        Index("idx_deadlines_term", "term"),
        Index("idx_deadlines_academic_year", "academic_year"),
        Index("idx_deadlines_deadline_type", "deadline_type"),
        Index("idx_deadlines_due_date", "due_date"),
        Index("idx_deadlines_status", "status"),
        Index("idx_deadlines_related_form_id", "related_form_id"),
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
    term: Mapped[str | None] = mapped_column(String(50))
    academic_year: Mapped[str | None] = mapped_column(String(20))
    deadline_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'other'"),
    )
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    related_form_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("forms.id", ondelete="SET NULL"),
    )
    verification_status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'pending_review'"),
    )
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'pending_review'"),
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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

