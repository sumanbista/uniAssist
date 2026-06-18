"""Service layer for governed contact directory records."""

from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.domains.auth.models.roles import UserRole
from app.domains.contacts.models import Contact
from app.domains.contacts.repositories import ContactsRepository
from app.domains.contacts.schemas import ContactCreate, ContactType
from app.shared.events import EventBus, EventContext

logger = get_logger(__name__)

PUBLIC_VISIBLE_STATUSES = ("verified", "published")
ADMIN_VISIBLE_STATUSES = ("pending_review", "stale", "verified", "published")
ADMIN_ROLES = {UserRole.ADMIN, UserRole.UNIVERSITY_ADMIN, UserRole.SUPER_ADMIN}


class ContactsService:
    """Coordinate Contacts domain validation, governance, and events."""

    def __init__(
        self,
        repository: ContactsRepository,
        event_bus: EventBus | None = None,
    ) -> None:
        self.repository = repository
        self.event_bus = event_bus

    async def create_contact(
        self,
        contact_data: ContactCreate,
        university_id: UUID,
        actor_id: UUID,
        event_context: EventContext,
    ) -> Contact:
        """Create a tenant-scoped contact and emit an audit event."""

        contact_type = _normalize_contact_type(contact_data.contact_type)
        contact = Contact(
            university_id=university_id,
            name=contact_data.name,
            title=contact_data.title,
            department=contact_data.department,
            email=str(contact_data.email).casefold(),
            phone=contact_data.phone,
            office_location=contact_data.office_location,
            office_hours=contact_data.office_hours,
            contact_type=contact_type,
            source_url=str(contact_data.source_url) if contact_data.source_url else None,
            verification_status=contact_data.verification_status,
            status=contact_data.status,
            last_verified_at=contact_data.last_verified_at,
            metadata_=contact_data.metadata,
        )
        created_contact = await self.repository.create_contact(contact)
        logger.info(
            "contact_created actor_id=%s university_id=%s contact_id=%s",
            actor_id,
            university_id,
            created_contact.id,
        )
        if self.event_bus is not None:
            await self.event_bus.emit_event(
                event_type="contact.created",
                aggregate_type="contact",
                aggregate_id=created_contact.id,
                university_id=university_id,
                actor_id=actor_id,
                correlation_id=event_context.correlation_id,
                payload={
                    "actor_id": str(actor_id),
                    "university_id": str(university_id),
                    "contact_id": str(created_contact.id),
                    "correlation_id": str(event_context.correlation_id)
                    if event_context.correlation_id
                    else None,
                },
            )
        return created_contact

    async def retrieve_contact(
        self,
        university_id: UUID,
        contact_id: UUID,
        role: UserRole,
    ) -> Contact | None:
        """Retrieve a visible tenant-scoped contact."""

        statuses = self._visible_statuses(role)
        return await self.repository.get_contact_by_id(
            university_id=university_id,
            contact_id=contact_id,
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
        )

    async def list_contacts(
        self,
        university_id: UUID,
        role: UserRole,
        limit: int,
        offset: int,
        department: str | None = None,
        contact_type: ContactType | str | None = None,
    ) -> tuple[list[Contact], int]:
        """List visible tenant-scoped contacts."""

        statuses = self._visible_statuses(role)
        return await self.repository.list_contacts(
            university_id=university_id,
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
            limit=limit,
            offset=offset,
            department=_normalize_optional_filter(department),
            contact_type=_normalize_contact_type(contact_type)
            if contact_type is not None
            else None,
        )

    async def search_contacts(
        self,
        university_id: UUID,
        role: UserRole,
        query: str,
        limit: int,
        offset: int = 0,
    ) -> tuple[list[Contact], int]:
        """Search visible tenant-scoped contacts."""

        statuses = self._visible_statuses(role)
        return await self.repository.search_contacts(
            university_id=university_id,
            query_text=_normalize_required_query(query),
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
            limit=limit,
            offset=offset,
        )

    async def search_by_department(
        self,
        university_id: UUID,
        role: UserRole,
        department: str,
        limit: int,
        offset: int = 0,
    ) -> tuple[list[Contact], int]:
        """Search visible contacts by department."""

        statuses = self._visible_statuses(role)
        return await self.repository.search_by_department(
            university_id=university_id,
            department=_normalize_required_query(department),
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
            limit=limit,
            offset=offset,
        )

    async def search_by_contact_type(
        self,
        university_id: UUID,
        role: UserRole,
        contact_type: ContactType | str,
        limit: int,
        offset: int = 0,
    ) -> tuple[list[Contact], int]:
        """Search visible contacts by contact type."""

        statuses = self._visible_statuses(role)
        return await self.repository.search_by_contact_type(
            university_id=university_id,
            contact_type=_normalize_contact_type(contact_type),
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def _visible_statuses(role: UserRole) -> tuple[str, ...]:
        """Return lifecycle states visible to this role."""

        if role in ADMIN_ROLES:
            return ADMIN_VISIBLE_STATUSES
        return PUBLIC_VISIBLE_STATUSES


def _normalize_contact_type(contact_type: ContactType | str) -> str:
    """Normalize contact type enum values."""

    if isinstance(contact_type, ContactType):
        return contact_type.value
    return ContactType(contact_type).value


def _normalize_optional_filter(value: str | None) -> str | None:
    """Normalize optional exact-match filters."""

    if value is None:
        return None
    normalized_value = " ".join(value.strip().split())
    return normalized_value or None


def _normalize_required_query(value: str) -> str:
    """Normalize a free-text query for safe SQL parameterization."""

    normalized_value = " ".join(value.strip().split())
    if not normalized_value:
        raise ValueError("query is required")
    if any(ord(character) < 32 for character in normalized_value):
        raise ValueError("query contains unsupported control characters")
    return normalized_value


def contact_to_dict(contact: Contact) -> dict[str, Any]:
    """Serialize a contact for deterministic tool results."""

    return {
        "id": str(contact.id),
        "university_id": str(contact.university_id),
        "name": contact.name,
        "title": contact.title,
        "department": contact.department,
        "email": contact.email,
        "phone": contact.phone,
        "office_location": contact.office_location,
        "office_hours": contact.office_hours,
        "contact_type": contact.contact_type,
        "source_url": contact.source_url,
        "verification_status": contact.verification_status,
        "status": contact.status,
        "last_verified_at": contact.last_verified_at.isoformat()
        if contact.last_verified_at
        else None,
        "metadata": contact.metadata_,
    }

