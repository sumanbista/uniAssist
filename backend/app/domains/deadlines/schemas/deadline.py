"""Typed schemas for governed deadline records."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class DeadlineType(StrEnum):
    """Supported institutional deadline categories."""

    ADD_DROP = "add_drop"
    WITHDRAWAL = "withdrawal"
    GRADUATION_APPLICATION = "graduation_application"
    TUITION_DUE = "tuition_due"
    REGISTRATION = "registration"
    HOUSING = "housing"
    FINANCIAL_AID = "financial_aid"
    OTHER = "other"


class DeadlineCreate(BaseModel):
    """Request body for creating a governed deadline."""

    university_id: UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    term: str | None = Field(default=None, max_length=50)
    academic_year: str | None = Field(default=None, max_length=20)
    deadline_type: DeadlineType = DeadlineType.OTHER
    due_date: date
    source_url: HttpUrl | None = None
    related_form_id: UUID | None = None
    verification_status: str = Field(default="pending_review", max_length=50)
    status: str = Field(default="pending_review", max_length=50)
    last_verified_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """Normalize and require a non-empty title."""

        normalized_value = " ".join(value.strip().split())
        if not normalized_value:
            raise ValueError("title is required")
        if any(ord(character) < 32 for character in normalized_value):
            raise ValueError("title cannot contain control characters")
        return normalized_value

    @field_validator("term", "academic_year", "verification_status", "status")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        """Normalize optional text fields and reject control characters."""

        if value is None:
            return None
        normalized_value = " ".join(value.strip().split())
        if not normalized_value:
            return None
        if any(ord(character) < 32 for character in normalized_value):
            raise ValueError("text fields cannot contain control characters")
        return normalized_value

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        """Normalize optional description text."""

        if value is None:
            return None
        normalized_value = " ".join(value.strip().split())
        if not normalized_value:
            return None
        if any(ord(character) < 32 for character in normalized_value):
            raise ValueError("description cannot contain control characters")
        return normalized_value

    @field_validator("metadata")
    @classmethod
    def validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Reject oversized metadata payloads before persistence."""

        if len(value) > 50:
            raise ValueError("metadata contains too many keys")
        return value


class DeadlineResponse(BaseModel):
    """Canonical response for one deadline."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    university_id: UUID
    title: str
    description: str | None = None
    term: str | None = None
    academic_year: str | None = None
    deadline_type: str
    due_date: date
    source_url: str | None = None
    related_form_id: UUID | None = None
    related_form: "RelatedFormSummary | None" = None
    verification_status: str
    status: str
    last_verified_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class DeadlineListResponse(BaseModel):
    """Paginated response for deadline records."""

    deadlines: list[DeadlineResponse]
    total: int
    limit: int
    offset: int


class RelatedFormSummary(BaseModel):
    """Safe related form summary for Deadline responses."""

    form_id: UUID
    title: str
    category: str | None = None
    status: str
    verification_status: str
