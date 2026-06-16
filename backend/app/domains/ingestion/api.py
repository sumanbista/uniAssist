"""FastAPI routes for Caldwell ingestion runs."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.auth.services import GOVERNANCE_ADMIN_ROLES
from app.domains.ingestion.schemas import IngestionRunResponse
from app.domains.ingestion.service import CaldwellIngestionService
from app.domains.ingestion.pdf_forms import router as pdf_forms_router
from app.shared.auth import require_any_role
from app.shared.database.session import get_db_session
from app.shared.events import EventContext

router = APIRouter(prefix="/ingestion", tags=["ingestion"])
router.include_router(pdf_forms_router)
logger = get_logger(__name__)
AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_any_role(GOVERNANCE_ADMIN_ROLES)),
]


def get_ingestion_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CaldwellIngestionService:
    """Build a Caldwell ingestion service for the request."""

    return CaldwellIngestionService(session)


@router.post("/run/forms", response_model=IngestionRunResponse)
async def run_forms_ingestion(
    current_user: AdminUser,
    service: Annotated[CaldwellIngestionService, Depends(get_ingestion_service)],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> IngestionRunResponse:
    """Run one admin-triggered Caldwell forms ingestion pass."""

    logger.info(
        "ingestion_api_requested content_type=forms user_id=%s university_id=%s",
        current_user.user_id,
        current_user.university_id,
    )
    return await service.run_forms(
        event_context=EventContext(
            actor_id=current_user.user_id,
            correlation_id=correlation_id,
        )
    )


@router.post("/run/calendar", response_model=IngestionRunResponse)
async def run_calendar_ingestion(
    current_user: AdminUser,
    service: Annotated[CaldwellIngestionService, Depends(get_ingestion_service)],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> IngestionRunResponse:
    """Run one admin-triggered Caldwell academic calendar ingestion pass."""

    logger.info(
        "ingestion_api_requested content_type=calendar user_id=%s university_id=%s",
        current_user.user_id,
        current_user.university_id,
    )
    return await service.run_calendar(
        event_context=EventContext(
            actor_id=current_user.user_id,
            correlation_id=correlation_id,
        )
    )
