"""E2E contract tests for Forms, Deadlines, and workflow relationships."""

from datetime import date, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.domains.auth.models.roles import UserRole
from app.domains.deadlines.api.deadlines import get_deadline_service
from app.domains.deadlines.schemas import DeadlineCreate
from app.domains.deadlines.services import DeadlineService
from app.domains.forms.api.forms import (
    get_deadline_relationship_service,
    get_forms_retrieval_service,
    get_forms_service,
)
from app.domains.orchestration.api.orchestrator import get_retrieval_orchestrator
from app.domains.relationships.api.relationships import (
    get_relationship_traversal_service,
)
from app.domains.relationships.services import RelationshipsService
from app.domains.relationships.traversal import RelationshipTraversalService
from app.main import app
from app.shared.events import EventBus, EventContext
from app.tests.deadline_helpers import FakeDeadlineRepository, InMemoryEventStore
from app.tests.forms_deadlines_helpers import (
    FakeFormsRepositoryForLinks,
    InMemoryRelationshipRepository,
)
from app.tests.workflow_e2e_helpers import (
    WorkflowFormsRetrievalService,
    WorkflowFormsService,
    auth_headers,
    build_orchestrator,
    form_record,
)

JWT_SECRET = "workflow-secret-with-at-least-32-bytes"


