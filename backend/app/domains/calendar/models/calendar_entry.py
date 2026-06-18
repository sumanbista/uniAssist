"""Canonical Academic Calendar domain database model."""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base


class AcademicCalendarEntry(Base):
    """Governed academic calendar entry scoped to one university."""

    __tablename__ = "academic_calendar_entries"
    __table_args__ = (
        UniqueConstraint(
            "university_id",
            "source_hash",
            name="uq_academic_calendar_entries_university_source_hash",
        ),
        Index("idx_academic_calendar_entries_university_id", "university_id"),
        Index("idx_academic_calendar_entries_term", "term"),
        Index("idx_academic_calendar_entries_academic_year", "academic_year"),
        Index("idx_academic_calendar_entries_entry_type", "entry_type"),
        Index("idx_academic_calendar_entries_start_date", "start_date"),
        Index("idx_academic_calendar_entries_status", "status"),
        Index("idx_academic_calendar_entries_source_hash", "source_hash"),
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
    entry_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'other'"),
    )
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        server_default=text("'pending_review'"),
    )
    verification_status: Mapped[str] = mapped_column(
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
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
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

