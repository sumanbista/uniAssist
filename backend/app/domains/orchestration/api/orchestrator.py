"""FastAPI routes for constrained retrieval orchestration."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.forms.repositories import FormsRepository
from app.domains.forms.retrieval import FormsRetrievalService
from app.domains.orchestration.schemas import (
    OrchestrationRequest,
    OrchestrationResponse,
)
from app.domains.orchestration.services import (
    FormsSearchTool,
    RelationshipLookupTool,
    RetrievalOrchestrator,
    RetrievalPlanner,
    SemanticFormsSearchTool,
    ToolRegistry,
)
from app.domains.relationships.repositories import RelationshipsRepository
from app.domains.relationships.services import RelationshipsService
from app.shared.database.session import get_db_session

router = APIRouter(prefix="/orchestrator", tags=["orchestration"])


def get_retrieval_orchestrator(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> RetrievalOrchestrator:
    """Build a request-scoped retrieval orchestrator."""

    forms_service = FormsRetrievalService(FormsRepository(session))
    relationships_service = RelationshipsService(RelationshipsRepository(session))
    registry = ToolRegistry()
    registry.register(FormsSearchTool(forms_service))
    registry.register(SemanticFormsSearchTool(forms_service))
    registry.register(RelationshipLookupTool(relationships_service))
    return RetrievalOrchestrator(
        planner=RetrievalPlanner(),
        tool_registry=registry,
    )


@router.post("/query", response_model=OrchestrationResponse)
async def execute_orchestrated_query(
    request: OrchestrationRequest,
    university_id: Annotated[UUID, Header(alias="X-University-ID")],
    orchestrator: Annotated[
        RetrievalOrchestrator,
        Depends(get_retrieval_orchestrator),
    ],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> OrchestrationResponse:
    """Execute a bounded deterministic retrieval orchestration plan."""

    return await orchestrator.execute_query(
        query=request.query,
        university_id=university_id,
        correlation_id=correlation_id,
    )
