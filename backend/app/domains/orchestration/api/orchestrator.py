"""FastAPI routes for constrained retrieval orchestration."""

import inspect
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.calendar.repositories import CalendarRepository
from app.domains.calendar.services import CalendarService
from app.domains.deadlines.repositories import DeadlineRepository
from app.domains.deadlines.services import DeadlineService
from app.domains.forms.repositories import FormsRepository
from app.domains.forms.retrieval import FormsRetrievalService
from app.domains.orchestration.schemas import (
    OrchestrationRequest,
    OrchestrationResponse,
)
from app.domains.orchestration.services import (
    CalendarQueryTool,
    DeadlineQueryTool,
    FormsSearchTool,
    RelationshipLookupTool,
    RetrievalOrchestrator,
    RetrievalPlanner,
    SemanticFormsSearchTool,
    ToolRegistry,
)
from app.domains.relationships.repositories import RelationshipsRepository
from app.domains.relationships.services import RelationshipsService
from app.domains.relationships.traversal import RelationshipTraversalService
from app.domains.auth.schemas import AuthenticatedUser
from app.shared.auth import get_current_user
from app.shared.database.session import get_db_session

router = APIRouter(prefix="/orchestrator", tags=["orchestration"])


def get_retrieval_orchestrator(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RetrievalOrchestrator:
    """Build a request-scoped retrieval orchestrator."""

    forms_service = FormsRetrievalService(FormsRepository(session))
    relationships_service = RelationshipsService(RelationshipsRepository(session))
    traversal_service = RelationshipTraversalService(
        relationships_service=relationships_service,
        forms_repository=FormsRepository(session),
        deadlines_repository=DeadlineRepository(session),
    )
    registry = ToolRegistry()
    registry.register(FormsSearchTool(forms_service))
    registry.register(SemanticFormsSearchTool(forms_service))
    registry.register(CalendarQueryTool(CalendarService(CalendarRepository(session))))
    registry.register(DeadlineQueryTool(DeadlineService(DeadlineRepository(session))))
    registry.register(
        RelationshipLookupTool(
            service=relationships_service,
            traversal_service=traversal_service,
        )
    )
    return RetrievalOrchestrator(
        planner=RetrievalPlanner(),
        tool_registry=registry,
    )


@router.post("/query", response_model=OrchestrationResponse)
async def execute_orchestrated_query(
    request: OrchestrationRequest,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    orchestrator: Annotated[
        RetrievalOrchestrator,
        Depends(get_retrieval_orchestrator),
    ],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> OrchestrationResponse:
    """Execute a bounded deterministic retrieval orchestration plan."""

    execute_params = inspect.signature(orchestrator.execute_query).parameters
    if "role" in execute_params:
        return await orchestrator.execute_query(
            query=request.query,
            university_id=current_user.university_id,
            role=current_user.role,
            correlation_id=correlation_id,
        )
    return await orchestrator.execute_query(
        query=request.query,
        university_id=current_user.university_id,
        correlation_id=correlation_id,
    )
