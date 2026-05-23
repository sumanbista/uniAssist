"""Canonical relationship graph database model."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base


class EntityRelationship(Base):
    """One-hop relationship between two canonical entities."""

    __tablename__ = "entity_relationships"
    __table_args__ = (
        UniqueConstraint(
            "source_entity_type",
            "source_entity_id",
            "target_entity_type",
            "target_entity_id",
            "relationship_type",
            name="uq_entity_relationships_source_target_type",
        ),
        Index(
            "idx_entity_relationships_source",
            "source_entity_type",
            "source_entity_id",
        ),
        Index(
            "idx_entity_relationships_target",
            "target_entity_type",
            "target_entity_id",
        ),
        Index("idx_entity_relationships_relationship_type", "relationship_type"),
        Index("idx_entity_relationships_provenance_type", "provenance_type"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    source_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_entity_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    target_entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    target_entity_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    provenance_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source_reference_id: Mapped[UUID | None] = mapped_column(PostgresUUID(as_uuid=True))
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
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
