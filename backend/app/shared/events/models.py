"""SQLAlchemy models for internal platform events."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base


class EventStoreRecord(Base):
    """Append-only durable event store record."""

    __tablename__ = "event_store"
    __table_args__ = (
        Index("idx_event_store_aggregate_id", "aggregate_id"),
        Index("idx_event_store_event_type", "event_type"),
        Index("idx_event_store_occurred_at", "occurred_at"),
        Index("idx_event_store_university_id", "university_id"),
    )

    event_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(200), nullable=False)
    aggregate_type: Mapped[str] = mapped_column(String(100), nullable=False)
    aggregate_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    university_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    actor_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True))
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    correlation_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
