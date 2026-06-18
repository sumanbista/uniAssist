"""API tests for the governed Deadline domain."""

from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

from app.domains.auth.models.roles import UserRole
from app.domains.deadlines.api.deadlines import get_deadline_service
from app.main import app
from app.shared.auth.dependencies import get_current_user
from app.tests.deadline_helpers import (
    FakeRouteDeadlineService,
    InMemoryEventStore,
    override_user,
    user,
)


def test_admin_can_create_deadline_and_event_is_emitted() -> None:
    """Admin users should create tenant-stamped deadlines and emit audit events."""

    university_id = uuid4()
    actor = user(UserRole.ADMIN, university_id)
    store = InMemoryEventStore()
    service = FakeRouteDeadlineService([], store)

    app.dependency_overrides[get_current_user] = override_user(actor)
    app.dependency_overrides[get_deadline_service] = lambda: service
    client = TestClient(app)
    correlation_id = uuid4()
    response = client.post(
        "/deadlines",
        headers={"X-Correlation-ID": str(correlation_id)},
        json={
            "title": "Withdrawal Deadline",
            "deadline_type": "withdrawal",
            "due_date": str(date.today() + timedelta(days=7)),
            "university_id": str(uuid4()),
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["university_id"] == str(university_id)
    assert service.create_calls == [(university_id, actor.user_id)]
    assert [event.event_type for event in store.events] == ["deadline.created"]
    assert store.events[0].actor_id == actor.user_id
    assert store.events[0].correlation_id == correlation_id


def test_student_cannot_create_deadline() -> None:
    """Student users should not be allowed to create deadlines."""

    app.dependency_overrides[get_current_user] = override_user(user(UserRole.STUDENT, uuid4()))
    app.dependency_overrides[get_deadline_service] = lambda: FakeRouteDeadlineService(
        [],
        InMemoryEventStore(),
    )
    client = TestClient(app)
    response = client.post(
        "/deadlines",
        json={
            "title": "Withdrawal Deadline",
            "deadline_type": "withdrawal",
            "due_date": str(date.today() + timedelta(days=7)),
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 403


def test_deadline_tenant_comes_from_authenticated_user_not_client_header() -> None:
    """Deadline routes should ignore tenant spoofing headers."""

    jwt_university_id = uuid4()
    spoofed_university_id = uuid4()
    service = FakeRouteDeadlineService([], InMemoryEventStore())
    app.dependency_overrides[get_current_user] = override_user(
        user(UserRole.STUDENT, jwt_university_id)
    )
    app.dependency_overrides[get_deadline_service] = lambda: service
    client = TestClient(app)
    response = client.get(
        "/deadlines",
        headers={"X-University-ID": str(spoofed_university_id)},
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.list_university_ids == [jwt_university_id]


def test_related_form_id_is_returned_without_storage_path() -> None:
    """Deadline responses may expose form IDs but not internal form storage paths."""

    university_id = uuid4()
    related_form_id = uuid4()
    actor = user(UserRole.ADMIN, university_id)
    service = FakeRouteDeadlineService([], InMemoryEventStore())
    app.dependency_overrides[get_current_user] = override_user(actor)
    app.dependency_overrides[get_deadline_service] = lambda: service
    client = TestClient(app)
    response = client.post(
        "/deadlines",
        json={
            "title": "Graduation Application Due",
            "deadline_type": "graduation_application",
            "due_date": str(date.today() + timedelta(days=30)),
            "related_form_id": str(related_form_id),
        },
    )
    app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 201
    assert body["related_form_id"] == str(related_form_id)
    assert "storage_path" not in body
