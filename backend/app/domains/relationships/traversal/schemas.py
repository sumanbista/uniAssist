"""Schemas for bounded relationship traversal."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.config import settings
from app.domains.relationships.enums import RelationshipType


class TraversalStatus(StrEnum):
    """Traversal result status values."""

    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class TraversalRequest(BaseModel):
    """Request body for bounded relationship traversal."""

    entity_id: UUID
    entity_type: str = Field(min_length=1, max_length=100)
    max_hops: int = Field(default=settings.TRAVERSAL_MAX_HOPS, ge=1)
    max_nodes: int = Field(default=settings.TRAVERSAL_MAX_NODES, ge=1)
    allowed_relationship_types: list[RelationshipType] = Field(default_factory=list)
    traversal_timeout_ms: int = Field(default=settings.TRAVERSAL_TIMEOUT_MS, ge=1)

    @field_validator("entity_type")
    @classmethod
    def normalize_entity_type(cls, value: str) -> str:
        """Normalize entity type input."""

        normalized_value = value.strip().lower()
        if not normalized_value:
            raise ValueError("entity_type is required")
        if any(ord(character) < 32 for character in normalized_value):
            raise ValueError("entity_type contains unsupported control characters")
        return normalized_value

    @field_validator("allowed_relationship_types")
    @classmethod
    def dedupe_relationship_types(
        cls,
        values: list[RelationshipType],
    ) -> list[RelationshipType]:
        """Remove duplicate relationship types while preserving order."""

        seen: set[RelationshipType] = set()
        deduped_values: list[RelationshipType] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            deduped_values.append(value)
        return deduped_values


class TraversalNode(BaseModel):
    """Node visited during bounded traversal."""

    entity_id: UUID
    entity_type: str
    depth: int = Field(ge=0)
    traversal_score: float = Field(ge=0, le=1)
    provenance_type: str | None = None
    confidence_score: float | None = Field(default=None, ge=0, le=1)


class TraversalEdge(BaseModel):
    """Relationship edge traversed between two nodes."""

    source_entity_id: UUID
    source_entity_type: str
    target_entity_id: UUID
    target_entity_type: str
    relationship_type: RelationshipType
    depth: int = Field(ge=1)
    traversal_score: float = Field(ge=0, le=1)
    provenance_type: str
    confidence_score: float | None = Field(default=None, ge=0, le=1)
    scoring_metadata: dict[str, float] = Field(default_factory=dict)


class TraversalTrace(BaseModel):
    """Replay-safe trace for bounded traversal."""

    root_entity_id: UUID
    root_entity_type: str
    visited_nodes: list[TraversalNode]
    traversed_edges: list[TraversalEdge]
    traversal_depth: int = Field(ge=0)
    scoring_metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = Field(ge=0)
    status: TraversalStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TraversalResult(BaseModel):
    """Bounded traversal response."""

    related_entities: list[TraversalNode]
    trace: TraversalTrace
    metadata: dict[str, Any] = Field(default_factory=dict)