@pytest.fixture(autouse=True)
def configure_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use production JWT parsing with deterministic test settings."""

    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_JWT_ISSUER", None)


@pytest.fixture()
def client() -> TestClient:
    """Return a TestClient and clear dependency overrides."""

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_forms_deadlines_workflow_e2e_contract(client: TestClient) -> None:
    """Validate governed form-deadline workflow, traversal, and orchestration."""

    university_id = uuid4()
    other_university_id = uuid4()
    actor_id = uuid4()
    store = InMemoryEventStore()
    forms: dict[UUID, SimpleNamespace] = {}
    deadline_repository = FakeDeadlineRepository()
    relationship_repository = InMemoryRelationshipRepository()
    relationships_service = RelationshipsService(
        relationship_repository,
        event_bus=EventBus(store),
    )
    deadline_service = DeadlineService(
        deadline_repository,
        forms_repository=FakeFormsRepositoryForLinks(forms),
        relationships_service=relationships_service,
        event_bus=EventBus(store),
    )
    forms_service = WorkflowFormsService(forms)
    forms_retrieval_service = WorkflowFormsRetrievalService(forms)

    app.dependency_overrides[get_forms_service] = lambda: forms_service
    app.dependency_overrides[get_forms_retrieval_service] = (
        lambda: forms_retrieval_service
    )
    app.dependency_overrides[get_deadline_service] = lambda: deadline_service
    app.dependency_overrides[get_deadline_relationship_service] = (
        lambda: deadline_service
    )
    app.dependency_overrides[get_relationship_traversal_service] = lambda: (
        RelationshipTraversalService(
            relationships_service=RelationshipsService(relationship_repository),
            forms_repository=FakeFormsRepositoryForLinks(forms),
            deadlines_repository=deadline_repository,
        )
    )
    app.dependency_overrides[get_retrieval_orchestrator] = lambda: build_orchestrator(
        forms_retrieval_service=forms_retrieval_service,
        relationships_service=RelationshipsService(relationship_repository),
        deadline_service=deadline_service,
        forms=forms,
        deadline_repository=deadline_repository,
    )

    admin_headers = auth_headers(
        role=UserRole.ADMIN,
        university_id=university_id,
        jwt_secret=JWT_SECRET,
        user_id=actor_id,
    )
    student_headers = auth_headers(
        role=UserRole.STUDENT,
        university_id=university_id,
        jwt_secret=JWT_SECRET,
    )
    attacker_headers = {
        **admin_headers,
        "X-University-ID": str(other_university_id),
    }

    create_form = client.post(
        "/forms",
        headers=admin_headers,
        json={
            "university_id": str(other_university_id),
            "title": "Withdrawal Form",
            "description": "Withdraw from a course",
            "category": "registrar",
            "storage_path": "tenant/private/withdrawal.pdf",
            "status": "published",
            "verification_status": "verified",
        },
    )
    assert create_form.status_code == 201
    form_id = UUID(create_form.json()["id"])
    assert forms[form_id].university_id == university_id

    create_deadline = client.post(
        "/deadlines",
        headers=attacker_headers,
        json={
            "university_id": str(other_university_id),
            "title": "Withdrawal Deadline",
            "description": "Last day to submit withdrawal",
            "deadline_type": "withdrawal",
            "due_date": str(date.today() + timedelta(days=10)),
            "related_form_id": str(form_id),
            "status": "published",
            "verification_status": "verified",
        },
    )
    assert create_deadline.status_code == 201
    deadline_body = create_deadline.json()
    deadline_id = UUID(deadline_body["id"])
    assert deadline_body["university_id"] == str(university_id)
    assert deadline_body["related_form"]["form_id"] == str(form_id)
    assert "storage_path" not in str(deadline_body)
    assert len(relationship_repository.relationships) == 1
    assert relationship_repository.relationships[0].relationship_type == "deadline_for"

    await deadline_service.create_deadline(
        deadline_data=DeadlineCreate(
            title="Pending Withdrawal Deadline",
            deadline_type="withdrawal",
            due_date=date.today() + timedelta(days=20),
            related_form_id=form_id,
            status="pending_review",
            verification_status="pending_review",
        ),
        university_id=university_id,
        actor_id=actor_id,
        event_context=EventContext(actor_id=actor_id),
    )

    cross_tenant_form_id = uuid4()
    forms[cross_tenant_form_id] = form_record(
        form_id=cross_tenant_form_id,
        university_id=other_university_id,
        title="Other Withdrawal Form",
    )
    cross_tenant_deadline = client.post(
        "/deadlines",
        headers=admin_headers,
        json={
            "title": "Blocked Deadline",
            "due_date": str(date.today() + timedelta(days=30)),
            "related_form_id": str(cross_tenant_form_id),
        },
    )
    assert cross_tenant_deadline.status_code == 400

    form_search = client.get(
        "/forms/search",
        headers=student_headers,
        params={"q": "withdrawal", "include_deadlines": "true"},
    )
    assert form_search.status_code == 200
    form_body = form_search.json()
    related_deadlines = form_body["forms"][0]["related_deadlines"]
    assert [item["deadline_id"] for item in related_deadlines] == [str(deadline_id)]
    assert "Pending Withdrawal Deadline" not in str(form_body)
    assert "storage_path" not in str(form_body)

    deadline_search = client.get(
        "/deadlines/search",
        headers=student_headers,
        params={"q": "withdrawal"},
    )
    assert deadline_search.status_code == 200
    deadline_search_body = deadline_search.json()
    assert [item["id"] for item in deadline_search_body["deadlines"]] == [
        str(deadline_id)
    ]
    assert deadline_search_body["deadlines"][0]["related_form"]["title"] == (
        "Withdrawal Form"
    )
    assert "Pending Withdrawal Deadline" not in str(deadline_search_body)
    assert "storage_path" not in str(deadline_search_body)

    mixed_query = client.post(
        "/orchestrator/query",
        headers=student_headers,
        json={"query": "withdrawal form deadline"},
    )
    assert mixed_query.status_code == 200
    mixed_body = mixed_query.json()
    assert "forms_search" in mixed_body["results"]
    assert "deadline_query" in mixed_body["results"]
    assert mixed_body["results"]["deadline_query"][0]["id"] == str(deadline_id)

    form_to_deadline = client.post(
        "/relationships/traverse",
        headers=student_headers,
        json={
            "entity_type": "form",
            "entity_id": str(form_id),
            "allowed_relationship_types": ["deadline_for"],
        },
    )
    deadline_to_form = client.post(
        "/relationships/traverse",
        headers=student_headers,
        json={
            "entity_type": "deadline",
            "entity_id": str(deadline_id),
            "allowed_relationship_types": ["deadline_for"],
        },
    )
    assert form_to_deadline.status_code == 200
    assert deadline_to_form.status_code == 200
    assert form_to_deadline.json()["related_entities"][0]["entity_type"] == "deadline"
    assert deadline_to_form.json()["related_entities"][0]["entity_type"] == "form"
