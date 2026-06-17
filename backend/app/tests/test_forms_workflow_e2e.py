"""Route-level E2E coverage for the governed Forms PDF workflow."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.domains.auth.models.roles import UserRole
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.forms.api.forms import (
    get_forms_file_access_service,
    get_forms_retrieval_service,
)
from app.domains.forms.governance.enums import LifecycleStatus, VerificationStatus
from app.domains.forms.retrieval.service import RetrievedForm
from app.domains.forms.schemas import FormFileAccessResult
from app.domains.governance.review_queue.api import get_review_queue_service
from app.domains.governance.review_queue.schemas import (
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewItemResponse,
)
from app.domains.ingestion.pdf_forms.api import get_pdf_form_ingestion_service
from app.domains.ingestion.pdf_forms.schemas import PdfFormUploadResponse
from app.main import app
from app.shared.auth.dependencies import get_current_user


class FormsWorkflowState:
    """Shared in-memory workflow state for HTTP contract tests."""

    def __init__(self, root: Path, university_id: UUID) -> None:
        self.root = root
        self.university_id = university_id
        self.forms: dict[UUID, SimpleNamespace] = {}

    def create_form(self, *, title: str, source_url: str | None, content: bytes):
        """Create a pending-review form and write its PDF bytes."""

        form_id = uuid4()
        file_path = self.root / f"{form_id}.pdf"
        file_path.write_bytes(content)
        form = SimpleNamespace(
            id=form_id,
            university_id=self.university_id,
            title=title,
            description="Uploaded PDF form",
            category="registrar",
            source_url=source_url,
            status=LifecycleStatus.PENDING_REVIEW.value,
            verification_status=VerificationStatus.PENDING_REVIEW.value,
            verification_score=0.5,
            last_verified_at=None,
            next_review_at=None,
            expires_at=None,
            staleness_score=0.0,
            metadata_={"upload_method": "admin_pdf"},
            file_path=file_path,
            submitted_at=datetime.now(UTC),
            review_notes=None,
        )
        self.forms[form_id] = form
        return form


class FakePdfIngestionService:
    """Stateful fake preserving upload endpoint contract."""

    def __init__(self, state: FormsWorkflowState) -> None:
        self.state = state

    async def ingest_pdf_form(self, *, university_id, upload, metadata, event_context):
        """Create a pending-review form from multipart upload."""

        content = await upload.read()
        form = self.state.create_form(
            title=metadata.title,
            source_url=str(metadata.source_url) if metadata.source_url else None,
            content=content,
        )
        return PdfFormUploadResponse(
            form_id=form.id,
            title=form.title,
            status=form.status,
            verification_status=form.verification_status,
            extracted_text_preview="Uploaded PDF form",
            page_count=1,
        )


class FakeReviewQueueService:
    """Stateful fake preserving review queue endpoint contracts."""

    def __init__(self, state: FormsWorkflowState) -> None:
        self.state = state

    async def list_pending_reviews(self, *, university_id, entity_type, limit, offset):
        """Return pending forms for the tenant."""

        return [
            _review_item(form)
            for form in self.state.forms.values()
            if form.university_id == university_id
            and form.status == LifecycleStatus.PENDING_REVIEW.value
        ][offset : offset + limit]

    async def get_review_item(self, *, university_id, entity_type, entity_id):
        """Return one review item when present."""

        form = self.state.forms.get(entity_id)
        if form is None or form.university_id != university_id:
            return None
        return _review_item(form)

    async def decide_review(
        self,
        *,
        university_id,
        request: ReviewDecisionRequest,
        event_context,
    ):
        """Apply approve/reject to a pending form."""

        form = self.state.forms.get(request.entity_id)
        if form is None or form.university_id != university_id:
            return None
        if request.decision.value == "approve":
            form.status = LifecycleStatus.VERIFIED.value
            form.verification_status = VerificationStatus.VERIFIED.value
            form.verification_score = 1.0
            form.last_verified_at = datetime.now(UTC)
        else:
            form.status = LifecycleStatus.REJECTED.value
            form.verification_status = VerificationStatus.REJECTED.value
        form.review_notes = request.review_notes
        return ReviewDecisionResponse(
            entity_type="form",
            entity_id=form.id,
            decision=request.decision,
            status=form.status,
            verification_status=form.verification_status,
            review_notes=form.review_notes,
        )


class FakeFormsRetrievalService:
    """Stateful fake preserving Forms search contract."""

    def __init__(self, state: FormsWorkflowState) -> None:
        self.state = state

    async def retrieve_forms(self, query, university_id, limit):
        """Return verified forms and hide rejected forms."""

        query_text = query.casefold()
        results = [
            form
            for form in self.state.forms.values()
            if form.university_id == university_id
            and form.status == LifecycleStatus.VERIFIED.value
            and query_text in form.title.casefold()
        ]
        return [
            RetrievedForm(
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
                metadata=form.metadata_,
                ranking_score=0.9,
                ranking_signals={"governance_status": 1.0},
            )
            for form in results[:limit]
        ]


class FakeFormsFileAccessService:
    """Stateful fake preserving secure file endpoint behavior."""

    def __init__(self, state: FormsWorkflowState) -> None:
        self.state = state

    async def get_form_file(self, *, form_id, current_user):
        """Return a PDF only when role and lifecycle permit it."""

        form = self.state.forms.get(form_id)
        if form is None or form.university_id != current_user.university_id:
            from app.domains.forms.services import FormFileNotFoundError

            raise FormFileNotFoundError("Form file not found")
        if form.status == LifecycleStatus.REJECTED.value:
            from app.domains.forms.services import FormFileAccessDeniedError

            raise FormFileAccessDeniedError("Form file is not accessible")
        if (
            form.status == LifecycleStatus.PENDING_REVIEW.value
            and current_user.role
            not in {UserRole.ADMIN, UserRole.UNIVERSITY_ADMIN, UserRole.SUPER_ADMIN}
        ):
            from app.domains.forms.services import FormFileAccessDeniedError

            raise FormFileAccessDeniedError("Form file is not accessible")
        return FormFileAccessResult(
            file_path=form.file_path,
            filename=f"{form.title.replace(' ', '_')}.pdf",
        )


def _review_item(form: SimpleNamespace) -> ReviewItemResponse:
    """Convert fake form state to review response."""

    return ReviewItemResponse(
        entity_type="form",
        entity_id=form.id,
        title=form.title,
        category=form.category,
        source_url=form.source_url,
        status=form.status,
        verification_status=form.verification_status,
        submitted_at=form.submitted_at,
        source_metadata={"upload_method": "admin_pdf"},
    )


def _user(role: UserRole, university_id: UUID) -> AuthenticatedUser:
    """Build an authenticated user for dependency overrides."""

    return AuthenticatedUser(user_id=uuid4(), university_id=university_id, role=role)


def test_forms_pdf_workflow_e2e(tmp_path: Path) -> None:
    """Exercise upload, review, search, and file access contracts together."""

    university_id = uuid4()
    state = FormsWorkflowState(root=tmp_path, university_id=university_id)
    current_user = _user(UserRole.ADMIN, university_id)

    async def override_current_user() -> AuthenticatedUser:
        return current_user

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_pdf_form_ingestion_service] = lambda: FakePdfIngestionService(
        state
    )
    app.dependency_overrides[get_review_queue_service] = lambda: FakeReviewQueueService(
        state
    )
    app.dependency_overrides[get_forms_retrieval_service] = lambda: FakeFormsRetrievalService(
        state
    )
    app.dependency_overrides[get_forms_file_access_service] = lambda: FakeFormsFileAccessService(
        state
    )

    client = TestClient(app)
    try:
        upload_response = client.post(
            "/ingestion/forms/pdf",
            data={"title": "Tuition Appeal", "source_url": "https://example.edu/form.pdf"},
            files={"file": ("tuition.pdf", b"%PDF-1.7\nbody", "application/pdf")},
        )
        assert upload_response.status_code == 200
        assert "storage_path" not in upload_response.json()
        uploaded_form_id = upload_response.json()["form_id"]

        pending_response = client.get(
            "/governance/reviews/pending",
            headers={"X-University-ID": str(university_id)},
        )
        assert pending_response.status_code == 200
        assert "storage_path" not in pending_response.json()[0]
        assert [item["entity_id"] for item in pending_response.json()] == [
            uploaded_form_id
        ]

        pending_file_response = client.get(f"/forms/{uploaded_form_id}/file")
        assert pending_file_response.status_code == 200
        assert pending_file_response.headers["content-type"] == "application/pdf"

        approve_response = client.post(
            "/governance/reviews/decision",
            headers={"X-University-ID": str(university_id)},
            json={
                "entity_type": "form",
                "entity_id": uploaded_form_id,
                "decision": "approve",
                "review_notes": "Ready",
            },
        )
        assert approve_response.status_code == 200
        assert approve_response.json()["status"] == "verified"

        search_response = client.get(
            "/forms/search",
            headers={"X-University-ID": str(university_id)},
            params={"q": "Tuition", "limit": 10},
        )
        assert search_response.status_code == 200
        assert [form["id"] for form in search_response.json()["forms"]] == [
            uploaded_form_id
        ]

        current_user = _user(UserRole.STUDENT, university_id)
        student_file_response = client.get(f"/forms/{uploaded_form_id}/file")
        assert student_file_response.status_code == 200

        current_user = _user(UserRole.ADMIN, university_id)
        rejected_upload = client.post(
            "/ingestion/forms/pdf",
            data={"title": "Rejected Withdrawal"},
            files={"file": ("withdrawal.pdf", b"%PDF-1.7\nbody", "application/pdf")},
        )
        rejected_form_id = rejected_upload.json()["form_id"]
        reject_response = client.post(
            "/governance/reviews/decision",
            headers={"X-University-ID": str(university_id)},
            json={
                "entity_type": "form",
                "entity_id": rejected_form_id,
                "decision": "reject",
                "review_notes": "Outdated",
            },
        )
        assert reject_response.status_code == 200
        assert reject_response.json()["status"] == "rejected"

        rejected_search = client.get(
            "/forms/search",
            headers={"X-University-ID": str(university_id)},
            params={"q": "Rejected", "limit": 10},
        )
        assert rejected_search.status_code == 200
        assert rejected_search.json()["forms"] == []
        assert client.get(f"/forms/{rejected_form_id}/file").status_code == 403

        current_user = _user(UserRole.STUDENT, university_id)
        student_upload = client.post(
            "/ingestion/forms/pdf",
            data={"title": "Blocked"},
            files={"file": ("blocked.pdf", b"%PDF-1.7\nbody", "application/pdf")},
        )
        assert student_upload.status_code == 403
        student_review = client.post(
            "/governance/reviews/decision",
            headers={"X-University-ID": str(university_id)},
            json={
                "entity_type": "form",
                "entity_id": uploaded_form_id,
                "decision": "approve",
            },
        )
        assert student_review.status_code == 403
    finally:
        app.dependency_overrides.clear()
