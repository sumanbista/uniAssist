"""Service and orchestration tests for the Calendar domain."""

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.auth.models.roles import UserRole
from app.domains.calendar.schemas import CalendarEntryCreate
from app.domains.calendar.services import CalendarService
from app.domains.orchestration.schemas import ExecutionStep, OrchestrationToolName
from app.domains.orchestration.services import CalendarQueryTool
from app.shared.events import EventBus
from app.tests.calendar_helpers import (
    FakeCalendarRepository,
    InMemoryEventStore,
    calendar_entry,
)


@pytest.mark.anyio
async def test_student_visibility_hides_pending_review_and_admin_can_see_it() -> None:
    """Student reads should hide pending review, while admins can see it."""

    university_id = uuid4()
    entries = [
        calendar_entry(university_id=university_id, title="Published Holiday"),
        calendar_entry(
            university_id=university_id,
            title="Pending Finals Week",
            entry_type="finals_week",
            status="pending_review",
            verification_status="pending_review",
        ),
        calendar_entry(
            university_id=university_id,
            title="Rejected Break",
            status="rejected",
            verification_status="rejected",
        ),
    ]
    service = CalendarService(FakeCalendarRepository(entries))

    student_entries, _student_total = await service.list_entries(
        university_id=university_id,
        role=UserRole.STUDENT,
        limit=20,
        offset=0,
    )
    admin_entries, _admin_total = await service.list_entries(
        university_id=university_id,
        role=UserRole.ADMIN,
        limit=20,
        offset=0,
    )

    assert [entry.title for entry in student_entries] == ["Published Holiday"]
    assert {entry.title for entry in admin_entries} == {
        "Published Holiday",
        "Pending Finals Week",
    }


@pytest.mark.anyio
async def test_upcoming_calendar_entries_and_search_by_entry_type() -> None:
    """Calendar service should return upcoming entries and type-filtered search."""

    university_id = uuid4()
    service = CalendarService(
        FakeCalendarRepository(
            [
                calendar_entry(
                    university_id=university_id,
                    title="Finals Week",
                    entry_type="finals_week",
                    start_date=date.today() + timedelta(days=14),
                ),
                calendar_entry(
                    university_id=university_id,
                    title="Old Holiday",
                    entry_type="holiday",
                    start_date=date.today() - timedelta(days=14),
                ),
            ]
        )
    )

    upcoming = await service.upcoming_entries(
        university_id=university_id,
        role=UserRole.STUDENT,
        as_of=date.today(),
        limit=10,
    )
    finals, total = await service.search_entries(
        university_id=university_id,
        role=UserRole.STUDENT,
        query="Finals",
        entry_type="finals_week",
        limit=10,
        offset=0,
    )

    assert [entry.title for entry in upcoming] == ["Finals Week"]
    assert total == 1
    assert finals[0].entry_type == "finals_week"


@pytest.mark.anyio
async def test_calendar_entry_created_event_emitted_from_service() -> None:
    """Calendar service should emit calendar.entry_created with audit context."""

    university_id = uuid4()
    actor_id = uuid4()
    correlation_id = uuid4()
    store = InMemoryEventStore()
    service = CalendarService(
        FakeCalendarRepository(),
        event_bus=EventBus(store),
    )

    created = await service.create_entry(
        entry_data=CalendarEntryCreate(
            title="Registration Opens",
            entry_type="registration_period",
            start_date=date.today() + timedelta(days=30),
        ),
        university_id=university_id,
        actor_id=actor_id,
        event_context=SimpleNamespace(actor_id=actor_id, correlation_id=correlation_id),
    )

    assert [event.event_type for event in store.events] == ["calendar.entry_created"]
    assert store.events[0].aggregate_id == created.id
    assert store.events[0].payload["actor_id"] == str(actor_id)
    assert store.events[0].payload["university_id"] == str(university_id)
    assert store.events[0].payload["entity_id"] == str(created.id)
    assert store.events[0].payload["correlation_id"] == str(correlation_id)


@pytest.mark.anyio
async def test_orchestrator_calendar_query_tool_works() -> None:
    """The deterministic orchestration calendar_query tool should use CalendarService."""

    university_id = uuid4()
    service = CalendarService(
        FakeCalendarRepository(
            [
                calendar_entry(
                    university_id=university_id,
                    title="Finals Week",
                    entry_type="finals_week",
                )
            ]
        )
    )
    tool = CalendarQueryTool(service)

    result = await tool.run(
        step=ExecutionStep(
            step_id=1,
            tool_name=OrchestrationToolName.CALENDAR_QUERY,
            params={"query": "When are finals?", "limit": 5},
            timeout_seconds=1,
        ),
        university_id=university_id,
        prior_results=[],
        role=UserRole.STUDENT,
    )

    assert result.tool_name == OrchestrationToolName.CALENDAR_QUERY
    assert result.data[0]["title"] == "Finals Week"
    assert result.metadata["trace"]["tenant_scoped"] is True
    assert result.metadata["trace"]["governance_filtered"] is True
