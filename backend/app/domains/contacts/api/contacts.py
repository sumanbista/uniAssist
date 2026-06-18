"""FastAPI routes for the governed Contacts domain."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.auth.services import GOVERNANCE_ADMIN_ROLES
from app.domains.contacts.models import Contact
from app.domains.contacts.repositories import ContactsRepository
from app.domains.contacts.schemas import (
    ContactCreate,
    ContactListResponse,
    ContactResponse,
    ContactType,
)
from app.domains.contacts.services import ContactsService
from app.shared.auth import get_current_user, require_any_role
from app.shared.database.session import get_db_session
from app.shared.events import EventBus, EventContext, EventStore

router = APIRouter(prefix="/contacts", tags=["contacts"])
logger = get_logger(__name__)

AdminUser = Annotated[
    AuthenticatedUser,
    Depends(require_any_role(GOVERNANCE_ADMIN_ROLES)),
]


def get_contacts_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ContactsService:
    """Build a Contacts service for a request."""

    return ContactsService(
        repository=ContactsRepository(session),
        event_bus=EventBus(EventStore(session)),
    )


@router.get("", response_model=ContactListResponse)
async def list_contacts(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContactsService, Depends(get_contacts_service)],
    department: Annotated[str | None, Query(max_length=255)] = None,
    contact_type: ContactType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ContactListResponse:
    """List governed contacts visible to the caller."""

    contacts, total = await service.list_contacts(
        university_id=current_user.university_id,
        role=current_user.role,
        limit=limit,
        offset=offset,
        department=department,
        contact_type=contact_type,
    )
    return ContactListResponse(
        contacts=[_contact_to_response(contact) for contact in contacts],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/search", response_model=ContactListResponse)
async def search_contacts(
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContactsService, Depends(get_contacts_service)],
    q: Annotated[str | None, Query(min_length=1, max_length=255)] = None,
    department: Annotated[str | None, Query(max_length=255)] = None,
    contact_type: ContactType | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ContactListResponse:
    """Search governed contacts visible to the caller."""

    try:
        if q is not None:
            contacts, total = await service.search_contacts(
                university_id=current_user.university_id,
                role=current_user.role,
                query=q,
                limit=limit,
                offset=offset,
            )
        elif department is not None:
            contacts, total = await service.search_by_department(
                university_id=current_user.university_id,
                role=current_user.role,
                department=department,
                limit=limit,
                offset=offset,
            )
        elif contact_type is not None:
            contacts, total = await service.search_by_contact_type(
                university_id=current_user.university_id,
                role=current_user.role,
                contact_type=contact_type,
                limit=limit,
                offset=offset,
            )
        else:
            raise ValueError("provide q, department, or contact_type")
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    return ContactListResponse(
        contacts=[_contact_to_response(contact) for contact in contacts],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{contact_id}", response_model=ContactResponse)
async def get_contact(
    contact_id: UUID,
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[ContactsService, Depends(get_contacts_service)],
) -> ContactResponse:
    """Retrieve one governed contact visible to the caller."""

    contact = await service.retrieve_contact(
        university_id=current_user.university_id,
        contact_id=contact_id,
        role=current_user.role,
    )
    if contact is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contact not found",
        )
    return _contact_to_response(contact)


@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    contact_data: ContactCreate,
    current_user: AdminUser,
    service: Annotated[ContactsService, Depends(get_contacts_service)],
    correlation_id: Annotated[UUID | None, Header(alias="X-Correlation-ID")] = None,
) -> ContactResponse:
    """Create a governed contact."""

    logger.info(
        "contact_create_requested actor_id=%s university_id=%s",
        current_user.user_id,
        current_user.university_id,
    )
    contact = await service.create_contact(
        contact_data=contact_data.model_copy(
            update={"university_id": current_user.university_id}
        ),
        university_id=current_user.university_id,
        actor_id=current_user.user_id,
        event_context=EventContext(
            actor_id=current_user.user_id,
            correlation_id=correlation_id,
        ),
    )
    return _contact_to_response(contact)


def _contact_to_response(contact: Contact) -> ContactResponse:
    """Convert an ORM contact to an API response without leaking internals."""

    return ContactResponse(
        id=contact.id,
        university_id=contact.university_id,
        name=contact.name,
        title=contact.title,
        department=contact.department,
        email=contact.email,
        phone=contact.phone,
        office_location=contact.office_location,
        office_hours=contact.office_hours,
        contact_type=contact.contact_type,
        source_url=contact.source_url,
        verification_status=contact.verification_status,
        status=contact.status,
        last_verified_at=contact.last_verified_at,
        metadata=contact.metadata_,
        created_at=contact.created_at,
        updated_at=contact.updated_at,
    )

