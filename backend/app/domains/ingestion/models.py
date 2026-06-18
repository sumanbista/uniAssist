"""Ingestion-owned persistence models."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.domains.calendar.models import AcademicCalendarEntry
from app.shared.database.base import Base


class RawPage(Base):
    """Raw HTML page captured before deterministic normalization."""

    __tablename__ = "raw_pages"
    __table_args__ = (
        UniqueConstraint("source_id", "content_hash", name="uq_raw_pages_source_hash"),
        Index("idx_raw_pages_source_id", "source_id"),
        Index("idx_raw_pages_content_hash", "content_hash"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    html_content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
