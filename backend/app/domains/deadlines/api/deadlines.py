"""FastAPI routes for the governed Deadline domain."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.auth.services import GOVERNANCE_ADMIN_ROLES
from app.domains.deadlines.models import Deadline
from app.domains.deadlines.repositories import DeadlineRepository
from app.domains.deadlines.schemas import (
    DeadlineCreate,
    DeadlineListResponse,
    DeadlineResponse,
    DeadlineType,
    RelatedFormSummary,
)
from app.domains.deadlines.services import DeadlineService
from app.domains.deadlines.services.deadline_service import InvalidRelatedFormError
from app.domains.forms.repositories import FormsRepository
from app.domains.relationships.repositories import RelationshipsRepository
from app.domains.relationships.services import RelationshipsService
from app.shared.auth import get_current_user, require_any_role
from app.shared.database.session import get_db_session
from app.shared.events import EventBus, EventContext, EventStore

router = APIRouter(prefix="/deadlines", tags=["deadlines"])
logger = get_logger(__name__)

AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_any_role(GOVERNANCE_ADMIN_ROLES)),
]


def get_deadline_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DeadlineService:
    """Build a Deadline service for a request."""

    event_bus = EventBus(EventStore(session))
    return DeadlineService(
        repository=DeadlineRepository(session),
        forms_repository=FormsRepository(session),
        relationships_service=RelationshipsService(
            RelationshipsRepository(session),
            event_bus=event_bus,
        ),
        event_bus=event_bus,
    )


@router.get("", response_model=DeadlineListResponse)
async def list_deadlines(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[DeadlineService, Depends(get_deadline_service)],
    term: Annotated[str | None, Query(max_length=50)] = None,
    academic_year: Annotated[str | None, Query(max_length=20)] = None,
    deadline_type: DeadlineType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DeadlineListResponse:
    """List governed deadlines visible to the caller."""

    deadlines, total = await service.list_deadlines(
        university_id=current_user.university_id,
        role=current_user.role,
        limit=limit,
        offset=offset,
        term=term,
        academic_year=academic_year,
        deadline_type=deadline_type,
    )
    return DeadlineListResponse(
        deadlines=[
            await _deadline_to_response(
                service=service,
                university_id=current_user.university_id,
                deadline=deadline,
            )
            for deadline in deadlines
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/upcoming", response_model=DeadlineListResponse)
async def upcoming_deadlines(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[DeadlineService, Depends(get_deadline_service)],
    as_of: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> DeadlineListResponse:
    """Return upcoming governed deadlines."""

    deadlines = await service.upcoming_deadlines(
        university_id=current_user.university_id,
        role=current_user.role,
        as_of=as_of or date.today(),
        limit=limit,
    )
    return DeadlineListResponse(
        deadlines=[
            await _deadline_to_response(
                service=service,
                university_id=current_user.university_id,
                deadline=deadline,
            )
            for deadline in deadlines
        ],
        total=len(deadlines),
        limit=limit,
        offset=0,
    )


@router.get("/search", response_model=DeadlineListResponse)
async def search_deadlines(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[DeadlineService, Depends(get_deadline_service)],
    q: Annotated[str, Query(min_length=1, max_length=255)],
    deadline_type: DeadlineType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DeadlineListResponse:
    """Search governed deadlines visible to the caller."""

    try:
        deadlines, total = await service.search_deadlines(
            university_id=current_user.university_id,
            role=current_user.role,
            query=q,
            limit=limit,
            offset=offset,
            deadline_type=deadline_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return DeadlineListResponse(
        deadlines=[
            await _deadline_to_response(
                service=service,
                university_id=current_user.university_id,
                deadline=deadline,
            )
            for deadline in deadlines
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{deadline_id}", response_model=DeadlineResponse)
async def get_deadline(
    deadline_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[DeadlineService, Depends(get_deadline_service)],
) -> DeadlineResponse:
    """Retrieve one governed deadline visible to the caller."""

    deadline = await service.retrieve_deadline(
        university_id=current_user.university_id,
        deadline_id=deadline_id,
        role=current_user.role,
    )
    if deadline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Deadline not found",
        )
    return await _deadline_to_response(
        service=service,
        university_id=current_user.university_id,
        deadline=deadline,
    )


@router.post("", response_model=DeadlineResponse, status_code=status.HTTP_201_CREATED)
async def create_deadline(
    deadline_data: DeadlineCreate,
    current_user: AdminUser,
    service: Annotated[DeadlineService, Depends(get_deadline_service)],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> DeadlineResponse:
    """Create a governed deadline."""

    logger.info(
        "deadline_create_requested actor_id=%s university_id=%s",
        current_user.user_id,
        current_user.university_id,
    )
    try:
        deadline = await service.create_deadline(
            deadline_data=deadline_data.model_copy(
                update={"university_id": current_user.university_id}
            ),
            university_id=current_user.university_id,
            actor_id=current_user.user_id,
            event_context=EventContext(
                actor_id=current_user.user_id,
                correlation_id=correlation_id,
            ),
        )
    except InvalidRelatedFormError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Related form cannot be linked",
        ) from exc
    return await _deadline_to_response(
        service=service,
        university_id=current_user.university_id,
        deadline=deadline,
    )


async def _deadline_to_response(
    service: DeadlineService,
    university_id: UUID,
    deadline: Deadline,
) -> DeadlineResponse:
    """Convert an ORM deadline to an API response without leaking internals."""

    related_form: RelatedFormSummary | None = await service.related_form_summary(
        university_id=university_id,
        deadline=deadline,
    )
    return DeadlineResponse(
        id=deadline.id,
        university_id=deadline.university_id,
        title=deadline.title,
        description=deadline.description,
        term=deadline.term,
        academic_year=deadline.academic_year,
        deadline_type=deadline.deadline_type,
        due_date=deadline.due_date,
        source_url=deadline.source_url,
        related_form_id=deadline.related_form_id,
        related_form=related_form,
        verification_status=deadline.verification_status,
        status=deadline.status,
        last_verified_at=deadline.last_verified_at,
        metadata=deadline.metadata_,
        created_at=deadline.created_at,
        updated_at=deadline.updated_at,
    )
