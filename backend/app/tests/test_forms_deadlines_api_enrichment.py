"""API enrichment tests for Forms and Deadlines relationships."""

from datetime import UTC, date, datetime
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from app.domains.auth.models.roles import UserRole
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.deadlines.api.deadlines import get_deadline_service
from app.domains.deadlines.schemas import RelatedFormSummary
from app.domains.forms.api.forms import (
    get_deadline_relationship_service,
    get_forms_service,
    get_relationships_service,
)
from app.domains.forms.schemas import RelatedDeadlineSummary
from app.domains.forms.services import FormsService
from app.main import app
from app.shared.auth.dependencies import get_current_user
from app.tests.deadline_helpers import (
    FakeRouteDeadlineService,
    InMemoryEventStore,
    override_user,
    user,
)


def test_deadline_response_includes_safe_related_form_summary() -> None:
    """Deadline response should include safe form summary and no storage path."""

    university_id = uuid4()
    related_form_id = uuid4()
    route_service = FakeRouteDeadlineService([], InMemoryEventStore())
    route_service.related_forms[related_form_id] = RelatedFormSummary(
        form_id=related_form_id,
        title="Withdrawal Form",
        category="registrar",
        status="verified",
        verification_status="verified",
    )
    app.dependency_overrides[get_current_user] = override_user(
        user(UserRole.ADMIN, university_id)
    )
    app.dependency_overrides[get_deadline_service] = lambda: route_service
    client = TestClient(app)
    response = client.post(
        "/deadlines",
        json={
            "title": "Withdrawal Deadline",
            "due_date": str(date.today()),
            "related_form_id": str(related_form_id),
        },
    )
    app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 201
    assert body["related_form"]["title"] == "Withdrawal Form"
    assert "storage_path" not in str(body)


def test_form_retrieval_includes_visible_related_deadline_summary() -> None:
    """Form retrieval can include safe visible related deadline summaries."""

    university_id = uuid4()
    form_id = uuid4()
    deadline_id = uuid4()
    fake_form = _form_response_row(form_id, university_id)

    class FakeFormsService(FormsService):
        async def retrieve_form(self, university_id, form_id):
            return fake_form

    class FakeDeadlineSummaryService:
        async def related_deadline_summaries_for_form(self, **kwargs):
            return [
                RelatedDeadlineSummary(
                    deadline_id=deadline_id,
                    title="Withdrawal Deadline",
                    deadline_type="withdrawal",
                    due_date=date.today(),
                    status="verified",
                    verification_status="verified",
                )
            ]

    async def current_user():
        return AuthenticatedUser(
            user_id=uuid4(),
            university_id=university_id,
            role=UserRole.STUDENT,
        )

    app.dependency_overrides[get_current_user] = current_user
    app.dependency_overrides[get_forms_service] = lambda: FakeFormsService(None)
    app.dependency_overrides[get_relationships_service] = lambda: object()
    app.dependency_overrides[get_deadline_relationship_service] = (
        lambda: FakeDeadlineSummaryService()
    )
    client = TestClient(app)
    response = client.get(f"/forms/{form_id}?include_deadlines=true")
    app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["related_deadlines"][0]["deadline_id"] == str(deadline_id)
    assert "storage_path" not in str(body)


def _form_response_row(form_id, university_id):
    """Build a form-like row for route serialization."""

    return SimpleNamespace(
        id=form_id,
        university_id=university_id,
        title="Withdrawal Form",
        description="Withdraw from a course",
        category="registrar",
        source_url=None,
        verification_status="verified",
        verification_score=None,
        last_verified_at=None,
        verified_by=None,
        review_notes=None,
        expires_at=None,
        next_review_at=None,
        review_count=0,
        staleness_score=None,
        status="verified",
        metadata_={},
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
