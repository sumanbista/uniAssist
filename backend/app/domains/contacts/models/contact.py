"""Canonical Contacts domain database models."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Index, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.database.base import Base


class Contact(Base):
    """Governed university directory record."""

    __tablename__ = "contacts"
    __table_args__ = (
        Index("idx_contacts_university_id", "university_id"),
        Index("idx_contacts_department", "department"),
        Index("idx_contacts_contact_type", "contact_type"),
        Index("idx_contacts_email", "email"),
        Index("idx_contacts_status", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        server_default=text("uuid_generate_v4()"),
    )
    university_id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(50))
    office_location: Mapped[str | None] = mapped_column(String(255))
    office_hours: Mapped[str | None] = mapped_column(Text)
    contact_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
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

