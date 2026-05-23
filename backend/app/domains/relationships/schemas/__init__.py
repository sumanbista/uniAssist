"""Relationships domain Pydantic schemas."""

from app.domains.relationships.schemas.relationship import (
    RelationshipCreate,
    RelationshipListResponse,
    RelationshipResponse,
)

__all__ = [
    "RelationshipCreate",
    "RelationshipListResponse",
    "RelationshipResponse",
]
