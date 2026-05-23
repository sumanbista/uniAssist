"""Canonical relationship enums."""

from enum import StrEnum


class RelationshipType(StrEnum):
    """Supported deterministic relationship types."""

    REQUIRES = "requires"
    RELATED_TO = "related_to"
    DEADLINE_FOR = "deadline_for"
    REFERENCES = "references"
    ASSOCIATED_WITH = "associated_with"


class ProvenanceType(StrEnum):
    """Supported relationship provenance types."""

    MANUAL = "manual"
    INGESTION = "ingestion"
    ADMIN_VERIFIED = "admin_verified"
    AI_INFERRED = "ai_inferred"
