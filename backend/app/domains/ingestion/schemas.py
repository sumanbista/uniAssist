"""Typed schemas for Caldwell ingestion foundations."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.domains.ingestion.enums import IngestionContentType, IngestionSourceType


class SourceDefinition(BaseModel):
    """Allowlisted source configuration for a Caldwell ingestion run."""

    model_config = ConfigDict(frozen=True)

    source_id: str = Field(min_length=1, max_length=100)
    university_id: UUID
    university_slug: str = Field(default="caldwell", pattern=r"^caldwell$")
    source_name: str = Field(min_length=1, max_length=200)
    content_type: IngestionContentType
    source_type: IngestionSourceType = IngestionSourceType.HTML
    url: HttpUrl
    adapter_name: str = Field(default="caldwell_university")
    adapter_version: str = Field(default="v1")
    trust_level: str = Field(default="high", pattern=r"^(high|medium|low)$")
    is_authoritative: bool = True
    requires_auth: bool = False
    parser_config: dict[str, Any] = Field(default_factory=dict)


class RawSourceArtifact(BaseModel):
    """Validated raw HTML captured from an allowlisted source."""

    source: SourceDefinition
    source_url: HttpUrl
    html_content: str = Field(min_length=1)
    content_hash: str = Field(min_length=64, max_length=64)
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ParsedHtmlRecord(BaseModel):
    """Sanitized HTML-derived record before canonical normalization."""

    source_url: HttpUrl
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    extracted_at: datetime
    source_hash: str = Field(min_length=64, max_length=64)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title", "description")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        """Normalize whitespace in parsed text fields."""

        return " ".join(value.split())


class ExtractedForm(BaseModel):
    """Canonical extracted form payload."""

    source_url: HttpUrl
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    extracted_at: datetime
    source_hash: str = Field(min_length=64, max_length=64)


class ExtractedCalendarEntry(BaseModel):
    """Canonical extracted academic calendar payload."""

    source_url: HttpUrl
    title: str = Field(min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    extracted_at: datetime
    source_hash: str = Field(min_length=64, max_length=64)


class IngestionRunResponse(BaseModel):
    """API response for a synchronous Caldwell ingestion run."""

    status: str
    university_id: UUID
    content_type: IngestionContentType
    records_processed: int
    records_created: int
    records_skipped: int
    source_ids: list[str]
    errors: list[str] = Field(default_factory=list)

