"""Deterministic relationship traversal scoring."""

from uuid import UUID

from app.domains.relationships.enums import RelationshipType
from app.domains.relationships.models import EntityRelationship
from app.domains.relationships.traversal.schemas import TraversalEdge

RELATIONSHIP_WEIGHTS: dict[RelationshipType, float] = {
    RelationshipType.REQUIRES: 1.0,
    RelationshipType.DEADLINE_FOR: 0.85,
    RelationshipType.RELATED_TO: 0.6,
    RelationshipType.REFERENCES: 0.35,
}


def ordered_relationships(
    relationships: list[EntityRelationship],
) -> list[EntityRelationship]:
    """Sort relationships deterministically by weight and endpoint identifiers."""

    return sorted(
        relationships,
        key=lambda relationship: (
            -RELATIONSHIP_WEIGHTS.get(
                relationship_type_or_none(relationship.relationship_type),
                0.0,
            ),
            relationship.relationship_type,
            relationship.target_entity_type,
            str(relationship.target_entity_id),
            relationship.source_entity_type,
            str(relationship.source_entity_id),
            str(relationship.id),
        ),
    )


def other_endpoint(
    relationship: EntityRelationship,
    entity_type: str,
    entity_id: UUID,
) -> tuple[str, UUID]:
    """Return the endpoint opposite the current node."""

    if (
        relationship.source_entity_type == entity_type
        and relationship.source_entity_id == entity_id
    ):
        return relationship.target_entity_type, relationship.target_entity_id
    return relationship.source_entity_type, relationship.source_entity_id


def to_traversal_edge(
    relationship: EntityRelationship,
    depth: int,
) -> TraversalEdge:
    """Convert a persisted relationship into a weighted traversal edge."""

    relationship_type = RelationshipType(relationship.relationship_type)
    confidence_score = (
        float(relationship.confidence_score)
        if relationship.confidence_score is not None
        else 1.0
    )
    relationship_weight = RELATIONSHIP_WEIGHTS.get(relationship_type, 0.0)
    depth_weight = 1 / depth
    traversal_score = min(
        1.0,
        max(0.0, relationship_weight * confidence_score * depth_weight),
    )
    return TraversalEdge(
        source_entity_id=relationship.source_entity_id,
        source_entity_type=relationship.source_entity_type,
        target_entity_id=relationship.target_entity_id,
        target_entity_type=relationship.target_entity_type,
        relationship_type=relationship_type,
        depth=depth,
        traversal_score=round(traversal_score, 4),
        provenance_type=relationship.provenance_type,
        confidence_score=round(confidence_score, 4),
        scoring_metadata={
            "relationship_weight": relationship_weight,
            "confidence_score": confidence_score,
            "depth_weight": round(depth_weight, 4),
        },
    )


def relationship_type_or_none(value: str) -> RelationshipType | None:
    """Parse a relationship type without raising for unsupported stored values."""

    try:
        return RelationshipType(value)
    except ValueError:
        return None
