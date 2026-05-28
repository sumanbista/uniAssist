"""FastAPI routes for canonical relationships."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.schemas import AuthenticatedUser
from app.domains.auth.services import GOVERNANCE_ADMIN_ROLES
from app.core.logging import get_logger
from app.domains.relationships.models import EntityRelationship
from app.domains.relationships.repositories import RelationshipsRepository
from app.domains.relationships.schemas import (
    RelationshipCreate,
    RelationshipListResponse,
    RelationshipResponse,
)
from app.domains.relationships.services import (
    DuplicateRelationshipError,
    RelationshipsService,
)
from app.domains.relationships.traversal import (
    RelationshipTraversalService,
    TraversalRequest,
    TraversalResult,
)
from app.domains.forms.repositories import FormsRepository
from app.shared.auth import require_any_role, scoped_university_id
from app.shared.database.session import get_db_session
from app.shared.events import EventBus, EventContext, EventStore

router = APIRouter(prefix="/relationships", tags=["relationships"])
AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_any_role(GOVERNANCE_ADMIN_ROLES)),
]
logger = get_logger(__name__)


def get_relationships_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RelationshipsService:
    """Build a Relationships service for a request."""

    return RelationshipsService(
        RelationshipsRepository(session),
        event_bus=EventBus(EventStore(session)),
    )


def get_relationship_traversal_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RelationshipTraversalService:
    """Build a relationship traversal service for a request."""

    return RelationshipTraversalService(
        relationships_service=RelationshipsService(RelationshipsRepository(session)),
        forms_repository=FormsRepository(session),
    )


@router.post(
    "",
    response_model=RelationshipResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_relationship(
    relationship_data: RelationshipCreate,
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    current_user: AdminUser,
    service: Annotated[RelationshipsService, Depends(get_relationships_service)],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> RelationshipResponse:
    """Create a canonical relationship."""

    scoped_university = scoped_university_id(current_user, university_id)
    logger.info(
        "Governance action requested: action=relationship.create user_id=%s university_id=%s",
        current_user.user_id,
        scoped_university,
    )
    try:
        relationship = await service.attach_relationship(
            relationship_data,
            university_id=scoped_university,
            event_context=EventContext(
                actor_id=current_user.user_id,
                correlation_id=correlation_id,
            ),
        )
    except DuplicateRelationshipError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _relationship_to_response(relationship)


@router.get("/{entity_type}/{entity_id}", response_model=RelationshipListResponse)
async def get_relationships_for_entity(
    entity_type: str,
    entity_id: UUID,
    service: Annotated[RelationshipsService, Depends(get_relationships_service)],
) -> RelationshipListResponse:
    """Retrieve deterministic one-hop relationships for an entity."""

    relationships = await service.retrieve_related_entities(entity_type, entity_id)
    return RelationshipListResponse(
        relationships=[
            _relationship_to_response(relationship) for relationship in relationships
        ],
        entity_type=entity_type.strip().lower(),
        entity_id=entity_id,
    )


@router.post("/traverse", response_model=TraversalResult)
async def traverse_relationships(
    request: TraversalRequest,
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    service: Annotated[
        RelationshipTraversalService,
        Depends(get_relationship_traversal_service),
    ],
) -> TraversalResult:
    """Traverse bounded relationship links for a tenant-scoped entity."""

    return await service.traverse_related_entities(
        request=request,
        university_id=university_id,
    )


def _relationship_to_response(
    relationship: EntityRelationship,
) -> RelationshipResponse:
    """Convert an ORM relationship to an API response."""

    return RelationshipResponse(
        id=relationship.id,
        source_entity_type=relationship.source_entity_type,
        source_entity_id=relationship.source_entity_id,
        target_entity_type=relationship.target_entity_type,
        target_entity_id=relationship.target_entity_id,
        relationship_type=relationship.relationship_type,
        confidence_score=float(relationship.confidence_score)
        if relationship.confidence_score is not None
        else None,
        provenance_type=relationship.provenance_type,
        source_reference_id=relationship.source_reference_id,
        metadata=relationship.metadata_,
        created_at=relationship.created_at,
        updated_at=relationship.updated_at,
    )
