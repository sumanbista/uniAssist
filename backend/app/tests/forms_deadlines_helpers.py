"""Shared helpers for Forms and Deadlines relationship integration tests."""

from types import SimpleNamespace
from uuid import UUID, uuid4

from app.domains.deadlines.services import DeadlineService
from app.domains.relationships.schemas import RelationshipCreate
from app.domains.relationships.services import RelationshipsService
from app.shared.events import EventBus
from app.tests.deadline_helpers import (
    FakeDeadlineRepository,
    InMemoryEventStore,
)
from app.tests.relationship_traversal_fakes import FakeFormsRepository


class FakeFormsRepositoryForLinks(FakeFormsRepository):
    """Fake forms repository for deadline link validation."""


class InMemoryRelationshipRepository:
    """Relationship repository fake preserving duplicate lookup semantics."""

    def __init__(self) -> None:
        self.relationships: list[SimpleNamespace] = []

    async def create_relationship(self, relationship_data: RelationshipCreate):
        """Create a relationship row in memory."""

        relationship = SimpleNamespace(
            id=uuid4(),
            source_entity_type=relationship_data.source_entity_type,
            source_entity_id=relationship_data.source_entity_id,
            target_entity_type=relationship_data.target_entity_type,
            target_entity_id=relationship_data.target_entity_id,
            relationship_type=relationship_data.relationship_type.value,
            confidence_score=relationship_data.confidence_score,
            provenance_type=relationship_data.provenance_type.value,
            source_reference_id=relationship_data.source_reference_id,
            metadata_=relationship_data.metadata,
        )
        self.relationships.append(relationship)
        return relationship

    async def get_relationships_for_entity(self, entity_type: str, entity_id: UUID):
        """Return relationships connected to an entity."""

        normalized_type = entity_type.strip().lower()
        return [
            relationship
            for relationship in self.relationships
            if (
                relationship.source_entity_type == normalized_type
                and relationship.source_entity_id == entity_id
            )
            or (
                relationship.target_entity_type == normalized_type
                and relationship.target_entity_id == entity_id
            )
        ]


def build_deadline_service(forms, store=None):
    """Build DeadlineService with in-memory relationship infrastructure."""

    relationship_repo = InMemoryRelationshipRepository()
    relationship_service = RelationshipsService(
        relationship_repo,
        event_bus=EventBus(store or InMemoryEventStore()),
    )
    return (
        DeadlineService(
            FakeDeadlineRepository(),
            forms_repository=FakeFormsRepositoryForLinks(forms),
            relationships_service=relationship_service,
            event_bus=EventBus(store or InMemoryEventStore()),
        ),
        relationship_repo,
    )
