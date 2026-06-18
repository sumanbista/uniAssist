"""Shared Deadline test helpers."""

from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid4

from app.domains.auth.models.roles import UserRole
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.deadlines.models import Deadline
from app.domains.deadlines.schemas import RelatedFormSummary
from app.domains.deadlines.services import DeadlineService
from app.shared.events import PlatformEvent


class InMemoryEventStore:
    """In-memory event store for event assertions."""

    def __init__(self) -> None:
        self.events: list[PlatformEvent] = []

    async def append(self, event: PlatformEvent) -> PlatformEvent:
        """Append an event."""

        self.events.append(event)
        return event


class FakeDeadlineRepository:
    """Repository fake with service-compatible Deadline behavior."""

    def __init__(self, deadlines: list[Deadline] | None = None) -> None:
        self.deadlines = deadlines or []
        self.created_deadlines: list[Deadline] = []

    async def create_deadline(self, deadline: Deadline) -> Deadline:
        """Persist a deadline in memory."""

        now = datetime.now(UTC)
        deadline.id = deadline.id or uuid4()
        deadline.created_at = now
        deadline.updated_at = now
        self.deadlines.append(deadline)
        self.created_deadlines.append(deadline)
        return deadline

    async def get_deadline_by_id(
        self,
        university_id,
        deadline_id,
        visible_statuses,
        visible_verification_statuses,
    ):
        """Return one visible deadline."""

        for deadline in self._visible(
            university_id,
            visible_statuses,
            visible_verification_statuses,
        ):
            if deadline.id == deadline_id:
                return deadline
        return None

    async def list_deadlines(
        self,
        university_id,
        visible_statuses,
        visible_verification_statuses,
        limit,
        offset,
        term=None,
        academic_year=None,
        deadline_type=None,
    ):
        """Return visible deadlines matching optional filters."""

        deadlines = self._visible(
            university_id,
            visible_statuses,
            visible_verification_statuses,
        )
        if term is not None:
            deadlines = [deadline for deadline in deadlines if deadline.term == term]
        if academic_year is not None:
            deadlines = [
                deadline for deadline in deadlines if deadline.academic_year == academic_year
            ]
        if deadline_type is not None:
            deadlines = [
                deadline for deadline in deadlines if deadline.deadline_type == deadline_type
            ]
        return deadlines[offset : offset + limit], len(deadlines)

    async def search_deadlines(
        self,
        university_id,
        query_text,
        visible_statuses,
        visible_verification_statuses,
        limit,
        offset,
        deadline_type=None,
    ):
        """Return visible deadlines matching query text and optional type."""

        query = query_text.casefold()
        deadlines = self._visible(
            university_id,
            visible_statuses,
            visible_verification_statuses,
        )
        deadlines = [
            deadline
            for deadline in deadlines
            if query in deadline.title.casefold()
            or (deadline.description is not None and query in deadline.description.casefold())
            or (deadline.term is not None and query in deadline.term.casefold())
        ]
        if deadline_type is not None:
            deadlines = [
                deadline for deadline in deadlines if deadline.deadline_type == deadline_type
            ]
        return deadlines[offset : offset + limit], len(deadlines)

    async def upcoming_deadlines(
        self,
        university_id,
        as_of,
        visible_statuses,
        visible_verification_statuses,
        limit,
    ):
        """Return upcoming visible deadlines."""

        deadlines = [
            deadline
            for deadline in self._visible(
                university_id,
                visible_statuses,
                visible_verification_statuses,
            )
            if deadline.due_date >= as_of
        ]
        return sorted(deadlines, key=lambda deadline: deadline.due_date)[:limit]

    def _visible(
        self,
        university_id,
        visible_statuses,
        visible_verification_statuses,
    ) -> list[Deadline]:
        """Apply tenant and governance filters."""

        return [
            deadline
            for deadline in self.deadlines
            if deadline.university_id == university_id
            and deadline.is_active
            and deadline.status in visible_statuses
            and deadline.verification_status in visible_verification_statuses
        ]


class FakeRouteDeadlineService:
    """Route dependency fake preserving Deadline API contracts."""

    def __init__(self, deadlines: list[Deadline], store: InMemoryEventStore) -> None:
        self.deadlines = deadlines
        self.store = store
        self.create_calls: list[tuple[UUID, UUID]] = []
        self.list_university_ids: list[UUID] = []
        self.related_forms: dict[UUID, RelatedFormSummary] = {}

    async def create_deadline(self, deadline_data, university_id, actor_id, event_context):
        """Create a deadline and emit a matching event."""

        self.create_calls.append((university_id, actor_id))
        deadline = deadline_record(
            university_id=university_id,
            title=deadline_data.title,
            status=deadline_data.status,
            verification_status=deadline_data.verification_status,
            deadline_type=deadline_data.deadline_type.value,
            due_date=deadline_data.due_date,
            related_form_id=deadline_data.related_form_id,
        )
        self.deadlines.append(deadline)
        await self.store.append(
            PlatformEvent(
                event_type="deadline.created",
                aggregate_type="deadline",
                aggregate_id=deadline.id,
                university_id=university_id,
                actor_id=actor_id,
                correlation_id=event_context.correlation_id,
                payload={
                    "actor_id": str(actor_id),
                    "university_id": str(university_id),
                    "entity_id": str(deadline.id),
                    "correlation_id": str(event_context.correlation_id)
                    if event_context.correlation_id
                    else None,
                },
            )
        )
        return deadline

    async def list_deadlines(self, **kwargs):
        """List deadlines through real service filtering rules."""

        self.list_university_ids.append(kwargs["university_id"])
        service = DeadlineService(FakeDeadlineRepository(self.deadlines))
        return await service.list_deadlines(**kwargs)

    async def search_deadlines(self, **kwargs):
        """Search deadlines through real service filtering rules."""

        service = DeadlineService(FakeDeadlineRepository(self.deadlines))
        return await service.search_deadlines(**kwargs)

    async def upcoming_deadlines(self, **kwargs):
        """Return upcoming deadlines through real service filtering rules."""

        service = DeadlineService(FakeDeadlineRepository(self.deadlines))
        return await service.upcoming_deadlines(**kwargs)

    async def retrieve_deadline(self, **kwargs):
        """Retrieve one deadline through real service filtering rules."""

        service = DeadlineService(FakeDeadlineRepository(self.deadlines))
        return await service.retrieve_deadline(**kwargs)

    async def related_form_summary(self, university_id, deadline):
        """Return a configured safe related form summary."""

        if deadline.related_form_id is None:
            return None
        return self.related_forms.get(deadline.related_form_id)


def deadline_record(**overrides) -> Deadline:
    """Build a deadline model for tests."""

    values = {
        "id": uuid4(),
        "university_id": uuid4(),
        "title": "Withdrawal Deadline",
        "description": "Last day to withdraw",
        "term": "Fall",
        "academic_year": "2026-2027",
        "deadline_type": "withdrawal",
        "due_date": date.today() + timedelta(days=7),
        "source_url": "https://example.edu/deadlines",
        "related_form_id": None,
        "verification_status": "verified",
        "status": "verified",
        "last_verified_at": datetime.now(UTC),
        "metadata_": {},
        "is_active": True,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return Deadline(**values)


def user(role: UserRole, university_id: UUID) -> AuthenticatedUser:
    """Build an authenticated user for dependency overrides."""

    return AuthenticatedUser(user_id=uuid4(), university_id=university_id, role=role)


def override_user(current_user: AuthenticatedUser):
    """Return a FastAPI dependency override for current user."""

    async def dependency() -> AuthenticatedUser:
        return current_user

    return dependency
