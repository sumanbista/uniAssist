"""Service layer for governed deadline records."""

from datetime import date
from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.domains.auth.models.roles import UserRole
from app.domains.deadlines.models import Deadline
from app.domains.deadlines.repositories import DeadlineRepository
from app.domains.deadlines.schemas import DeadlineCreate, DeadlineType
from app.shared.events import EventBus, EventContext

logger = get_logger(__name__)

PUBLIC_VISIBLE_STATUSES = ("verified", "published")
ADMIN_VISIBLE_STATUSES = ("pending_review", "stale", "verified", "published")


class DeadlineService:
    """Coordinate Deadline domain validation, governance, and events."""

    def __init__(
        self,
        repository: DeadlineRepository,
        event_bus: EventBus | None = None,
    ) -> None:
        self.repository = repository
        self.event_bus = event_bus

    async def create_deadline(
        self,
        deadline_data: DeadlineCreate,
        university_id: UUID,
        actor_id: UUID,
        event_context: EventContext,
    ) -> Deadline:
        """Create a tenant-scoped deadline and emit an audit event."""

        deadline_type = _normalize_deadline_type(deadline_data.deadline_type)
        deadline = Deadline(
            university_id=university_id,
            title=deadline_data.title,
            description=deadline_data.description,
            term=_normalize_optional_filter(deadline_data.term),
            academic_year=_normalize_optional_filter(deadline_data.academic_year),
            deadline_type=deadline_type,
            due_date=deadline_data.due_date,
            source_url=str(deadline_data.source_url) if deadline_data.source_url else None,
            related_form_id=deadline_data.related_form_id,
            verification_status=deadline_data.verification_status,
            status=deadline_data.status,
            last_verified_at=deadline_data.last_verified_at,
            metadata_=deadline_data.metadata,
        )
        created_deadline = await self.repository.create_deadline(deadline)
        logger.info(
            "deadline_created actor_id=%s university_id=%s deadline_id=%s",
            actor_id,
            university_id,
            created_deadline.id,
        )
        if self.event_bus is not None:
            await self.event_bus.emit_event(
                event_type="deadline.created",
                aggregate_type="deadline",
                aggregate_id=created_deadline.id,
                university_id=university_id,
                actor_id=actor_id,
                correlation_id=event_context.correlation_id,
                payload={
                    "actor_id": str(actor_id),
                    "university_id": str(university_id),
                    "entity_id": str(created_deadline.id),
                    "correlation_id": str(event_context.correlation_id)
                    if event_context.correlation_id
                    else None,
                },
            )
        return created_deadline

    async def retrieve_deadline(
        self,
        university_id: UUID,
        deadline_id: UUID,
        role: UserRole,
    ) -> Deadline | None:
        """Retrieve a visible tenant-scoped deadline."""

        statuses = self._visible_statuses(role)
        return await self.repository.get_deadline_by_id(
            university_id=university_id,
            deadline_id=deadline_id,
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
        )

    async def list_deadlines(
        self,
        university_id: UUID,
        role: UserRole,
        limit: int,
        offset: int,
        term: str | None = None,
        academic_year: str | None = None,
        deadline_type: DeadlineType | str | None = None,
    ) -> tuple[list[Deadline], int]:
        """List visible tenant-scoped deadlines."""

        statuses = self._visible_statuses(role)
        return await self.repository.list_deadlines(
            university_id=university_id,
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
            limit=limit,
            offset=offset,
            term=_normalize_optional_filter(term),
            academic_year=_normalize_optional_filter(academic_year),
            deadline_type=_normalize_deadline_type(deadline_type)
            if deadline_type is not None
            else None,
        )

    async def search_deadlines(
        self,
        university_id: UUID,
        role: UserRole,
        query: str,
        limit: int,
        offset: int,
        deadline_type: DeadlineType | str | None = None,
    ) -> tuple[list[Deadline], int]:
        """Search visible tenant-scoped deadlines."""

        normalized_query = _normalize_required_query(query)
        statuses = self._visible_statuses(role)
        return await self.repository.search_deadlines(
            university_id=university_id,
            query_text=normalized_query,
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
            limit=limit,
            offset=offset,
            deadline_type=_normalize_deadline_type(deadline_type)
            if deadline_type is not None
            else None,
        )

    async def upcoming_deadlines(
        self,
        university_id: UUID,
        role: UserRole,
        as_of: date,
        limit: int,
    ) -> list[Deadline]:
        """Return upcoming visible tenant-scoped deadlines."""

        statuses = self._visible_statuses(role)
        return await self.repository.upcoming_deadlines(
            university_id=university_id,
            as_of=as_of,
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
            limit=limit,
        )

    @staticmethod
    def _visible_statuses(role: UserRole) -> tuple[str, ...]:
        """Return lifecycle states visible to this role."""

        if role in {UserRole.ADMIN, UserRole.UNIVERSITY_ADMIN, UserRole.SUPER_ADMIN}:
            return ADMIN_VISIBLE_STATUSES
        return PUBLIC_VISIBLE_STATUSES


def _normalize_deadline_type(deadline_type: DeadlineType | str) -> str:
    """Normalize deadline type enum values."""

    if isinstance(deadline_type, DeadlineType):
        return deadline_type.value
    return DeadlineType(deadline_type).value


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


def deadline_to_dict(deadline: Deadline) -> dict[str, Any]:
    """Serialize a deadline for deterministic tool results."""

    return {
        "id": str(deadline.id),
        "university_id": str(deadline.university_id),
        "title": deadline.title,
        "description": deadline.description,
        "term": deadline.term,
        "academic_year": deadline.academic_year,
        "deadline_type": deadline.deadline_type,
        "due_date": deadline.due_date.isoformat(),
        "source_url": deadline.source_url,
        "related_form_id": str(deadline.related_form_id)
        if deadline.related_form_id
        else None,
        "verification_status": deadline.verification_status,
        "status": deadline.status,
        "last_verified_at": deadline.last_verified_at.isoformat()
        if deadline.last_verified_at
        else None,
        "metadata": deadline.metadata_,
    }
