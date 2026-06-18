"""API tests for the governed Calendar domain."""

from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.domains.auth.models.roles import UserRole
from app.domains.calendar.api.calendar import get_calendar_service
from app.main import app
from app.shared.auth.dependencies import get_current_user
from app.tests.calendar_helpers import (
    FakeRouteCalendarService,
    InMemoryEventStore,
    override_user,
    user,
)


def test_admin_can_create_calendar_entry_and_event_is_emitted() -> None:
    """Admin users should create tenant-stamped entries and emit audit events."""

    university_id = uuid4()
    actor = user(UserRole.ADMIN, university_id)
    store = InMemoryEventStore()
    service = FakeRouteCalendarService([], store)

    app.dependency_overrides[get_current_user] = override_user(actor)
    app.dependency_overrides[get_calendar_service] = lambda: service
    client = TestClient(app)
    correlation_id = uuid4()
    response = client.post(
        "/calendar",
        headers={"X-Correlation-ID": str(correlation_id)},
        json={
            "title": "Spring Break",
            "entry_type": "break",
            "start_date": str(date.today() + timedelta(days=7)),
            "university_id": str(uuid4()),
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["university_id"] == str(university_id)
    assert service.create_calls == [(university_id, actor.user_id)]
    assert [event.event_type for event in store.events] == ["calendar.entry_created"]
    assert store.events[0].actor_id == actor.user_id
    assert store.events[0].correlation_id == correlation_id


def test_student_cannot_create_calendar_entry() -> None:
    """Student users should not be allowed to create calendar entries."""

    app.dependency_overrides[get_current_user] = override_user(user(UserRole.STUDENT, uuid4()))
    app.dependency_overrides[get_calendar_service] = lambda: FakeRouteCalendarService(
        [],
        InMemoryEventStore(),
    )
    client = TestClient(app)
    response = client.post(
        "/calendar",
        json={
            "title": "Spring Break",
            "entry_type": "break",
            "start_date": str(date.today() + timedelta(days=7)),
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 403


def test_calendar_tenant_comes_from_authenticated_user_not_client_header() -> None:
    """Calendar routes should ignore tenant spoofing headers."""

    jwt_university_id = uuid4()
    spoofed_university_id = uuid4()
    service = FakeRouteCalendarService([], InMemoryEventStore())
    app.dependency_overrides[get_current_user] = override_user(
        user(UserRole.STUDENT, jwt_university_id)
    )
    app.dependency_overrides[get_calendar_service] = lambda: service
    client = TestClient(app)
    response = client.get(
        "/calendar",
        headers={"X-University-ID": str(spoofed_university_id)},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.list_university_ids == [jwt_university_id]
