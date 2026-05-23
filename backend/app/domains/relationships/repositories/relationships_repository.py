"""Persistence access for canonical relationships."""

from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.relationships.models import EntityRelationship
from app.domains.relationships.schemas import RelationshipCreate


class RelationshipsRepository:
    """Repository for deterministic relationship persistence and retrieval."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_relationship(
        self,
        relationship_data: RelationshipCreate,
    ) -> EntityRelationship:
        """Persist a canonical relationship."""

        relationship = EntityRelationship(
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
        self.session.add(relationship)
        await self.session.commit()
        await self.session.refresh(relationship)
        return relationship

    async def get_relationships_for_entity(
        self,
        entity_type: str,
        entity_id: UUID,
    ) -> list[EntityRelationship]:
        """Return one-hop relationships where the entity is source or target."""

        normalized_entity_type = entity_type.strip().lower()
        rows = await self.session.execute(
            select(EntityRelationship)
            .where(
                or_(
                    (
                        EntityRelationship.source_entity_type == normalized_entity_type
                    )
                    & (EntityRelationship.source_entity_id == entity_id),
                    (
                        EntityRelationship.target_entity_type == normalized_entity_type
                    )
                    & (EntityRelationship.target_entity_id == entity_id),
                )
            )
            .order_by(
                EntityRelationship.relationship_type.asc(),
                EntityRelationship.target_entity_type.asc(),
                EntityRelationship.target_entity_id.asc(),
                EntityRelationship.id.asc(),
            )
        )
        return list(rows.scalars().all())
