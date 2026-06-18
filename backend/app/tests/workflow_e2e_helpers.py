"""Shared in-memory helpers for workflow E2E contract tests."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt

from app.domains.auth.models.roles import UserRole
from app.domains.deadlines.services import DeadlineService
from app.domains.forms.retrieval.service import RetrievedForm
from app.domains.orchestration.services import (
    DeadlineQueryTool,
    FormsSearchTool,
    RelationshipLookupTool,
    RetrievalOrchestrator,
    RetrievalPlanner,
    ToolRegistry,
)
from app.domains.relationships.services import RelationshipsService
from app.domains.relationships.traversal import RelationshipTraversalService
from app.tests.deadline_helpers import FakeDeadlineRepository
from app.tests.forms_deadlines_helpers import FakeFormsRepositoryForLinks


class WorkflowFormsService:
    """In-memory Forms service for workflow contract tests."""

    def __init__(self, forms: dict[UUID, SimpleNamespace]) -> None:
        self.forms = forms

    async def create_form(self, form_data):
        """Create a form while trusting route-derived tenant context."""

        form = form_record(
            form_id=uuid4(),
            university_id=form_data.university_id,
            title=form_data.title,
            description=form_data.description,
            category=form_data.category,
            status=form_data.status,
            verification_status=form_data.verification_status,
            storage_path=form_data.storage_path,
        )
        self.forms[form.id] = form
        return form

    async def retrieve_form(self, university_id, form_id):
        """Return one tenant-scoped form."""

        form = self.forms.get(form_id)
        if form is None or form.university_id != university_id:
            return None
        return form


class WorkflowFormsRetrievalService:
    """In-memory Forms retrieval service with public governance filtering."""

    def __init__(self, forms: dict[UUID, SimpleNamespace]) -> None:
        self.forms = forms

    async def retrieve_forms(self, query, university_id, limit):
        """Return public, tenant-scoped forms matching query text."""

        normalized_query = query.casefold()
        results = [
            retrieved_form(form)
            for form in self.forms.values()
            if form.university_id == university_id
            and form.status in {"verified", "published"}
            and form.verification_status in {"verified", "published"}
            and normalized_query in f"{form.title} {form.description or ''}".casefold()
        ]
        return results[:limit]


def build_orchestrator(
    forms_retrieval_service: WorkflowFormsRetrievalService,
    relationships_service: RelationshipsService,
    deadline_service: DeadlineService,
    forms: dict[UUID, SimpleNamespace],
    deadline_repository: FakeDeadlineRepository,
) -> RetrievalOrchestrator:
    """Build a workflow-aware orchestrator over in-memory services."""

    traversal_service = RelationshipTraversalService(
        relationships_service=relationships_service,
        forms_repository=FakeFormsRepositoryForLinks(forms),
        deadlines_repository=deadline_repository,
    )
    registry = ToolRegistry()
    registry.register(FormsSearchTool(forms_retrieval_service))
    registry.register(
        RelationshipLookupTool(
            service=relationships_service,
            traversal_service=traversal_service,
        )
    )
    registry.register(DeadlineQueryTool(deadline_service))
    return RetrievalOrchestrator(
        planner=RetrievalPlanner(
            allowed_tools=["forms_search", "relationship_lookup", "deadline_query"],
            max_steps=3,
            timeout_seconds=1.0,
            result_limit=5,
        ),
        tool_registry=registry,
    )


def auth_headers(
    *,
    role: UserRole,
    university_id: UUID,
    jwt_secret: str,
    user_id: UUID | None = None,
) -> dict[str, str]:
    """Build a bearer token for route-level workflow tests."""

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
        jwt_secret,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def form_record(
    *,
    form_id: UUID,
    university_id: UUID,
    title: str,
    description: str | None = "Withdraw from a course",
    category: str | None = "registrar",
    status: str = "published",
    verification_status: str = "verified",
    storage_path: str | None = None,
) -> SimpleNamespace:
    """Build a form-like row with safe and internal fields."""

    now = datetime.now(UTC)
    return SimpleNamespace(
        id=form_id,
        university_id=university_id,
        title=title,
        description=description,
        category=category,
        source_url="https://example.edu/forms/withdrawal",
        storage_path=storage_path,
        verification_status=verification_status,
        verification_score=1.0,
        last_verified_at=now,
        verified_by=None,
        review_notes=None,
        expires_at=None,
        next_review_at=None,
        review_count=1,
        staleness_score=0.0,
        status=status,
        metadata_={"storage_path": storage_path} if storage_path else {},
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def retrieved_form(form: SimpleNamespace) -> RetrievedForm:
    """Convert an in-memory form row to a retrieval DTO."""

    return RetrievedForm(
        id=form.id,
        university_id=form.university_id,
        title=form.title,
        description=form.description,
        category=form.category,
        source_url=form.source_url,
        verification_status=form.verification_status,
        verification_score=form.verification_score,
        last_verified_at=form.last_verified_at,
        next_review_at=form.next_review_at,
        expires_at=form.expires_at,
        staleness_score=form.staleness_score,
        status=form.status,
        metadata={},
        ranking_score=1.0,
        ranking_signals={"exact_match": 1.0},
        similarity_score=None,
    )
