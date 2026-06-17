"""Focused regressions for auth, tenant, and contract hardening."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.domains.auth.models.roles import UserRole
from app.domains.forms.api.forms import get_forms_retrieval_service
from app.domains.forms.retrieval.service import FormsRetrievalService, RetrievedForm
from app.domains.governance.review_queue.api import get_review_queue_service
from app.domains.governance.review_queue.schemas import ReviewItemResponse
from app.domains.ingestion.pdf_forms.api import get_pdf_form_ingestion_service
from app.domains.ingestion.pdf_forms.schemas import PdfFormUploadResponse
from app.domains.orchestration.api.orchestrator import get_retrieval_orchestrator
from app.domains.orchestration.schemas import (
    OrchestrationResponse,
    OrchestrationStatus,
    OrchestrationToolName,
    OrchestrationTrace,
)
from app.main import app


JWT_SECRET = "test-secret-with-at-least-32-bytes"


@pytest.fixture(autouse=True)
def configure_jwt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Use real JWT verification with deterministic test settings."""

    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", JWT_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_JWT_AUDIENCE", "authenticated")
    monkeypatch.setattr(settings, "SUPABASE_JWT_ISSUER", None)


@pytest.fixture()
def client() -> TestClient:
    """Return a TestClient and clean dependency overrides after use."""

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def auth_headers(
    *,
    role: UserRole = UserRole.STUDENT,
    university_id: UUID | None = None,
) -> dict[str, str]:
    """Build a bearer token for route-level regression tests."""

    token = jwt.encode(
        {
            "sub": str(uuid4()),
            "aud": "authenticated",
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "app_metadata": {
                "university_id": str(university_id or uuid4()),
                "role": role.value,
            },
        },
        JWT_SECRET,
        algorithm="HS256",
    )
    return {"Authorization": f"Bearer {token}"}


def test_tools_routes_require_auth_and_preserve_tool_rbac(client: TestClient) -> None:
    """Direct tool routes should require JWT auth and enforce tool permissions."""

    unauthenticated = client.get("/tools/reg_faq", params={"query": "register"})
    assert unauthenticated.status_code == 401

    unauthorized_role = client.get(
        "/tools/reg_faq",
        params={"query": "register"},
        headers=auth_headers(role=UserRole.FACULTY),
    )
    assert unauthorized_role.status_code == 403

    allowed_role = client.get(
        "/tools/reg_faq",
        params={"query": "register"},
        headers=auth_headers(role=UserRole.STUDENT),
    )
    assert allowed_role.status_code == 200
    assert allowed_role.json()["status"] == "success"


@pytest.mark.parametrize(
    "path",
    [
        "/analytics/summary",
        "/analytics/tools",
        "/analytics/roles",
        "/analytics/recent",
    ],
)
def test_analytics_routes_reject_missing_and_non_admin_auth(
    client: TestClient,
    path: str,
) -> None:
    """Analytics endpoints should ignore role query params and require admin JWTs."""

    assert client.get(path).status_code == 401
    assert client.get(f"{path}?role=admin").status_code == 401

    student_response = client.get(
        f"{path}?role=admin",
        headers=auth_headers(role=UserRole.STUDENT),
    )
    assert student_response.status_code == 403


@pytest.mark.parametrize(
    "role",
    [UserRole.ADMIN, UserRole.UNIVERSITY_ADMIN, UserRole.SUPER_ADMIN],
)
def test_analytics_routes_allow_governance_admin_roles(
    client: TestClient,
    role: UserRole,
) -> None:
    """All governance admin-class roles should be able to read analytics."""

    response = client.get("/analytics/summary", headers=auth_headers(role=role))

    assert response.status_code == 200
    assert "total_queries" in response.json()


class RecordingOrchestrator:
    """Fake orchestrator that records the tenant passed by the route."""

    def __init__(self) -> None:
        self.seen_university_id: UUID | None = None

    async def execute_query(
        self,
        *,
        query: str,
        university_id: UUID,
        correlation_id: UUID | None = None,
    ) -> OrchestrationResponse:
        """Return the observed tenant in response metadata."""

        self.seen_university_id = university_id
        request_id = uuid4()
        resolved_correlation_id = correlation_id or request_id
        return OrchestrationResponse(
            trace=OrchestrationTrace(
                request_id=request_id,
                correlation_id=resolved_correlation_id,
                query=query,
                selected_tools=[OrchestrationToolName.FORMS_SEARCH],
                execution_order=[],
                step_results=[],
                latency_ms=0,
                confidence_score=0.0,
                status=OrchestrationStatus.SUCCESS,
            ),
            results={},
            metadata={"university_id": str(university_id)},
        )


def test_orchestrator_query_requires_auth_and_derives_tenant_from_jwt(
    client: TestClient,
) -> None:
    """The orchestrator must not trust caller-supplied tenant headers."""

    assert client.post("/orchestrator/query", json={"query": "forms"}).status_code == 401

    jwt_university_id = uuid4()
    attacker_university_id = uuid4()
    orchestrator = RecordingOrchestrator()
    app.dependency_overrides[get_retrieval_orchestrator] = lambda: orchestrator

    response = client.post(
        "/orchestrator/query",
        headers={
            **auth_headers(
                role=UserRole.STUDENT,
                university_id=jwt_university_id,
            ),
            "X-University-ID": str(attacker_university_id),
        },
        json={"query": "forms"},
    )

    assert response.status_code == 200
    assert orchestrator.seen_university_id == jwt_university_id
    assert response.json()["metadata"]["university_id"] == str(jwt_university_id)
    assert response.json()["metadata"]["university_id"] != str(attacker_university_id)


