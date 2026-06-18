"""Service layer for canonical relationships."""

from uuid import UUID

from app.domains.relationships.models import EntityRelationship
from app.domains.relationships.repositories import RelationshipsRepository
from app.domains.relationships.schemas import RelationshipCreate
from app.shared.events import EventBus, EventContext


class DuplicateRelationshipError(ValueError):
    """Raised when a relationship already exists."""


class RelationshipsService:
    """Coordinate deterministic relationship operations."""

    def __init__(
        self,
        repository: RelationshipsRepository,
        event_bus: EventBus | None = None,
    ) -> None:
        self.repository = repository
        self.event_bus = event_bus

    async def attach_relationship(
        self,
        relationship_data: RelationshipCreate,
        university_id: UUID | None = None,
        event_context: EventContext | None = None,
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
        relationship = await self.repository.create_relationship(relationship_data)
        await self._emit_relationship_created(
            relationship=relationship,
            university_id=university_id,
            event_context=event_context,
        )
        return relationship

    async def upsert_relationship(
        self,
        relationship_data: RelationshipCreate,
        university_id: UUID | None = None,
        event_context: EventContext | None = None,
        event_type: str = "relationships.created",
    ) -> EntityRelationship | None:
        """Create a relationship if absent, returning None for duplicates."""

        await self._run_validation_hooks(relationship_data)
        existing_relationships = await self.repository.get_relationships_for_entity(
            relationship_data.source_entity_type,
            relationship_data.source_entity_id,
        )
        for relationship in existing_relationships:
            if self._is_duplicate(relationship, relationship_data):
                return None
        relationship = await self.repository.create_relationship(relationship_data)
        await self._emit_relationship_created(
            relationship=relationship,
            university_id=university_id,
            event_context=event_context,
            event_type=event_type,
        )
        return relationship

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

    async def _emit_relationship_created(
        self,
        relationship: EntityRelationship,
        university_id: UUID | None,
        event_context: EventContext | None = None,
        event_type: str = "relationships.created",
    ) -> None:
        """Emit an audit-ready relationship mutation event when scoped."""

        if self.event_bus is None or university_id is None:
            return
        await self.event_bus.emit_event(
            event_type=event_type,
            aggregate_type="relationship",
            aggregate_id=relationship.id,
            university_id=university_id,
            actor_id=event_context.actor_id if event_context else None,
            correlation_id=event_context.correlation_id if event_context else None,
            payload={
                "source_entity_type": relationship.source_entity_type,
                "source_entity_id": str(relationship.source_entity_id),
                "target_entity_type": relationship.target_entity_type,
                "target_entity_id": str(relationship.target_entity_id),
                "relationship_type": relationship.relationship_type,
                "provenance_type": relationship.provenance_type,
            },
            metadata={"source": "relationships_service"},
        )
