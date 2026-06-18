"""FastAPI routes for the governed Calendar domain."""

from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.auth.services import GOVERNANCE_ADMIN_ROLES
from app.domains.calendar.models import AcademicCalendarEntry
from app.domains.calendar.repositories import CalendarRepository
from app.domains.calendar.schemas import (
    CalendarEntryCreate,
    CalendarEntryListResponse,
    CalendarEntryResponse,
    CalendarEntryType,
)
from app.domains.calendar.services import CalendarService
from app.shared.auth import get_current_user, require_any_role
from app.shared.database.session import get_db_session
from app.shared.events import EventBus, EventContext, EventStore

router = APIRouter(prefix="/calendar", tags=["calendar"])
logger = get_logger(__name__)

AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_any_role(GOVERNANCE_ADMIN_ROLES)),
]


def get_calendar_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CalendarService:
    """Build a Calendar service for a request."""

    return CalendarService(
        repository=CalendarRepository(session),
        event_bus=EventBus(EventStore(session)),
    )


@router.get("", response_model=CalendarEntryListResponse)
async def list_calendar_entries(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    term: Annotated[str | None, Query(max_length=50)] = None,
    academic_year: Annotated[str | None, Query(max_length=20)] = None,
    entry_type: CalendarEntryType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CalendarEntryListResponse:
    """List governed academic calendar entries visible to the caller."""

    entries, total = await service.list_entries(
        university_id=current_user.university_id,
        role=current_user.role,
        limit=limit,
        offset=offset,
        term=term,
        academic_year=academic_year,
        entry_type=entry_type,
    )
    return CalendarEntryListResponse(
        entries=[_entry_to_response(entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/upcoming", response_model=CalendarEntryListResponse)
async def upcoming_calendar_entries(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    as_of: date | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> CalendarEntryListResponse:
    """Return upcoming governed academic calendar entries."""

    entries = await service.upcoming_entries(
        university_id=current_user.university_id,
        role=current_user.role,
        as_of=as_of or date.today(),
        limit=limit,
    )
    return CalendarEntryListResponse(
        entries=[_entry_to_response(entry) for entry in entries],
        total=len(entries),
        limit=limit,
        offset=0,
    )


@router.get("/search", response_model=CalendarEntryListResponse)
async def search_calendar_entries(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    q: Annotated[str, Query(min_length=1, max_length=255)],
    entry_type: CalendarEntryType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> CalendarEntryListResponse:
    """Search governed academic calendar entries visible to the caller."""

    try:
        entries, total = await service.search_entries(
            university_id=current_user.university_id,
            role=current_user.role,
            query=q,
            limit=limit,
            offset=offset,
            entry_type=entry_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return CalendarEntryListResponse(
        entries=[_entry_to_response(entry) for entry in entries],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{entry_id}", response_model=CalendarEntryResponse)
async def get_calendar_entry(
    entry_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[CalendarService, Depends(get_calendar_service)],
) -> CalendarEntryResponse:
    """Retrieve one governed academic calendar entry visible to the caller."""

    entry = await service.retrieve_entry(
        university_id=current_user.university_id,
        entry_id=entry_id,
        role=current_user.role,
    )
    if entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Calendar entry not found",
        )
    return _entry_to_response(entry)


@router.post("", response_model=CalendarEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_calendar_entry(
    entry_data: CalendarEntryCreate,
    current_user: AdminUser,
    service: Annotated[CalendarService, Depends(get_calendar_service)],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> CalendarEntryResponse:
    """Create a governed academic calendar entry."""

    logger.info(
        "calendar_entry_create_requested actor_id=%s university_id=%s",
        current_user.user_id,
        current_user.university_id,
    )
    entry = await service.create_entry(
        entry_data=entry_data.model_copy(update={"university_id": current_user.university_id}),
        university_id=current_user.university_id,
        actor_id=current_user.user_id,
        event_context=EventContext(
            actor_id=current_user.user_id,
            correlation_id=correlation_id,
        ),
    )
    return _entry_to_response(entry)


def _entry_to_response(entry: AcademicCalendarEntry) -> CalendarEntryResponse:
    """Convert an ORM entry to an API response without leaking internals."""

    return CalendarEntryResponse(
        id=entry.id,
        university_id=entry.university_id,
        title=entry.title,
        description=entry.description,
        term=entry.term,
        academic_year=entry.academic_year,
        entry_type=entry.entry_type,
        start_date=entry.start_date,
        end_date=entry.end_date,
        source_url=entry.source_url,
        verification_status=entry.verification_status,
        status=entry.status,
        last_verified_at=entry.last_verified_at,
        metadata=entry.metadata_,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )
