"""Typed schemas for governed academic calendar records."""

from datetime import date, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class CalendarEntryType(StrEnum):
    """Supported academic calendar entry categories."""

    SEMESTER_START = "semester_start"
    SEMESTER_END = "semester_end"
    HOLIDAY = "holiday"
    BREAK = "break"
    FINALS_WEEK = "finals_week"
    REGISTRATION_PERIOD = "registration_period"
    OTHER = "other"


class CalendarEntryCreate(BaseModel):
    """Request body for creating a governed calendar entry."""

    university_id: UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    term: str | None = Field(default=None, max_length=50)
    academic_year: str | None = Field(default=None, max_length=20)
    entry_type: CalendarEntryType = CalendarEntryType.OTHER
    start_date: date
    end_date: date | None = None
    source_url: HttpUrl | None = None
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
        """Normalize whitespace and reject control characters in text fields."""

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

    @model_validator(mode="after")
    def validate_dates(self) -> "CalendarEntryCreate":
        """Ensure date ranges are coherent."""

        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class CalendarEntryResponse(BaseModel):
    """Canonical response for one calendar entry."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    university_id: UUID
    title: str
    description: str | None = None
    term: str | None = None
    academic_year: str | None = None
    entry_type: str
    start_date: date | None = None
    end_date: date | None = None
    source_url: str | None = None
    verification_status: str
    status: str
    last_verified_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CalendarEntryListResponse(BaseModel):
    """Paginated response for calendar entries."""

    entries: list[CalendarEntryResponse]
    total: int
    limit: int
    offset: int
