"""Service and orchestration tests for the Deadline domain."""

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.auth.models.roles import UserRole
from app.domains.deadlines.schemas import DeadlineCreate
from app.domains.deadlines.services import DeadlineService
from app.domains.orchestration.schemas import ExecutionStep, OrchestrationToolName
from app.domains.orchestration.services import DeadlineQueryTool
from app.shared.events import EventBus
from app.tests.deadline_helpers import (
    FakeDeadlineRepository,
    InMemoryEventStore,
    deadline_record,
)


@pytest.mark.anyio
async def test_student_visibility_hides_pending_review_and_admin_can_see_it() -> None:
    """Student reads should hide pending review, while admins can see it."""

    university_id = uuid4()
    deadlines = [
        deadline_record(university_id=university_id, title="Published Withdrawal"),
        deadline_record(
            university_id=university_id,
            title="Pending Tuition",
            deadline_type="tuition_due",
            status="pending_review",
            verification_status="pending_review",
        ),
        deadline_record(
            university_id=university_id,
            title="Archived Registration",
            status="archived",
            verification_status="verified",
        ),
    ]
    service = DeadlineService(FakeDeadlineRepository(deadlines))

    student_deadlines, _student_total = await service.list_deadlines(
        university_id=university_id,
        role=UserRole.STUDENT,
        limit=20,
        offset=0,
    )
    admin_deadlines, _admin_total = await service.list_deadlines(
        university_id=university_id,
        role=UserRole.ADMIN,
        limit=20,
        offset=0,
    )

    assert [deadline.title for deadline in student_deadlines] == ["Published Withdrawal"]
    assert {deadline.title for deadline in admin_deadlines} == {
        "Published Withdrawal",
        "Pending Tuition",
    }


@pytest.mark.anyio
async def test_upcoming_deadlines_and_search_by_deadline_type() -> None:
    """Deadline service should return upcoming and type-filtered deadlines."""

    university_id = uuid4()
    service = DeadlineService(
        FakeDeadlineRepository(
            [
                deadline_record(
                    university_id=university_id,
                    title="Tuition Due",
                    deadline_type="tuition_due",
                    due_date=date.today() + timedelta(days=14),
                ),
                deadline_record(
                    university_id=university_id,
                    title="Old Housing Deadline",
                    deadline_type="housing",
                    due_date=date.today() - timedelta(days=14),
                ),
            ]
        )
    )

    upcoming = await service.upcoming_deadlines(
        university_id=university_id,
        role=UserRole.STUDENT,
        as_of=date.today(),
        limit=10,
    )
    tuition, total = await service.search_deadlines(
        university_id=university_id,
        role=UserRole.STUDENT,
        query="Tuition",
        deadline_type="tuition_due",
        limit=10,
        offset=0,
    )

    assert [deadline.title for deadline in upcoming] == ["Tuition Due"]
    assert total == 1
    assert tuition[0].deadline_type == "tuition_due"


@pytest.mark.anyio
async def test_deadline_created_event_emitted_from_service() -> None:
    """Deadline service should emit deadline.created with audit context."""

    university_id = uuid4()
    actor_id = uuid4()
    correlation_id = uuid4()
    store = InMemoryEventStore()
    service = DeadlineService(
        FakeDeadlineRepository(),
        event_bus=EventBus(store),
    )

    created = await service.create_deadline(
        deadline_data=DeadlineCreate(
            title="Registration Deadline",
            deadline_type="registration",
            due_date=date.today() + timedelta(days=30),
        ),
        university_id=university_id,
        actor_id=actor_id,
        event_context=SimpleNamespace(actor_id=actor_id, correlation_id=correlation_id),
    )

    assert [event.event_type for event in store.events] == ["deadline.created"]
    assert store.events[0].aggregate_id == created.id
    assert store.events[0].payload["actor_id"] == str(actor_id)
    assert store.events[0].payload["university_id"] == str(university_id)
    assert store.events[0].payload["entity_id"] == str(created.id)
    assert store.events[0].payload["correlation_id"] == str(correlation_id)


@pytest.mark.anyio
async def test_orchestrator_deadline_query_tool_works() -> None:
    """The deterministic orchestration deadline_query tool should use DeadlineService."""

    university_id = uuid4()
    service = DeadlineService(
        FakeDeadlineRepository(
            [
                deadline_record(
                    university_id=university_id,
                    title="Withdrawal Deadline",
                    deadline_type="withdrawal",
                )
            ]
        )
    )
    tool = DeadlineQueryTool(service)

    result = await tool.run(
        step=ExecutionStep(
            step_id=1,
            tool_name=OrchestrationToolName.DEADLINE_QUERY,
            params={"query": "When is the withdrawal deadline?", "limit": 5},
            timeout_seconds=1,
        ),
        university_id=university_id,
        prior_results=[],
        role=UserRole.STUDENT,
    )

    assert result.tool_name == OrchestrationToolName.DEADLINE_QUERY
    assert result.data[0]["title"] == "Withdrawal Deadline"
    assert result.metadata["trace"]["tenant_scoped"] is True
    assert result.metadata["trace"]["governance_filtered"] is True
