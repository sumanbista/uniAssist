"""Tests for secure form PDF file access."""

from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domains.auth.models.roles import UserRole
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.forms.api.forms import get_forms_file_access_service
from app.domains.forms.schemas import FormFileAccessResult
from app.domains.forms.services import (
    FormFileAccessDeniedError,
    FormFileNotFoundError,
    FormsFileAccessService,
)
from app.main import app
from app.shared.auth.dependencies import get_current_user
from app.shared.storage import LocalStorageProvider


class FakeFormsRepository:
    """Tenant-aware repository fake for form file access tests."""

    def __init__(self, stored_form) -> None:
        self.stored_form = stored_form
        self.requested_university_id = None

    async def get_form_by_id(
        self,
        university_id,
        form_id,
        include_inactive=False,
    ):
        """Return the stored form only inside its tenant."""

        self.requested_university_id = university_id
        if (
            self.stored_form is not None
            and self.stored_form.id == form_id
            and self.stored_form.university_id == university_id
        ):
            return self.stored_form
        return None


def user(role: UserRole, university_id=None) -> AuthenticatedUser:
    """Build an authenticated user."""

    return AuthenticatedUser(
        user_id=uuid4(),
        university_id=university_id or uuid4(),
        role=role,
    )


def form(**overrides):
    """Build a form-like object with a stored PDF path."""

    university_id = overrides.pop("university_id", uuid4())
    values = {
        "id": uuid4(),
        "university_id": university_id,
        "title": "Tuition Appeal Form",
        "storage_path": f"{university_id}/pdf_forms/tuition.pdf",
        "status": "verified",
        "verification_status": "verified",
        "created_at": datetime.now(UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def write_pdf(root: Path, storage_path: str) -> None:
    """Create a minimal PDF-like file in local storage."""

    destination = root / storage_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(b"%PDF-1.7\nbody")


def build_service(tmp_path: Path, stored_form):
    """Build a file access service with local temp storage."""

    repository = FakeFormsRepository(stored_form)
    service = FormsFileAccessService(
        repository,
        storage_provider=LocalStorageProvider(tmp_path),
    )
    return service, repository


@pytest.mark.anyio
async def test_verified_form_file_opens(tmp_path: Path) -> None:
    """Verified forms should resolve to a safe inline PDF file."""

    stored_form = form()
    write_pdf(tmp_path, stored_form.storage_path)
    service, _repository = build_service(tmp_path, stored_form)

    result = await service.get_form_file(
        form_id=stored_form.id,
        current_user=user(UserRole.STUDENT, stored_form.university_id),
    )

    assert result.file_path.is_file()
    assert result.filename == "Tuition_Appeal_Form.pdf"


@pytest.mark.anyio
async def test_rejected_form_file_blocked(tmp_path: Path) -> None:
    """Rejected forms should never be file-accessible."""

    stored_form = form(status="rejected", verification_status="rejected")
    write_pdf(tmp_path, stored_form.storage_path)
    service, _repository = build_service(tmp_path, stored_form)

    with pytest.raises(FormFileAccessDeniedError):
        await service.get_form_file(
            form_id=stored_form.id,
            current_user=user(UserRole.ADMIN, stored_form.university_id),
        )


@pytest.mark.anyio
async def test_missing_file_handled_safely(tmp_path: Path) -> None:
    """Missing files should return a safe not-found error."""

    stored_form = form()
    service, _repository = build_service(tmp_path, stored_form)

    with pytest.raises(FormFileNotFoundError):
        await service.get_form_file(
            form_id=stored_form.id,
            current_user=user(UserRole.STUDENT, stored_form.university_id),
        )


@pytest.mark.anyio
async def test_cross_tenant_access_blocked(tmp_path: Path) -> None:
    """Lookup should be scoped to the requesting user's university."""

    stored_form = form()
    write_pdf(tmp_path, stored_form.storage_path)
    service, repository = build_service(tmp_path, stored_form)
    other_university_id = uuid4()

    with pytest.raises(FormFileNotFoundError):
        await service.get_form_file(
            form_id=stored_form.id,
            current_user=user(UserRole.STUDENT, other_university_id),
        )

    assert repository.requested_university_id == other_university_id


@pytest.mark.anyio
async def test_path_traversal_attempt_blocked(tmp_path: Path) -> None:
    """Canonical storage paths that escape tenant storage should be rejected."""

    university_id = uuid4()
    stored_form = form(
        university_id=university_id,
        storage_path=f"{university_id}/../../secret.pdf",
    )
    service, _repository = build_service(tmp_path, stored_form)

    with pytest.raises(FormFileNotFoundError):
        await service.get_form_file(
            form_id=stored_form.id,
            current_user=user(UserRole.ADMIN, university_id),
        )


@pytest.mark.anyio
async def test_pending_review_only_accessible_to_admin_class_roles(
    tmp_path: Path,
) -> None:
    """Pending-review PDFs should be limited to governance admin roles."""

    stored_form = form(status="pending_review", verification_status="pending_review")
    write_pdf(tmp_path, stored_form.storage_path)
    service, _repository = build_service(tmp_path, stored_form)

    admin_result = await service.get_form_file(
        form_id=stored_form.id,
        current_user=user(UserRole.UNIVERSITY_ADMIN, stored_form.university_id),
    )
    assert admin_result.file_path.is_file()

    with pytest.raises(FormFileAccessDeniedError):
        await service.get_form_file(
            form_id=stored_form.id,
            current_user=user(UserRole.STUDENT, stored_form.university_id),
        )


class FakeRouteFileService:
    """Route dependency fake that returns an existing PDF."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path

    async def get_form_file(self, **_kwargs) -> FormFileAccessResult:
        """Return a deterministic file access result."""

        return FormFileAccessResult(
            file_path=self.file_path,
            filename="Tuition_Appeal.pdf",
        )


def test_file_endpoint_returns_inline_pdf(tmp_path: Path) -> None:
    """The file endpoint should stream an inline PDF response."""

    pdf_path = tmp_path / "tuition.pdf"
    pdf_path.write_bytes(b"%PDF-1.7\nbody")
    current_user = user(UserRole.STUDENT)

    async def override_current_user() -> AuthenticatedUser:
        return current_user

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_forms_file_access_service] = lambda: FakeRouteFileService(
        pdf_path
    )
    try:
        response = TestClient(app).get(f"/forms/{uuid4()}/file")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert "inline" in response.headers["content-disposition"]
    assert "Tuition_Appeal.pdf" in response.headers["content-disposition"]
    assert response.content.startswith(b"%PDF-")
