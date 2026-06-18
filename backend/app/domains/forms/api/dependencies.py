"""Dependency builders for Forms API routes."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.auth.schemas import AuthenticatedUser
from app.domains.auth.services import GOVERNANCE_ADMIN_ROLES
from app.domains.deadlines.repositories import DeadlineRepository
from app.domains.deadlines.services import DeadlineService
from app.domains.forms.governance import FormsGovernanceService
from app.domains.forms.repositories import FormsRepository
from app.domains.forms.retrieval import FormsRetrievalService
from app.domains.forms.services import FormsFileAccessService, FormsService
from app.domains.relationships.repositories import RelationshipsRepository
from app.domains.relationships.services import RelationshipsService
from app.shared.auth import require_any_role
from app.shared.database.session import get_db_session, get_session_factory
from app.shared.events import EventBus, EventStore

AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_any_role(GOVERNANCE_ADMIN_ROLES)),
]


def get_forms_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FormsService:
    """Build a Forms service for a request."""

    return FormsService(FormsRepository(session))


def get_forms_retrieval_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FormsRetrievalService:
    """Build a Forms retrieval service for a request."""

    return FormsRetrievalService(FormsRepository(session))


def get_forms_governance_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FormsGovernanceService:
    """Build a Forms governance service for a request."""

    return FormsGovernanceService(
        FormsRepository(session),
        event_bus=EventBus(EventStore(session)),
    )


def get_relationships_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RelationshipsService:
    """Build a Relationships service for optional Forms summaries."""

    return RelationshipsService(RelationshipsRepository(session))


async def get_deadline_relationship_service(
    include_deadlines: Annotated[bool, Query()] = False,
) -> AsyncIterator[DeadlineService | None]:
    """Build a Deadline service only when related deadline summaries are requested."""

    if not include_deadlines:
        yield None
        return

    session_factory = get_session_factory()
    async with session_factory() as session:
        yield DeadlineService(
            repository=DeadlineRepository(session),
            relationships_service=RelationshipsService(RelationshipsRepository(session)),
        )


def get_forms_file_access_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> FormsFileAccessService:
    """Build a Forms file access service for a request."""

    return FormsFileAccessService(FormsRepository(session))
