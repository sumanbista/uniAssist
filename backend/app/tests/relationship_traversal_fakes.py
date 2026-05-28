"""Shared fakes for relationship traversal tests."""

import asyncio
from types import SimpleNamespace
from uuid import UUID, uuid4

from app.domains.relationships.enums import ProvenanceType, RelationshipType
from app.domains.relationships.traversal import RelationshipTraversalService


class FakeRelationshipsService:
    """In-memory relationship service for traversal tests."""

    def __init__(self, relationships: list[SimpleNamespace]) -> None:
        self.relationships = relationships

    async def retrieve_related_entities(
        self,
        entity_type: str,
        entity_id: UUID,
    ) -> list[SimpleNamespace]:
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


class FakeFormsRepository:
    """In-memory form repository for tenant and governance checks."""

    EXCLUDED_RETRIEVAL_STATUSES = ("archived", "deprecated", "rejected")

    def __init__(self, forms: dict[UUID, SimpleNamespace]) -> None:
        self.forms = forms

    async def get_form_by_id(
        self,
        university_id: UUID,
        form_id: UUID,
        include_inactive: bool = False,
    ) -> SimpleNamespace | None:
        """Return a tenant-scoped form when available."""

        form = self.forms.get(form_id)
        if form is None or form.university_id != university_id:
            return None
        return form


class SlowRelationshipsService:
    """Relationship service that exceeds traversal timeout budgets."""

    async def retrieve_related_entities(
        self,
        entity_type: str,
        entity_id: UUID,
    ) -> list[SimpleNamespace]:
        """Sleep longer than short test traversal budgets."""

        await asyncio.sleep(0.05)
        return []


class FakeTraversalService:
    """Traversal service stub for orchestrator tool integration tests."""

    async def traverse_related_entities(self, request, university_id):
        """Return one deterministic traversal node and trace."""

        service = traversal_service(
            university_id=university_id,
            root_id=request.entity_id,
            relationships=[
                relationship(
                    source_id=request.entity_id,
                    target_id=uuid4(),
                    relationship_type=RelationshipType.REQUIRES,
                    confidence_score=0.9,
                )
            ],
        )
        return await service.traverse_related_entities(request, university_id)


def traversal_service(
    university_id: UUID,
    root_id: UUID,
    relationships: list[SimpleNamespace],
    extra_form_ids: list[UUID] | None = None,
) -> RelationshipTraversalService:
    """Build a traversal service with tenant-scoped fake forms."""

    form_ids = [root_id, *(extra_form_ids or [])]
    for row in relationships:
        form_ids.extend([row.source_entity_id, row.target_entity_id])
    return RelationshipTraversalService(
        relationships_service=FakeRelationshipsService(relationships),
        forms_repository=FakeFormsRepository(
            {form_id: form(form_id, university_id) for form_id in set(form_ids)}
        ),
    )


def relationship(
    source_id: UUID,
    target_id: UUID,
    relationship_type: RelationshipType = RelationshipType.REQUIRES,
    confidence_score: float = 1.0,
) -> SimpleNamespace:
    """Create a fake relationship row."""

    return SimpleNamespace(
        id=uuid4(),
        source_entity_type="form",
        source_entity_id=source_id,
        target_entity_type="form",
        target_entity_id=target_id,
        relationship_type=relationship_type.value,
        confidence_score=confidence_score,
        provenance_type=ProvenanceType.ADMIN_VERIFIED.value,
        metadata_={},
    )


def form(
    form_id: UUID,
    university_id: UUID,
    status: str = "published",
    verification_status: str = "verified",
) -> SimpleNamespace:
    """Create a fake form row."""

    return SimpleNamespace(
        id=form_id,
        university_id=university_id,
        status=status,
        verification_status=verification_status,
    )
