"""Service layer for governed academic calendar records."""

from datetime import UTC, date, datetime
from hashlib import sha256
from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.domains.auth.models.roles import UserRole
from app.domains.calendar.models import AcademicCalendarEntry
from app.domains.calendar.repositories import CalendarRepository
from app.domains.calendar.schemas import CalendarEntryCreate, CalendarEntryType
from app.shared.events import EventBus, EventContext

logger = get_logger(__name__)

PUBLIC_VISIBLE_STATUSES = ("verified", "published")
ADMIN_VISIBLE_STATUSES = ("pending_review", "stale", "verified", "published")


class CalendarService:
    """Coordinate Calendar domain validation, governance, and events."""

    def __init__(
        self,
        repository: CalendarRepository,
        event_bus: EventBus | None = None,
    ) -> None:
        self.repository = repository
        self.event_bus = event_bus

    async def create_entry(
        self,
        entry_data: CalendarEntryCreate,
        university_id: UUID,
        actor_id: UUID,
        event_context: EventContext,
    ) -> AcademicCalendarEntry:
        """Create a tenant-scoped calendar entry and emit an audit event."""

        entry_type = _normalize_entry_type(entry_data.entry_type)
        entry = AcademicCalendarEntry(
            university_id=university_id,
            title=entry_data.title,
            description=entry_data.description,
            term=_normalize_optional_filter(entry_data.term),
            academic_year=_normalize_optional_filter(entry_data.academic_year),
            entry_type=entry_type,
            start_date=entry_data.start_date,
            end_date=entry_data.end_date,
            source_url=str(entry_data.source_url) if entry_data.source_url else None,
            source_hash=_source_hash(university_id, entry_data, entry_type),
            verification_status=entry_data.verification_status,
            status=entry_data.status,
            last_verified_at=entry_data.last_verified_at,
            extracted_at=datetime.now(UTC),
            metadata_=entry_data.metadata,
        )
        created_entry = await self.repository.create_entry(entry)
        logger.info(
            "calendar_entry_created actor_id=%s university_id=%s entry_id=%s",
            actor_id,
            university_id,
            created_entry.id,
        )
        if self.event_bus is not None:
            await self.event_bus.emit_event(
                event_type="calendar.entry_created",
                aggregate_type="calendar_entry",
                aggregate_id=created_entry.id,
                university_id=university_id,
                actor_id=actor_id,
                correlation_id=event_context.correlation_id,
                payload={
                    "actor_id": str(actor_id),
                    "university_id": str(university_id),
                    "entity_id": str(created_entry.id),
                    "correlation_id": str(event_context.correlation_id)
                    if event_context.correlation_id
                    else None,
                },
            )
        return created_entry

    async def retrieve_entry(
        self,
        university_id: UUID,
        entry_id: UUID,
        role: UserRole,
    ) -> AcademicCalendarEntry | None:
        """Retrieve a visible tenant-scoped calendar entry."""

        statuses = self._visible_statuses(role)
        return await self.repository.get_entry_by_id(
            university_id=university_id,
            entry_id=entry_id,
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
        )

    async def list_entries(
        self,
        university_id: UUID,
        role: UserRole,
        limit: int,
        offset: int,
        term: str | None = None,
        academic_year: str | None = None,
        entry_type: CalendarEntryType | None = None,
    ) -> tuple[list[AcademicCalendarEntry], int]:
        """List visible tenant-scoped entries."""

        statuses = self._visible_statuses(role)
        return await self.repository.list_entries(
            university_id=university_id,
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
            limit=limit,
            offset=offset,
            term=_normalize_optional_filter(term),
            academic_year=_normalize_optional_filter(academic_year),
            entry_type=_normalize_entry_type(entry_type) if entry_type is not None else None,
        )

    async def search_entries(
        self,
        university_id: UUID,
        role: UserRole,
        query: str,
        limit: int,
        offset: int,
        entry_type: CalendarEntryType | None = None,
    ) -> tuple[list[AcademicCalendarEntry], int]:
        """Search visible tenant-scoped entries."""

        normalized_query = _normalize_required_query(query)
        statuses = self._visible_statuses(role)
        return await self.repository.search_entries(
            university_id=university_id,
            query_text=normalized_query,
            visible_statuses=statuses,
            visible_verification_statuses=statuses,
            limit=limit,
            offset=offset,
            entry_type=_normalize_entry_type(entry_type) if entry_type is not None else None,
        )

    async def upcoming_entries(
        self,
        university_id: UUID,
        role: UserRole,
        as_of: date,
        limit: int,
    ) -> list[AcademicCalendarEntry]:
        """Return upcoming visible tenant-scoped entries."""

        statuses = self._visible_statuses(role)
        return await self.repository.upcoming_entries(
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


def _normalize_entry_type(entry_type: CalendarEntryType | str) -> str:
    """Normalize entry type enum values."""

    if isinstance(entry_type, CalendarEntryType):
        return entry_type.value
    return CalendarEntryType(entry_type).value


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


def _source_hash(
    university_id: UUID,
    entry_data: CalendarEntryCreate,
    entry_type: str,
) -> str:
    """Build a deterministic source hash for manually created entries."""

    source = "|".join(
        [
            str(university_id),
            entry_data.title,
            entry_data.start_date.isoformat(),
            entry_data.end_date.isoformat() if entry_data.end_date else "",
            entry_type,
            str(entry_data.source_url) if entry_data.source_url else "",
        ]
    )
    return sha256(source.encode("utf-8")).hexdigest()


def calendar_entry_to_dict(entry: AcademicCalendarEntry) -> dict[str, Any]:
    """Serialize a calendar entry for deterministic tool results."""

    return {
        "id": str(entry.id),
        "university_id": str(entry.university_id),
        "title": entry.title,
        "description": entry.description,
        "term": entry.term,
        "academic_year": entry.academic_year,
        "entry_type": entry.entry_type,
        "start_date": entry.start_date.isoformat() if entry.start_date else None,
        "end_date": entry.end_date.isoformat() if entry.end_date else None,
        "source_url": entry.source_url,
        "verification_status": entry.verification_status,
        "status": entry.status,
        "last_verified_at": entry.last_verified_at.isoformat()
        if entry.last_verified_at
        else None,
        "metadata": entry.metadata_,
    }
