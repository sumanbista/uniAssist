"""Tests for secure admin PDF form ingestion."""

from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.domains.auth.models.roles import UserRole
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.ingestion.pdf_forms.api import get_pdf_form_ingestion_service
from app.domains.ingestion.pdf_forms.schemas import (
    ExtractedPdfPage,
    PdfExtractionResult,
    PdfFormUploadInput,
    PdfFormUploadResponse,
)
from app.domains.ingestion.pdf_forms.service import (
    PdfFormIngestionError,
    PdfFormIngestionService,
    sanitize_original_filename,
)
from app.main import app
from app.shared.auth.dependencies import get_current_user
from app.shared.events import EventBus, PlatformEvent


class FakeUpload:
    """Minimal async upload object for service validation tests."""

    def __init__(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> None:
        self.filename = filename
        self.content_type = content_type
        self._content = content

    async def read(self, size: int = -1) -> bytes:
        """Return a bounded upload body."""

        if size < 0:
            return self._content
        return self._content[:size]


class FakeStorageProvider:
    """Storage provider that records content and returns deterministic paths."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.saved_content: bytes | None = None
        self.storage_path: str | None = None

    async def save_file(
        self,
        *,
        university_id: UUID,
        relative_path: str,
        content: bytes,
    ) -> str:
        """Persist bytes to a temporary path."""

        self.saved_content = content
        self.storage_path = f"{university_id}/{relative_path}"
        destination = self.root / self.storage_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        return self.storage_path

    def get_file_path(self, storage_path: str) -> Path:
        """Return a local path for extraction."""

        return self.root / storage_path


class FakeFormsService:
    """Forms service fake that records create input."""

    def __init__(self) -> None:
        self.created_form_data = None
        self.form_id = uuid4()

    async def create_form(self, form_data):
        """Return a pending-review canonical form."""

        self.created_form_data = form_data
        return SimpleNamespace(
            id=self.form_id,
            university_id=form_data.university_id,
            title=form_data.title,
            status=form_data.status,
            verification_status=form_data.verification_status,
            storage_path=form_data.storage_path,
        )


class FakeSession:
    """SQLAlchemy session fake for raw extraction capture."""

    def __init__(self) -> None:
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, entity) -> None:
        """Record an entity pending persistence."""

        self.added.append(entity)

    async def commit(self) -> None:
        """Record a commit."""

        self.commits += 1

    async def rollback(self) -> None:
        """Record a rollback."""

        self.rollbacks += 1


class InMemoryEventStore:
    """In-memory event store for emitted event assertions."""

    def __init__(self) -> None:
        self.events: list[PlatformEvent] = []

    async def append(self, event: PlatformEvent) -> PlatformEvent:
        """Append an event to memory."""

        self.events.append(event)
        return event


async def fake_text_extractor(_path: Path) -> PdfExtractionResult:
    """Return deterministic sanitized PDF extraction text."""

    return PdfExtractionResult(
        pages=[
            ExtractedPdfPage(page_number=1, text="First page text"),
            ExtractedPdfPage(page_number=2, text="Second page text"),
        ]
    )


def pdf_upload(content: bytes = b"%PDF-1.7\nbody") -> FakeUpload:
    """Build a valid fake PDF upload."""

    return FakeUpload(
        filename="..\\unsafe/original form.pdf",
        content_type="application/pdf",
        content=content,
    )


def upload_metadata() -> PdfFormUploadInput:
    """Build valid upload metadata."""

    return PdfFormUploadInput(
        title="Tuition Appeal",
        description="Appeal workflow",
        category="financial_aid",
        department="Student Accounts",
        source_url="https://example.edu/forms/tuition-appeal.pdf",
    )


def build_service(tmp_path: Path):
    """Build a PDF ingestion service with fakes."""

    session = FakeSession()
    store = InMemoryEventStore()
    service = PdfFormIngestionService(
        session,
        storage_provider=FakeStorageProvider(tmp_path),
        event_bus=EventBus(store),
        text_extractor=fake_text_extractor,
    )
    forms_service = FakeFormsService()
    service.forms_service = forms_service
    return service, forms_service, session, store


@pytest.mark.anyio
async def test_rejects_non_pdf_content_type(tmp_path: Path) -> None:
    """Non-PDF content types should be rejected before storage."""

    service, _forms_service, _session, _store = build_service(tmp_path)

    with pytest.raises(PdfFormIngestionError):
        await service.ingest_pdf_form(
            university_id=uuid4(),
            upload=FakeUpload(
                filename="form.txt",
                content_type="text/plain",
                content=b"not pdf",
            ),
            metadata=upload_metadata(),
            event_context=SimpleNamespace(actor_id=uuid4(), correlation_id=uuid4()),
        )


@pytest.mark.anyio
async def test_rejects_oversized_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Uploads larger than the configured maximum should fail closed."""

    monkeypatch.setattr(settings, "PDF_FORM_MAX_FILE_SIZE_BYTES", 8)
    service, _forms_service, _session, _store = build_service(tmp_path)

    with pytest.raises(PdfFormIngestionError):
        await service.ingest_pdf_form(
            university_id=uuid4(),
            upload=pdf_upload(b"%PDF-1.7\noversized"),
            metadata=upload_metadata(),
            event_context=SimpleNamespace(actor_id=uuid4(), correlation_id=uuid4()),
        )


def test_safe_filename_generation() -> None:
    """Original filenames should be metadata-only and path-safe."""

    assert sanitize_original_filename("../secret.pdf") == "secret.pdf"
    assert sanitize_original_filename("..\\secret.pdf") == "secret.pdf"
    assert sanitize_original_filename("bad name?.pdf") == "bad_name_.pdf"
    assert sanitize_original_filename("") == "uploaded.pdf"


@pytest.mark.anyio
async def test_successful_pdf_upload_creates_pending_review_form_and_events(
    tmp_path: Path,
) -> None:
    """Valid PDF uploads should create governed pending-review forms."""

    service, forms_service, session, store = build_service(tmp_path)
    university_id = uuid4()
    actor_id = uuid4()
    correlation_id = uuid4()

    response = await service.ingest_pdf_form(
        university_id=university_id,
        upload=pdf_upload(),
        metadata=upload_metadata(),
        event_context=SimpleNamespace(
            actor_id=actor_id,
            correlation_id=correlation_id,
        ),
    )

    assert response.form_id == forms_service.form_id
    assert response.title == "Tuition Appeal"
    assert response.status == "pending_review"
    assert response.verification_status == "pending_review"
    assert response.page_count == 2
    assert response.extracted_text_preview == "First page text Second page text"
    assert forms_service.created_form_data.storage_path.endswith(".pdf")
    assert forms_service.created_form_data.metadata["upload_method"] == "admin_pdf"
    assert forms_service.created_form_data.metadata["embedding_status"] == "pending"
    assert forms_service.created_form_data.metadata["department"] == "Student Accounts"
    assert session.added
    assert [event.event_type for event in store.events] == [
        "forms.pdf_uploaded",
        "entity.created",
    ]
    assert store.events[0].payload["actor_id"] == str(actor_id)
    assert store.events[0].payload["university_id"] == str(university_id)
    assert store.events[0].payload["correlation_id"] == str(correlation_id)
    assert (
        store.events[0].payload["storage_path"]
        == forms_service.created_form_data.storage_path
    )
    assert store.events[0].payload["form_id"] == str(response.form_id)


class FakeRouteService:
    """FastAPI dependency fake for route tests."""

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


def override_user(role: UserRole):
    """Build an authenticated user dependency override."""

    async def dependency() -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=uuid4(),
            university_id=uuid4(),
            role=role,
        )

    return dependency


def test_pdf_upload_route_enforces_rbac() -> None:
    """Students should not be allowed to upload governed PDF forms."""

    app.dependency_overrides[get_current_user] = override_user(UserRole.STUDENT)
    app.dependency_overrides[get_pdf_form_ingestion_service] = lambda: FakeRouteService()
    try:
        response = TestClient(app).post(
            "/ingestion/forms/pdf",
            data={"title": "Blocked Form"},
            files={"file": ("form.pdf", b"%PDF-1.7\nbody", "application/pdf")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403


def test_pdf_upload_route_accepts_admin() -> None:
    """Admins should be allowed to call the PDF upload endpoint."""

    app.dependency_overrides[get_current_user] = override_user(UserRole.ADMIN)
    app.dependency_overrides[get_pdf_form_ingestion_service] = lambda: FakeRouteService()
    try:
        response = TestClient(app).post(
            "/ingestion/forms/pdf",
            data={"title": "Admin Form"},
            files={"file": ("form.pdf", b"%PDF-1.7\nbody", "application/pdf")},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "pending_review"
