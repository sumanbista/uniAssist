"""Secure access to stored form PDF files."""

import re
from pathlib import Path, PurePosixPath
from uuid import UUID

import anyio

from app.core.logging import get_logger
from app.domains.auth.models.roles import UserRole
from app.domains.auth.schemas import AuthenticatedUser
from app.domains.forms.models import Form
from app.domains.forms.repositories import FormsRepository
from app.domains.forms.schemas import FormFileAccessResult
from app.shared.storage import LocalStorageProvider, StorageProvider

logger = get_logger(__name__)
PUBLIC_FILE_STATUSES = frozenset({"verified", "published"})
ADMIN_FILE_STATUSES = frozenset({"pending_review", "verified", "published"})
BLOCKED_FILE_STATUSES = frozenset({"rejected", "archived", "deprecated"})
ADMIN_ROLES = frozenset(
    {
        UserRole.ADMIN,
        UserRole.UNIVERSITY_ADMIN,
        UserRole.SUPER_ADMIN,
    }
)
PDF_MAGIC = b"%PDF-"
_SAFE_FILENAME_CHARS = re.compile(r"[^A-Za-z0-9._-]+")


class FormFileAccessDeniedError(PermissionError):
    """Raised when a user cannot access a form file."""


class FormFileNotFoundError(FileNotFoundError):
    """Raised when a form or stored file cannot be safely resolved."""


class FormsFileAccessService:
    """Resolve and authorize tenant-scoped stored form PDFs."""

    def __init__(
        self,
        repository: FormsRepository,
        storage_provider: StorageProvider | None = None,
    ) -> None:
        self.repository = repository
        self.storage_provider = storage_provider or LocalStorageProvider()

    async def get_form_file(
        self,
        *,
        form_id: UUID,
        current_user: AuthenticatedUser,
    ) -> FormFileAccessResult:
        """Return a safe local PDF file path for an authorized user."""

        form = await self.repository.get_form_by_id(
            university_id=current_user.university_id,
            form_id=form_id,
            include_inactive=True,
        )
        if form is None:
            raise FormFileNotFoundError("Form file not found")
        self._authorize_form_file_access(form=form, current_user=current_user)
        storage_path = self._validated_storage_path(
            storage_path=form.storage_path,
            university_id=current_user.university_id,
        )
        try:
            file_path = self.storage_provider.get_file_path(storage_path)
        except ValueError as exc:
            logger.warning(
                "form_file_path_rejected form_id=%s university_id=%s reason=invalid_storage_path",
                form.id,
                current_user.university_id,
            )
            raise FormFileNotFoundError("Form file not found") from exc
        if not await _is_existing_pdf(file_path):
            logger.warning(
                "form_file_missing_or_invalid form_id=%s university_id=%s",
                form.id,
                current_user.university_id,
            )
            raise FormFileNotFoundError("Form file not found")
        logger.info(
            "form_file_access_granted form_id=%s university_id=%s user_id=%s role=%s",
            form.id,
            current_user.university_id,
            current_user.user_id,
            current_user.role.value,
        )
        return FormFileAccessResult(
            file_path=file_path,
            filename=safe_pdf_filename(form.title),
        )

    @staticmethod
    def _authorize_form_file_access(
        *,
        form: Form,
        current_user: AuthenticatedUser,
    ) -> None:
        """Enforce lifecycle and role-based form file access."""

        if (
            form.status in BLOCKED_FILE_STATUSES
            or form.verification_status in BLOCKED_FILE_STATUSES
        ):
            logger.warning(
                "form_file_access_denied form_id=%s university_id=%s user_id=%s role=%s reason=blocked_status",
                form.id,
                current_user.university_id,
                current_user.user_id,
                current_user.role.value,
            )
            raise FormFileAccessDeniedError("Form file is not accessible")
        if (
            form.status in PUBLIC_FILE_STATUSES
            and form.verification_status in PUBLIC_FILE_STATUSES
        ):
            return
        if (
            current_user.role in ADMIN_ROLES
            and form.status in ADMIN_FILE_STATUSES
            and form.verification_status in ADMIN_FILE_STATUSES
        ):
            return
        logger.warning(
            "form_file_access_denied form_id=%s university_id=%s user_id=%s role=%s reason=insufficient_lifecycle_access",
            form.id,
            current_user.university_id,
            current_user.user_id,
            current_user.role.value,
        )
        raise FormFileAccessDeniedError("Form file is not accessible")

    @staticmethod
    def _validated_storage_path(
        *,
        storage_path: str | None,
        university_id: UUID,
    ) -> str:
        """Validate canonical storage path before touching the filesystem."""

        if not storage_path:
            raise FormFileNotFoundError("Form file not found")
        path = PurePosixPath(storage_path)
        if path.is_absolute() or ".." in path.parts:
            raise FormFileNotFoundError("Form file not found")
        if not path.parts or path.parts[0] != str(university_id):
            raise FormFileNotFoundError("Form file not found")
        if path.suffix.lower() != ".pdf":
            raise FormFileNotFoundError("Form file not found")
        return path.as_posix()


def safe_pdf_filename(title: str) -> str:
    """Generate a safe inline filename from a form title."""

    normalized = "_".join(title.strip().split())
    sanitized = _SAFE_FILENAME_CHARS.sub("_", normalized).strip("._")
    if not sanitized:
        sanitized = "form"
    return f"{sanitized[:120]}.pdf"


async def _is_existing_pdf(file_path: Path) -> bool:
    """Return whether a resolved local path is an existing PDF file."""

    def check_file() -> bool:
        if not file_path.is_file():
            return False
        with file_path.open("rb") as pdf_file:
            return pdf_file.read(len(PDF_MAGIC)) == PDF_MAGIC

    return await anyio.to_thread.run_sync(check_file)
