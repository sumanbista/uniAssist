"""API schemas for canonical relationships."""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.domains.relationships.enums import ProvenanceType, RelationshipType


class RelationshipCreate(BaseModel):
    """Request body for creating an entity relationship."""

    source_entity_type: str = Field(min_length=1, max_length=100)
    source_entity_id: UUID
    target_entity_type: str = Field(min_length=1, max_length=100)
    target_entity_id: UUID
    relationship_type: RelationshipType
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    provenance_type: ProvenanceType = ProvenanceType.MANUAL
    source_reference_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_entity_type", "target_entity_type", mode="before")
    @classmethod
    def normalize_entity_type(cls, value: str) -> str:
        """Normalize entity type identifiers."""

        normalized_value = value.strip().lower()
        if not normalized_value:
            raise ValueError("entity type is required")
        return normalized_value


class RelationshipResponse(BaseModel):
    """Relationship response with provenance metadata."""

    id: UUID
    source_entity_type: str
    source_entity_id: UUID
    target_entity_type: str
    target_entity_id: UUID
    relationship_type: RelationshipType
    confidence_score: float | None = None
    provenance_type: ProvenanceType
    source_reference_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class RelationshipListResponse(BaseModel):
    """List response for deterministic relationship retrieval."""

    relationships: list[RelationshipResponse]
    entity_type: str
    entity_id: UUID
