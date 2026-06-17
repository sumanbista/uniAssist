"""Typed schemas for governance review queues."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class ReviewDecision(StrEnum):
    """Supported manual review decisions."""

    APPROVE = "approve"
    REJECT = "reject"


class ReviewItemResponse(BaseModel):
    """Pending-review entity summary."""

    entity_type: str
    entity_id: UUID
    title: str
    category: str | None = None
    source_url: str | None = None
    status: str
    verification_status: str
    submitted_at: datetime
    source_metadata: dict[str, Any] = Field(default_factory=dict)


class ReviewDecisionRequest(BaseModel):
    """Manual governance review decision request."""

    entity_type: str = Field(min_length=1, max_length=50)
    entity_id: UUID
    decision: ReviewDecision
    review_notes: str | None = Field(default=None, max_length=4000)

    @field_validator("entity_type")
    @classmethod
    def normalize_entity_type(cls, value: str) -> str:
        """Normalize entity type identifiers."""

        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("entity_type is required")
        return normalized

    @field_validator("review_notes")
    @classmethod
    def sanitize_review_notes(cls, value: str | None) -> str | None:
        """Sanitize optional reviewer notes."""

        if value is None:
            return None
        normalized = " ".join(value.replace("\x00", "").split())
        return normalized or None


class ReviewDecisionResponse(BaseModel):
    """Result of a manual governance review decision."""

    entity_type: str
    entity_id: UUID
    decision: ReviewDecision
    status: str
    verification_status: str
    review_notes: str | None = None
