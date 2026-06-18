"""Focused tests for the governed Contacts domain foundation."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.domains.auth.models.roles import UserRole
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.contacts.api.contacts import get_contacts_service
from app.domains.contacts.models import Contact
from app.domains.contacts.services import ContactsService
from app.domains.orchestration.schemas import ExecutionStep, OrchestrationToolName
from app.domains.orchestration.services import ContactLookupTool
from app.main import app
from app.shared.auth.dependencies import get_current_user
from app.shared.events import EventBus, EventContext, PlatformEvent


JWT_SECRET = "contacts-test-secret-with-at-least-32-bytes"


@pytest.fixture(autouse=True)
def cleanup_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use deterministic JWT settings and clear route overrides."""

    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_JWT_ISSUER", None)
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def auth_headers(
    *,
    role: UserRole,
    university_id: UUID,
    user_id: UUID | None = None,
) -> dict[str, str]:
    """Build a bearer token for route-level Contacts tests."""

    token = jwt.encode(
        {
            "sub": str(user_id or uuid4()),
            "aud": "authenticated",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "app_metadata": {
                "university_id": str(university_id),
                "role": role.value,
            },
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def user(role: UserRole, university_id: UUID) -> AuthenticatedUser:
    """Build an authenticated user for dependency overrides."""

    return AuthenticatedUser(user_id=uuid4(), university_id=university_id, role=role)


def override_user(current_user: AuthenticatedUser):
    """Return a FastAPI dependency override for current user."""

    async def dependency() -> AuthenticatedUser:
        return current_user

    return dependency


def contact(**overrides) -> Contact:
    """Build a contact model for tests."""

    values = {
        "id": uuid4(),
        "university_id": uuid4(),
        "name": "Registrar Office",
        "title": "Registrar",
        "department": "Registrar",
        "email": "registrar@example.edu",
        "phone": "555-0100",
        "office_location": "Admin 101",
        "office_hours": "Monday-Friday 9-5",
        "contact_type": "office",
        "source_url": "https://example.edu/registrar",
        "verification_status": "verified",
        "status": "published",
        "last_verified_at": datetime.now(UTC),
        "metadata_": {},
        "is_active": True,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return Contact(**values)


class InMemoryEventStore:
    """In-memory event store for event assertions."""

    def __init__(self) -> None:
        self.events: list[PlatformEvent] = []

    async def append(self, event: PlatformEvent) -> PlatformEvent:
        """Append an event."""

        self.events.append(event)
        return event


class FakeContactsRepository:
    """Repository fake with service-compatible Contacts behavior."""

    def __init__(self, contacts: list[Contact] | None = None) -> None:
        self.contacts = contacts or []

    async def create_contact(self, new_contact: Contact) -> Contact:
        """Persist a contact in memory."""

        now = datetime.now(UTC)
        new_contact.id = new_contact.id or uuid4()
        new_contact.created_at = now
        new_contact.updated_at = now
        self.contacts.append(new_contact)
        return new_contact

    async def get_contact_by_id(
        self,
        university_id,
        contact_id,
        visible_statuses,
        visible_verification_statuses,
    ):
        """Return one visible contact."""

        for row in self._visible(university_id, visible_statuses, visible_verification_statuses):
            if row.id == contact_id:
                return row
        return None

    async def list_contacts(
        self,
        university_id,
        visible_statuses,
        visible_verification_statuses,
        limit,
        offset,
        department=None,
        contact_type=None,
    ):
        """Return visible contacts matching optional filters."""

        rows = self._visible(university_id, visible_statuses, visible_verification_statuses)
        if department is not None:
            rows = [row for row in rows if department.casefold() == row.department.casefold()]
        if contact_type is not None:
            rows = [row for row in rows if row.contact_type == contact_type]
        return rows[offset : offset + limit], len(rows)

    async def search_contacts(
        self,
        university_id,
        query_text,
        visible_statuses,
        visible_verification_statuses,
        limit,
        offset=0,
    ):
        """Return visible contacts matching query text."""

        query = query_text.casefold()
        rows = [
            row
            for row in self._visible(university_id, visible_statuses, visible_verification_statuses)
            if query in row.name.casefold()
            or query in row.title.casefold()
            or query in row.department.casefold()
            or query in row.email.casefold()
        ]
        return rows[offset : offset + limit], len(rows)

    async def search_by_department(
        self,
        university_id,
        department,
        visible_statuses,
        visible_verification_statuses,
        limit,
        offset=0,
    ):
        """Return visible contacts matching department."""

        query = department.casefold()
        rows = [
            row
            for row in self._visible(university_id, visible_statuses, visible_verification_statuses)
            if query in row.department.casefold()
        ]
        return rows[offset : offset + limit], len(rows)

    async def search_by_contact_type(
        self,
        university_id,
        contact_type,
        visible_statuses,
        visible_verification_statuses,
        limit,
        offset=0,
    ):
        """Return visible contacts matching contact type."""

        rows = [
            row
            for row in self._visible(university_id, visible_statuses, visible_verification_statuses)
            if row.contact_type == contact_type
        ]
        return rows[offset : offset + limit], len(rows)

    def _visible(
        self,
        university_id,
        visible_statuses,
        visible_verification_statuses,
    ) -> list[Contact]:
        """Apply tenant and governance filters."""

        return [
            row
            for row in self.contacts
            if row.university_id == university_id
            and row.is_active
            and row.status in visible_statuses
            and row.verification_status in visible_verification_statuses
        ]


class RecordingContactsService:
    """Route dependency fake preserving Contacts API contracts."""

    def __init__(self, contacts: list[Contact]) -> None:
        self.contacts = contacts
        self.create_calls: list[tuple[UUID, UUID]] = []
        self.list_university_ids: list[UUID] = []

    async def create_contact(self, contact_data, university_id, actor_id, event_context):
        """Create a contact and record tenant/actor context."""

        self.create_calls.append((university_id, actor_id))
        row = contact(
            university_id=university_id,
            name=contact_data.name,
            title=contact_data.title,
            department=contact_data.department,
            email=contact_data.email,
            contact_type=contact_data.contact_type.value,
            status=contact_data.status,
            verification_status=contact_data.verification_status,
        )
        self.contacts.append(row)
        return row

    async def retrieve_contact(self, **kwargs):
        """Retrieve one contact through the real service filtering rules."""

        service = ContactsService(FakeContactsRepository(self.contacts))
        return await service.retrieve_contact(**kwargs)

    async def list_contacts(self, **kwargs):
        """List contacts through the real service filtering rules."""

        self.list_university_ids.append(kwargs["university_id"])
        service = ContactsService(FakeContactsRepository(self.contacts))
        return await service.list_contacts(**kwargs)

    async def search_contacts(self, **kwargs):
        """Search contacts through the real service filtering rules."""

        service = ContactsService(FakeContactsRepository(self.contacts))
        return await service.search_contacts(**kwargs)

    async def search_by_department(self, **kwargs):
        """Search department through the real service filtering rules."""

        service = ContactsService(FakeContactsRepository(self.contacts))
        return await service.search_by_department(**kwargs)

    async def search_by_contact_type(self, **kwargs):
        """Search contact type through the real service filtering rules."""

        service = ContactsService(FakeContactsRepository(self.contacts))
        return await service.search_by_contact_type(**kwargs)


def test_admin_can_create_contact() -> None:
    """Admin users should create tenant-stamped contacts."""

    university_id = uuid4()
    actor = user(UserRole.ADMIN, university_id)
    service = RecordingContactsService([])
    app.dependency_overrides[get_current_user] = override_user(actor)
    app.dependency_overrides[get_contacts_service] = lambda: service

    response = TestClient(app).post(
        "/contacts",
        json={
            "university_id": str(uuid4()),
            "name": "Registrar Office",
            "title": "Registrar",
            "department": "Registrar",
            "email": "registrar@example.edu",
            "contact_type": "office",
        },
    )

    assert response.status_code == 201
    assert response.json()["university_id"] == str(university_id)
    assert service.create_calls == [(university_id, actor.user_id)]


def test_student_cannot_create_contact() -> None:
    """Student users should not be allowed to create contacts."""

    app.dependency_overrides[get_current_user] = override_user(user(UserRole.STUDENT, uuid4()))
    app.dependency_overrides[get_contacts_service] = lambda: RecordingContactsService([])

    response = TestClient(app).post(
        "/contacts",
        json={
            "name": "Registrar Office",
            "title": "Registrar",
            "department": "Registrar",
            "email": "registrar@example.edu",
            "contact_type": "office",
        },
    )

    assert response.status_code == 403


def test_student_sees_verified_and_published_only() -> None:
    """Student read endpoints should expose only public governed contacts."""

    university_id = uuid4()
    rows = [
        contact(university_id=university_id, name="Verified Registrar", status="verified", verification_status="verified"),
        contact(university_id=university_id, name="Published Aid", status="published", verification_status="published"),
        contact(university_id=university_id, name="Pending Dean", status="pending_review", verification_status="pending_review"),
        contact(university_id=university_id, name="Rejected Office", status="rejected", verification_status="rejected"),
    ]
    app.dependency_overrides[get_current_user] = override_user(user(UserRole.STUDENT, university_id))
    app.dependency_overrides[get_contacts_service] = lambda: RecordingContactsService(rows)

    response = TestClient(app).get("/contacts")

    assert response.status_code == 200
    assert {row["name"] for row in response.json()["contacts"]} == {
        "Verified Registrar",
        "Published Aid",
    }


def test_faculty_sees_verified_and_published_only() -> None:
    """Faculty read endpoints should use the same public visibility as students."""

    university_id = uuid4()
    rows = [
        contact(university_id=university_id, name="Verified Registrar", status="verified", verification_status="verified"),
        contact(university_id=university_id, name="Published Aid", status="published", verification_status="published"),
        contact(university_id=university_id, name="Stale Office", status="stale", verification_status="stale"),
    ]
    app.dependency_overrides[get_current_user] = override_user(user(UserRole.FACULTY, university_id))
    app.dependency_overrides[get_contacts_service] = lambda: RecordingContactsService(rows)

    response = TestClient(app).get("/contacts")

    assert response.status_code == 200
    assert {row["name"] for row in response.json()["contacts"]} == {
        "Verified Registrar",
        "Published Aid",
    }


def test_admin_class_users_see_pending_review_and_stale() -> None:
    """Admin-class users should see pending review and stale contacts."""

    university_id = uuid4()
    rows = [
        contact(university_id=university_id, name="Pending Dean", status="pending_review", verification_status="pending_review"),
        contact(university_id=university_id, name="Stale Aid", status="stale", verification_status="stale"),
    ]
    app.dependency_overrides[get_current_user] = override_user(user(UserRole.UNIVERSITY_ADMIN, university_id))
    app.dependency_overrides[get_contacts_service] = lambda: RecordingContactsService(rows)

    response = TestClient(app).get("/contacts")

    assert response.status_code == 200
    assert {row["name"] for row in response.json()["contacts"]} == {
        "Pending Dean",
        "Stale Aid",
    }


def test_rejected_archived_and_deprecated_contacts_are_hidden() -> None:
    """Terminal governance states should not be returned to any caller."""

    university_id = uuid4()
    rows = [
        contact(university_id=university_id, name="Rejected Office", status="rejected", verification_status="rejected"),
        contact(university_id=university_id, name="Archived Office", status="archived", verification_status="archived"),
        contact(university_id=university_id, name="Deprecated Office", status="deprecated", verification_status="deprecated"),
    ]
    app.dependency_overrides[get_current_user] = override_user(user(UserRole.SUPER_ADMIN, university_id))
    app.dependency_overrides[get_contacts_service] = lambda: RecordingContactsService(rows)

    response = TestClient(app).get("/contacts")

    assert response.status_code == 200
    assert response.json()["contacts"] == []


def test_search_by_name_department_and_contact_type() -> None:
    """Search endpoint should support name, department, and contact type queries."""

    university_id = uuid4()
    rows = [
        contact(university_id=university_id, name="Ada Lovelace", department="Computer Science", contact_type="faculty"),
        contact(university_id=university_id, name="Financial Aid", department="Student Accounts", contact_type="office"),
    ]
    app.dependency_overrides[get_current_user] = override_user(user(UserRole.STUDENT, university_id))
    app.dependency_overrides[get_contacts_service] = lambda: RecordingContactsService(rows)
    client = TestClient(app)

    name_response = client.get("/contacts/search", params={"q": "Ada"})
    department_response = client.get("/contacts/search", params={"department": "computer"})
    type_response = client.get("/contacts/search", params={"contact_type": "office"})

    assert [row["name"] for row in name_response.json()["contacts"]] == ["Ada Lovelace"]
    assert [row["name"] for row in department_response.json()["contacts"]] == ["Ada Lovelace"]
    assert [row["name"] for row in type_response.json()["contacts"]] == ["Financial Aid"]


def test_get_contact_returns_visible_contact_and_hides_nonvisible_contact() -> None:
    """GET /contacts/{id} should return only visible tenant-scoped contacts."""

    university_id = uuid4()
    visible_contact = contact(university_id=university_id, name="Visible Registrar")
    hidden_contact = contact(
        university_id=university_id,
        name="Rejected Registrar",
        status="rejected",
        verification_status="rejected",
    )
    app.dependency_overrides[get_current_user] = override_user(user(UserRole.STUDENT, university_id))
    app.dependency_overrides[get_contacts_service] = lambda: RecordingContactsService(
        [visible_contact, hidden_contact]
    )
    client = TestClient(app)

    visible_response = client.get(f"/contacts/{visible_contact.id}")
    hidden_response = client.get(f"/contacts/{hidden_contact.id}")

    assert visible_response.status_code == 200
    assert visible_response.json()["name"] == "Visible Registrar"
    assert hidden_response.status_code == 404


def test_contact_responses_do_not_expose_internal_fields() -> None:
    """Contacts responses should not leak ORM-only internal fields."""

    university_id = uuid4()
    app.dependency_overrides[get_current_user] = override_user(user(UserRole.STUDENT, university_id))
    app.dependency_overrides[get_contacts_service] = lambda: RecordingContactsService(
        [contact(university_id=university_id)]
    )

    response = TestClient(app).get("/contacts")

    assert response.status_code == 200
    payload = response.json()["contacts"][0]
    assert "metadata_" not in payload
    assert "is_active" not in payload
    assert "storage_path" not in payload


@pytest.mark.anyio
async def test_contact_created_event_is_emitted() -> None:
    """ContactsService should emit contact.created with required context."""

    university_id = uuid4()
    actor_id = uuid4()
    correlation_id = uuid4()
    event_store = InMemoryEventStore()
    service = ContactsService(
        repository=FakeContactsRepository(),
        event_bus=EventBus(event_store),
    )

    created = await service.create_contact(
        contact_data=SimpleNamespace(
            name="Registrar Office",
            title="Registrar",
            department="Registrar",
            email="registrar@example.edu",
            phone=None,
            office_location=None,
            office_hours=None,
            contact_type="office",
            source_url=None,
            verification_status="pending_review",
            status="pending_review",
            last_verified_at=None,
            metadata={},
        ),
        university_id=university_id,
        actor_id=actor_id,
        event_context=EventContext(actor_id=actor_id, correlation_id=correlation_id),
    )

    assert [event.event_type for event in event_store.events] == ["contact.created"]
    event = event_store.events[0]
    assert event.actor_id == actor_id
    assert event.university_id == university_id
    assert event.aggregate_id == created.id
    assert event.correlation_id == correlation_id
    assert event.payload["contact_id"] == str(created.id)


@pytest.mark.anyio
async def test_contact_lookup_tool_is_repository_backed_and_traceable() -> None:
    """The contact_lookup orchestration tool should return governed contact data."""

    university_id = uuid4()
    service = ContactsService(
        FakeContactsRepository(
            [
                contact(university_id=university_id, name="Registrar Office"),
                contact(university_id=uuid4(), name="Registrar Office"),
            ]
        )
    )
    tool = ContactLookupTool(service)

    result = await tool.run(
        step=ExecutionStep(
            step_id=1,
            tool_name=OrchestrationToolName.CONTACT_LOOKUP,
            params={"query": "registrar", "limit": 5},
            timeout_seconds=5,
        ),
        university_id=university_id,
        prior_results=[],
        role=UserRole.STUDENT,
    )

    assert result.tool_name == OrchestrationToolName.CONTACT_LOOKUP
    assert [row["name"] for row in result.data] == ["Registrar Office"]
    assert result.metadata["retrieval_type"] == "contact_lookup"
    assert result.metadata["trace"]["university_id"] == str(university_id)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("query", "expected_name"),
    [
        ("Who is the registrar?", "Registrar Office"),
        ("Contact financial aid.", "Financial Aid"),
        ("CS department phone number.", "CS Department"),
        ("Dean of students office.", "Dean of Students Office"),
    ],
)
async def test_contact_lookup_tool_handles_natural_language_examples(
    query: str,
    expected_name: str,
) -> None:
    """The contact_lookup tool should resolve documented natural-language examples."""

    university_id = uuid4()
    service = ContactsService(
        FakeContactsRepository(
            [
                contact(university_id=university_id, name="Registrar Office"),
                contact(university_id=university_id, name="Financial Aid", department="Financial Aid"),
                contact(university_id=university_id, name="CS Department", department="Computer Science"),
                contact(university_id=university_id, name="Dean of Students Office", title="Dean of Students"),
            ]
        )
    )
    tool = ContactLookupTool(service)

    result = await tool.run(
        step=ExecutionStep(
            step_id=1,
            tool_name=OrchestrationToolName.CONTACT_LOOKUP,
            params={"query": query, "limit": 5},
            timeout_seconds=5,
        ),
        university_id=university_id,
        prior_results=[],
        role=UserRole.STUDENT,
    )

    assert expected_name in {row["name"] for row in result.data}


def test_contacts_tenant_comes_from_jwt_and_spoofed_headers_are_ignored() -> None:
    """Contacts routes should derive tenant from JWT, not client-supplied headers."""

    jwt_university_id = uuid4()
    spoofed_university_id = uuid4()
    service = RecordingContactsService([])
    app.dependency_overrides[get_contacts_service] = lambda: service

    response = TestClient(app).get(
        "/contacts",
        headers={
            **auth_headers(role=UserRole.STUDENT, university_id=jwt_university_id),
            "X-University-ID": str(spoofed_university_id),
        },
    )

    assert response.status_code == 200
    assert service.list_university_ids == [jwt_university_id]
    assert service.list_university_ids != [spoofed_university_id]


def test_contacts_read_endpoints_require_auth_and_return_safe_errors() -> None:
    """Contacts read endpoints should require authentication and return stable errors."""

    client = TestClient(app)

    list_response = client.get("/contacts")
    search_response = client.get("/contacts/search", params={"q": "registrar"})
    detail_response = client.get(f"/contacts/{uuid4()}")

    assert list_response.status_code == 401
    assert search_response.status_code == 401
    assert detail_response.status_code == 401
    assert list_response.json()["detail"]["code"] == "UNAUTHORIZED"