def form(status: str, verification_status: str, title: str | None = None):
    """Build a form-like object for retrieval filtering tests."""

    return SimpleNamespace(
        id=uuid4(),
        university_id=uuid4(),
        title=title or f"{status} form",
        description=None,
        category=None,
        source_url=None,
        verification_status=verification_status,
        verification_score=1.0,
        last_verified_at=datetime.now(UTC),
        next_review_at=None,
        expires_at=None,
        staleness_score=0.0,
        status=status,
        metadata_={},
    )


class MixedStatusFormsRepository:
    """Repository fake returning every lifecycle class relevant to retrieval."""

    async def search_forms(self, query, university_id, limit):
        """Return mixed forms; the retrieval service must filter visibility."""

        return [
            form("pending_review", "pending_review", "Pending Form"),
            form("verified", "verified", "Verified Form"),
            form("published", "published", "Published Form"),
            form("rejected", "rejected", "Rejected Form"),
            form("archived", "archived", "Archived Form"),
            form("deprecated", "deprecated", "Deprecated Form"),
        ]


@pytest.mark.anyio
async def test_forms_retrieval_visibility_filters_to_verified_and_published() -> None:
    """Student-facing retrieval should only expose verified or published forms."""

    service = FormsRetrievalService(
        MixedStatusFormsRepository(),
        embedding_provider=None,
    )

    results = await service.retrieve_forms(
        query="form",
        university_id=uuid4(),
        limit=10,
    )

    statuses = {result.status for result in results}
    assert statuses == {"verified", "published"}
    assert {result.title for result in results} == {"Verified Form", "Published Form"}


class UploadContractService:
    """Fake upload service returning the public upload response schema."""

    async def ingest_pdf_form(self, **kwargs):
        """Return a deterministic upload response."""

        return PdfFormUploadResponse(
            form_id=uuid4(),
            title=kwargs["metadata"].title,
            status="pending_review",
            verification_status="pending_review",
            extracted_text_preview="preview",
            page_count=1,
        )


class ReviewContractService:
    """Fake review service returning the public review response schema."""

    async def list_pending_reviews(self, **_kwargs):
        """Return one pending review item."""

        return [
            ReviewItemResponse(
                entity_type="form",
                entity_id=uuid4(),
                title="Tuition Appeal",
                status="pending_review",
                verification_status="pending_review",
                submitted_at=datetime.now(UTC),
                source_metadata={"upload_method": "admin_pdf"},
            )
        ]


class SearchContractService:
    """Fake forms retrieval service returning the public search response schema."""

    async def retrieve_forms(self, **_kwargs):
        """Return one verified form search result."""

        return [
            RetrievedForm(
                id=uuid4(),
                university_id=uuid4(),
                title="Verified Tuition Appeal",
                description=None,
                category=None,
                source_url=None,
                verification_status="verified",
                verification_score=1.0,
                last_verified_at=datetime.now(UTC),
                next_review_at=None,
                expires_at=None,
                staleness_score=0.0,
                status="verified",
                metadata={},
                ranking_score=0.9,
                ranking_signals={"governance_status": 1.0},
            )
        ]


def test_external_responses_do_not_include_storage_path(client: TestClient) -> None:
    """Upload, review, and form search responses should hide storage internals."""

    university_id = uuid4()
    app.dependency_overrides[get_pdf_form_ingestion_service] = (
        lambda: UploadContractService()
    )
    app.dependency_overrides[get_review_queue_service] = lambda: ReviewContractService()
    app.dependency_overrides[get_forms_retrieval_service] = lambda: SearchContractService()

    admin_headers = auth_headers(role=UserRole.ADMIN, university_id=university_id)
    student_headers = auth_headers(role=UserRole.STUDENT, university_id=university_id)

    upload_response = client.post(
        "/ingestion/forms/pdf",
        headers=admin_headers,
        data={"title": "Tuition Appeal"},
        files={"file": ("tuition.pdf", b"%PDF-1.7\nbody", "application/pdf")},
    )
    assert upload_response.status_code == 200
    assert "storage_path" not in upload_response.json()

    review_response = client.get(
        "/governance/reviews/pending",
        headers=admin_headers,
    )
    assert review_response.status_code == 200
    assert "storage_path" not in review_response.json()[0]

    search_response = client.get(
        "/forms/search",
        headers=student_headers,
        params={"q": "tuition"},
    )
    assert search_response.status_code == 200
    assert "storage_path" not in search_response.json()["forms"][0]


def test_frontend_contract_uses_authenticated_pdf_fetch_without_storage_path() -> None:
    """Frontend API code should derive PDF access from form ID and auth headers."""

    repo_root = Path(__file__).resolve().parents[3]
    api_client = (repo_root / "frontend/src/lib/api.ts").read_text()
    form_results = (
        repo_root / "frontend/src/components/FormSearchResults.tsx"
    ).read_text()

    assert "storage_path" not in api_client
    assert "export async function openFormPdf" in api_client
    assert "fetch(getFormFileUrl(formId)" in api_client
    assert "headers: authHeaders()" in api_client
    assert "URL.createObjectURL" in api_client
    assert "openFormPdf(form.form_id)" in form_results
    assert "href={form.file_url}" not in form_results
