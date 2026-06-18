"""Typed schemas for governed contact directory records."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class ContactType(StrEnum):
    """Supported university directory contact categories."""

    FACULTY = "faculty"
    STAFF = "staff"
    DEPARTMENT = "department"
    OFFICE = "office"
    ADMINISTRATION = "administration"


class ContactCreate(BaseModel):
    """Request body for creating a governed contact record."""

    university_id: UUID | None = None
    name: str = Field(min_length=1, max_length=255)
    title: str = Field(min_length=1, max_length=255)
    department: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=3, max_length=320)
    phone: str | None = Field(default=None, max_length=50)
    office_location: str | None = Field(default=None, max_length=255)
    office_hours: str | None = Field(default=None, max_length=1000)
    contact_type: ContactType
    source_url: HttpUrl | None = None
    verification_status: str = Field(default="pending_review", max_length=50)
    status: str = Field(default="pending_review", max_length=50)
    last_verified_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "name",
        "title",
        "department",
    )
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        """Normalize whitespace and require a non-empty safe text value."""

        normalized_value = " ".join(value.strip().split())
        if not normalized_value:
            raise ValueError("field is required")
        if any(ord(character) < 32 for character in normalized_value):
            raise ValueError("text fields cannot contain control characters")
        return normalized_value

    @field_validator(
        "phone",
        "office_location",
        "office_hours",
        "verification_status",
        "status",
    )
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        """Normalize whitespace and reject control characters in text fields."""

        if value is None:
            return None
        normalized_value = " ".join(value.strip().split())
        if not normalized_value:
            return None
        if any(ord(character) < 32 for character in normalized_value):
            raise ValueError("text fields cannot contain control characters")
        return normalized_value

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        """Normalize and validate an email address without extra dependencies."""

        normalized_value = value.strip().casefold()
        if any(ord(character) < 33 for character in normalized_value):
            raise ValueError("email cannot contain whitespace or control characters")
        if normalized_value.count("@") != 1:
            raise ValueError("email must contain exactly one @")
        local_part, domain = normalized_value.split("@", 1)
        if not local_part or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("email must be a valid address")
        return normalized_value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Reject oversized metadata payloads before persistence."""

        if len(value) > 50:
            raise ValueError("metadata contains too many keys")
        return value


class ContactResponse(BaseModel):
    """Canonical response for one contact record."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    university_id: UUID
    name: str
    title: str
    department: str
    email: str
    phone: str | None = None
    office_location: str | None = None
    office_hours: str | None = None
    contact_type: str
    source_url: str | None = None
    verification_status: str
    status: str
    last_verified_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ContactListResponse(BaseModel):
    """Paginated response for contact records."""

    contacts: list[ContactResponse]
    total: int
    limit: int
    offset: int
