"""Shared Calendar test helpers."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from app.domains.auth.models.roles import UserRole
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.calendar.models import AcademicCalendarEntry
from app.domains.calendar.services import CalendarService
from app.shared.events import PlatformEvent


class InMemoryEventStore:
    """In-memory event store for event assertions."""

    def __init__(self) -> None:
        self.events: list[PlatformEvent] = []

    async def append(self, event: PlatformEvent) -> PlatformEvent:
        """Append an event."""

        self.events.append(event)
        return event


class FakeCalendarRepository:
    """Repository fake with service-compatible Calendar behavior."""

    def __init__(self, entries: list[AcademicCalendarEntry] | None = None) -> None:
        self.entries = entries or []
        self.created_entries: list[AcademicCalendarEntry] = []

    async def create_entry(self, entry: AcademicCalendarEntry) -> AcademicCalendarEntry:
        """Persist an entry in memory."""

        now = datetime.now(UTC)
        entry.id = entry.id or uuid4()
        entry.created_at = now
        entry.updated_at = now
        self.entries.append(entry)
        self.created_entries.append(entry)
        return entry

    async def get_entry_by_id(
        self,
        university_id,
        entry_id,
        visible_statuses,
        visible_verification_statuses,
    ):
        """Return one visible entry."""

        for entry in self._visible(university_id, visible_statuses, visible_verification_statuses):
            if entry.id == entry_id:
                return entry
        return None

    async def list_entries(
        self,
        university_id,
        visible_statuses,
        visible_verification_statuses,
        limit,
        offset,
        term=None,
        academic_year=None,
        entry_type=None,
    ):
        """Return visible entries matching optional filters."""

        entries = self._visible(university_id, visible_statuses, visible_verification_statuses)
        if term is not None:
            entries = [entry for entry in entries if entry.term == term]
        if academic_year is not None:
            entries = [entry for entry in entries if entry.academic_year == academic_year]
        if entry_type is not None:
            entries = [entry for entry in entries if entry.entry_type == entry_type]
        return entries[offset : offset + limit], len(entries)

    async def search_entries(
        self,
        university_id,
        query_text,
        visible_statuses,
        visible_verification_statuses,
        limit,
        offset,
        entry_type=None,
    ):
        """Return visible entries matching query text and optional type."""

        query = query_text.casefold()
        entries = self._visible(university_id, visible_statuses, visible_verification_statuses)
        entries = [
            entry
            for entry in entries
            if query in entry.title.casefold()
            or (entry.description is not None and query in entry.description.casefold())
            or (entry.term is not None and query in entry.term.casefold())
        ]
        if entry_type is not None:
            entries = [entry for entry in entries if entry.entry_type == entry_type]
        return entries[offset : offset + limit], len(entries)

    async def upcoming_entries(
        self,
        university_id,
        as_of,
        visible_statuses,
        visible_verification_statuses,
        limit,
    ):
        """Return upcoming visible entries."""

        entries = [
            entry
            for entry in self._visible(
                university_id,
                visible_statuses,
                visible_verification_statuses,
            )
            if entry.start_date is not None and entry.start_date >= as_of
        ]
        return sorted(entries, key=lambda entry: entry.start_date)[:limit]

    def _visible(
        self,
        university_id,
        visible_statuses,
        visible_verification_statuses,
    ) -> list[AcademicCalendarEntry]:
        """Apply tenant and governance filters."""

        return [
            entry
            for entry in self.entries
            if entry.university_id == university_id
            and entry.is_active
            and entry.status in visible_statuses
            and entry.verification_status in visible_verification_statuses
        ]


class FakeRouteCalendarService:
    """Route dependency fake preserving Calendar API contracts."""

    def __init__(self, entries: list[AcademicCalendarEntry], store: InMemoryEventStore) -> None:
        self.entries = entries
        self.store = store
        self.create_calls: list[tuple[UUID, UUID]] = []
        self.list_university_ids: list[UUID] = []

    async def create_entry(self, entry_data, university_id, actor_id, event_context):
        """Create an entry and emit a matching event."""

        self.create_calls.append((university_id, actor_id))
        entry = calendar_entry(
            university_id=university_id,
            title=entry_data.title,
            status=entry_data.status,
            verification_status=entry_data.verification_status,
            entry_type=entry_data.entry_type.value,
            start_date=entry_data.start_date,
        )
        self.entries.append(entry)
        await self.store.append(
            PlatformEvent(
                event_type="calendar.entry_created",
                aggregate_type="calendar_entry",
                aggregate_id=entry.id,
                university_id=university_id,
                actor_id=actor_id,
                correlation_id=event_context.correlation_id,
                payload={
                    "actor_id": str(actor_id),
                    "university_id": str(university_id),
                    "entity_id": str(entry.id),
                    "correlation_id": str(event_context.correlation_id)
                    if event_context.correlation_id
                    else None,
                },
            )
        )
        return entry

    async def list_entries(self, **kwargs):
        """List entries through the real service filtering rules."""

        self.list_university_ids.append(kwargs["university_id"])
        service = CalendarService(FakeCalendarRepository(self.entries))
        return await service.list_entries(**kwargs)

    async def search_entries(self, **kwargs):
        """Search entries through the real service filtering rules."""

        service = CalendarService(FakeCalendarRepository(self.entries))
        return await service.search_entries(**kwargs)

    async def upcoming_entries(self, **kwargs):
        """Return upcoming entries through the real service filtering rules."""

        service = CalendarService(FakeCalendarRepository(self.entries))
        return await service.upcoming_entries(**kwargs)

    async def retrieve_entry(self, **kwargs):
        """Retrieve one entry through the real service filtering rules."""

        service = CalendarService(FakeCalendarRepository(self.entries))
        return await service.retrieve_entry(**kwargs)


def calendar_entry(**overrides) -> AcademicCalendarEntry:
    """Build a calendar entry model for tests."""

    values = {
        "id": uuid4(),
        "university_id": uuid4(),
        "title": "Spring Break",
        "description": "No classes",
        "term": "Spring",
        "academic_year": "2026-2027",
        "entry_type": "break",
        "start_date": date.today() + timedelta(days=7),
        "end_date": date.today() + timedelta(days=11),
        "source_url": "https://example.edu/calendar",
        "source_hash": uuid4().hex + uuid4().hex,
        "status": "verified",
        "verification_status": "verified",
        "last_verified_at": datetime.now(UTC),
        "metadata_": {},
        "is_active": True,
        "extracted_at": datetime.now(UTC),
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return AcademicCalendarEntry(**values)


def user(role: UserRole, university_id: UUID) -> AuthenticatedUser:
    """Build an authenticated user for dependency overrides."""

    return AuthenticatedUser(user_id=uuid4(), university_id=university_id, role=role)


def override_user(current_user: AuthenticatedUser):
    """Return a FastAPI dependency override for current user."""

    async def dependency() -> AuthenticatedUser:
        return current_user

    return dependency
