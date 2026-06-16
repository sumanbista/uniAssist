"""Tests for Forms governance review queue integration."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domains.auth.models.roles import UserRole
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.forms.retrieval.service import FormsRetrievalService
from app.domains.governance.review_queue.api import get_review_queue_service
from app.domains.governance.review_queue.schemas import (
    ReviewDecision,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
)
from app.domains.governance.review_queue.service import (
    InvalidReviewDecisionError,
    ReviewQueueService,
)
from app.main import app
from app.shared.auth.dependencies import get_current_user
from app.shared.events import EventBus, PlatformEvent


class ScalarResult:
    """Minimal SQLAlchemy result fake."""

    def __init__(self, values) -> None:
        self.values = values

    def all(self):
        """Return all values."""

        return self.values


class ExecuteResult:
    """Minimal async session execute result fake."""

    def __init__(self, values) -> None:
        self.values = values

    def scalars(self) -> ScalarResult:
        """Return scalar values."""

        return ScalarResult(self.values)

    def scalar_one_or_none(self):
        """Return one value or None."""

        return self.values[0] if self.values else None


class FakeReviewSession:
    """In-memory session fake for review queue tests."""

    def __init__(self, forms) -> None:
        self.forms = forms
        self.commits = 0
        self.refreshes = 0
        self.added = []

    async def execute(self, _query) -> ExecuteResult:
        """Return forms supplied for the test."""

        return ExecuteResult(self.forms)

    def add(self, entity) -> None:
        """Record a pending entity."""

        self.added.append(entity)

    async def commit(self) -> None:
        """Record commit calls."""

        self.commits += 1

    async def refresh(self, _entity) -> None:
        """Record refresh calls."""

        self.refreshes += 1


class InMemoryEventStore:
    """In-memory event store for event assertions."""

    def __init__(self) -> None:
        self.events: list[PlatformEvent] = []

    async def append(self, event: PlatformEvent) -> PlatformEvent:
        """Append an event."""

        self.events.append(event)
        return event


def form(**overrides):
    """Build a form-like object for review tests."""

    values = {
        "id": uuid4(),
        "university_id": uuid4(),
        "title": "Tuition Appeal",
        "description": "Appeal form",
        "category": "financial_aid",
        "source_url": "https://example.edu/forms/tuition.pdf",
        "storage_path": "tenant/pdf_forms/form.pdf",
        "status": "pending_review",
        "verification_status": "pending_review",
        "verification_score": 0.5,
        "last_verified_at": None,
        "verified_by": None,
        "review_notes": None,
        "review_count": 0,
        "staleness_score": 0.0,
        "next_review_at": None,
        "expires_at": None,
        "created_at": datetime.now(UTC),
        "is_active": True,
        "metadata_": {
            "upload_method": "admin_pdf",
            "original_filename": "tuition.pdf",
            "file_size": 123,
            "page_count": 2,
        },
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def build_review_service(forms):
    """Build a review queue service with fakes."""

    store = InMemoryEventStore()
    session = FakeReviewSession(forms)
    return ReviewQueueService(session, event_bus=EventBus(store)), session, store


@pytest.mark.anyio
async def test_pending_uploaded_pdf_appears_in_review_queue() -> None:
    """Pending uploaded PDF forms should appear in review queue reads."""

    pending_form = form()
    service, _session, _store = build_review_service([pending_form])

    items = await service.list_pending_reviews(
        university_id=pending_form.university_id,
        entity_type="form",
    )

    assert len(items) == 1
    assert items[0].entity_id == pending_form.id
    assert items[0].status == "pending_review"
    assert items[0].source_metadata["upload_method"] == "admin_pdf"
    assert items[0].source_metadata["original_filename"] == "tuition.pdf"


@pytest.mark.anyio
async def test_admin_can_approve_pending_form_and_event_is_emitted() -> None:
    """Approving a pending form should verify it and emit review.approved."""

    actor_id = uuid4()
    correlation_id = uuid4()
    pending_form = form()
    service, session, store = build_review_service([pending_form])

    response = await service.decide_review(
        university_id=pending_form.university_id,
        request=ReviewDecisionRequest(
            entity_type="form",
            entity_id=pending_form.id,
            decision=ReviewDecision.APPROVE,
            review_notes="Looks correct",
        ),
        event_context=SimpleNamespace(actor_id=actor_id, correlation_id=correlation_id),
    )

    assert response is not None
    assert response.status == "verified"
    assert response.verification_status == "verified"
    assert pending_form.verified_by == actor_id
    assert pending_form.review_count == 1
    assert session.commits == 1
    assert [event.event_type for event in store.events] == ["review.approved"]
    assert store.events[0].payload["actor_id"] == str(actor_id)
    assert store.events[0].payload["correlation_id"] == str(correlation_id)
    assert store.events[0].payload["review_notes"] == "Looks correct"


@pytest.mark.anyio
async def test_admin_can_reject_pending_form_and_event_is_emitted() -> None:
    """Rejecting a pending form should reject it and emit review.rejected."""

    pending_form = form()
    service, _session, store = build_review_service([pending_form])

    response = await service.decide_review(
        university_id=pending_form.university_id,
        request=ReviewDecisionRequest(
            entity_type="form",
            entity_id=pending_form.id,
            decision=ReviewDecision.REJECT,
            review_notes="Outdated form",
        ),
        event_context=SimpleNamespace(actor_id=uuid4(), correlation_id=uuid4()),
    )

    assert response is not None
    assert response.status == "rejected"
    assert response.verification_status == "rejected"
    assert pending_form.is_active is False
    assert [event.event_type for event in store.events] == ["review.rejected"]
    assert store.events[0].payload["review_notes"] == "Outdated form"


@pytest.mark.anyio
async def test_invalid_review_transition_fails_securely() -> None:
    """Only pending-review forms should accept review decisions."""

    verified_form = form(status="verified", verification_status="verified")
    service, _session, _store = build_review_service([verified_form])

    with pytest.raises(InvalidReviewDecisionError):
        await service.decide_review(
            university_id=verified_form.university_id,
            request=ReviewDecisionRequest(
                entity_type="form",
                entity_id=verified_form.id,
                decision=ReviewDecision.REJECT,
            ),
            event_context=SimpleNamespace(actor_id=uuid4(), correlation_id=uuid4()),
        )


class FakeRouteReviewService:
    """Route dependency fake for RBAC tests."""

    async def decide_review(self, **kwargs):
        """Return a deterministic decision response."""

        request = kwargs["request"]
        return ReviewDecisionResponse(
            entity_type=request.entity_type,
            entity_id=request.entity_id,
            decision=request.decision,
            status="verified",
            verification_status="verified",
            review_notes=request.review_notes,
        )


def override_user(role: UserRole):
    """Build an authenticated user dependency override."""

    async def dependency() -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=uuid4(),
            university_id=uuid4(),
            role=role,
        )

    return dependency


def test_student_cannot_approve_or_reject() -> None:
    """Students should fail RBAC checks for review decisions."""

    app.dependency_overrides[get_current_user] = override_user(UserRole.STUDENT)
    app.dependency_overrides[get_review_queue_service] = lambda: FakeRouteReviewService()
    try:
        university_id = uuid4()
        response = TestClient(app).post(
            "/governance/reviews/decision",
            headers={"X-University-ID": str(university_id)},
            json={
                "entity_type": "form",
                "entity_id": str(uuid4()),
                "decision": "approve",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


class FakeRetrievalRepository:
    """Repository fake that returns mixed governance statuses."""

    async def search_forms(self, query, university_id, limit):
        """Return both retrievable and rejected forms."""

        return [
            form(
                university_id=university_id,
                title="Visible Form",
                status="verified",
                verification_status="verified",
                verification_score=1.0,
            ),
            form(
                university_id=university_id,
                title="Rejected Form",
                status="rejected",
                verification_status="rejected",
            ),
        ]


@pytest.mark.anyio
async def test_retrieval_excludes_rejected_forms() -> None:
    """Retrieval service should defensively exclude rejected forms."""

    university_id = uuid4()
    service = FormsRetrievalService(FakeRetrievalRepository(), embedding_provider=None)

    results = await service.retrieve_forms(
        query="form",
        university_id=university_id,
        limit=10,
    )

    assert [result.title for result in results] == ["Visible Form"]
