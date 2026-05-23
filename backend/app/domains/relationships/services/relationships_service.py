"""Service layer for canonical relationships."""

from uuid import UUID

from app.domains.relationships.models import EntityRelationship
from app.domains.relationships.repositories import RelationshipsRepository
from app.domains.relationships.schemas import RelationshipCreate


class DuplicateRelationshipError(ValueError):
    """Raised when a relationship already exists."""


class RelationshipsService:
    """Coordinate deterministic relationship operations."""

    def __init__(self, repository: RelationshipsRepository) -> None:
        self.repository = repository

    async def attach_relationship(
        self,
        relationship_data: RelationshipCreate,
    ) -> EntityRelationship:
        """Create a relationship after validation and duplicate prevention."""

        await self._run_validation_hooks(relationship_data)
        existing_relationships = await self.repository.get_relationships_for_entity(
            relationship_data.source_entity_type,
            relationship_data.source_entity_id,
        )
        for relationship in existing_relationships:
            if self._is_duplicate(relationship, relationship_data):
                raise DuplicateRelationshipError("Relationship already exists")
        return await self.repository.create_relationship(relationship_data)

    async def retrieve_related_entities(
        self,
        entity_type: str,
        entity_id: UUID,
    ) -> list[EntityRelationship]:
        """Retrieve deterministic one-hop relationships for an entity."""

        return await self.repository.get_relationships_for_entity(entity_type, entity_id)

    async def _run_validation_hooks(
        self,
        relationship_data: RelationshipCreate,
    ) -> None:
        """Placeholder for future relationship validation policies."""

        return None

    @staticmethod
    def _is_duplicate(
        relationship: EntityRelationship,
        relationship_data: RelationshipCreate,
    ) -> bool:
        """Return whether a persisted relationship matches a create request."""

        return (
            relationship.source_entity_type == relationship_data.source_entity_type
            and relationship.source_entity_id == relationship_data.source_entity_id
            and relationship.target_entity_type == relationship_data.target_entity_type
            and relationship.target_entity_id == relationship_data.target_entity_id
            and relationship.relationship_type == relationship_data.relationship_type.value
        )
