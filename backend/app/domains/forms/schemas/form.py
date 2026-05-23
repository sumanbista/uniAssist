"""API schemas for the Forms domain."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


class FormCreate(BaseModel):
    """Request body for creating a canonical form."""

    university_id: UUID
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    category: str | None = Field(default=None, max_length=100)
    source_url: HttpUrl | None = None
    storage_path: str | None = None
    verification_status: str = Field(default="pending_review", max_length=50)
    verification_score: float | None = Field(default=None, ge=0, le=1)
    last_verified_at: datetime | None = None
    expires_at: datetime | None = None
    next_review_at: datetime | None = None
    review_notes: str | None = None
    status: str = Field(default="draft", max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """Strip whitespace and reject empty titles."""

        normalized_title = value.strip()
        if not normalized_title:
            raise ValueError("title is required")
        return normalized_title

    @field_validator("category", "storage_path", "verification_status", "status")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """Strip optional text fields and convert blanks to missing values."""

        if value is None:
            return None
        normalized_value = value.strip()
        return normalized_value or None


class FormGovernanceRequest(BaseModel):
    """Request body for governance lifecycle actions."""

    review_notes: str | None = None


class FormVerifyRequest(FormGovernanceRequest):
    """Request body for verifying a form."""

    verified_by: UUID | None = None
    verification_score: float | None = Field(default=None, ge=0, le=1)
    expires_at: datetime | None = None
    next_review_at: datetime | None = None


class FormVerificationResponse(BaseModel):
    """Governance verification metadata for a form."""

    id: UUID
    university_id: UUID
    verification_status: str
    verification_score: float | None = None
    last_verified_at: datetime | None = None
    verified_by: UUID | None = None
    review_notes: str | None = None
    expires_at: datetime | None = None
    next_review_at: datetime | None = None
    review_count: int
    staleness_score: float | None = None
    status: str


class RelatedEntitySummary(BaseModel):
    """One-hop related entity summary for Forms responses."""

    entity_type: str
    entity_id: UUID
    relationship_type: str
    confidence_score: float | None = None
    provenance_type: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class FormResponse(BaseModel):
    """Canonical form response."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    university_id: UUID
    title: str
    description: str | None = None
    category: str | None = None
    source_url: str | None = None
    storage_path: str | None = None
    verification_status: str
    verification_score: float | None = None
    last_verified_at: datetime | None = None
    verified_by: UUID | None = None
    review_notes: str | None = None
    expires_at: datetime | None = None
    next_review_at: datetime | None = None
    review_count: int = 0
    staleness_score: float | None = None
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    related_entities: list[RelatedEntitySummary] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class FormListResponse(BaseModel):
    """Paginated list response for forms."""

    forms: list[FormResponse]
    total: int
    limit: int
    offset: int


class FormSearchResult(BaseModel):
    """Single Forms retrieval result with ranking metadata."""

    id: UUID
    university_id: UUID
    title: str
    description: str | None = None
    category: str | None = None
    source_url: str | None = None
    verification_status: str
    verification_score: float | None = None
    last_verified_at: datetime | None = None
    next_review_at: datetime | None = None
    expires_at: datetime | None = None
    staleness_score: float | None = None
    status: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    ranking_score: float
    ranking_signals: dict[str, float] = Field(default_factory=dict)


class FormSearchResponse(BaseModel):
    """Forms retrieval response."""

    forms: list[FormSearchResult]
    query: str
    limit: int
