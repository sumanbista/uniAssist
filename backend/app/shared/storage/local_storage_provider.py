"""Local filesystem storage provider."""

from pathlib import Path, PurePosixPath
from uuid import UUID

import anyio

from app.core.config import settings
from app.shared.storage.storage_provider import StorageProvider


class LocalStorageProvider(StorageProvider):
    """Store files under deterministic university-scoped directories."""

    def __init__(self, root_path: Path | None = None) -> None:
        self.root_path = (root_path or settings.PDF_FORM_STORAGE_ROOT).resolve()

    async def save_file(
        self,
        *,
        university_id: UUID,
        relative_path: str,
        content: bytes,
    ) -> str:
        """Persist bytes under the tenant directory and return its storage path."""

        tenant_relative_path = _safe_tenant_relative_path(university_id, relative_path)
        destination = self._resolve_storage_path(tenant_relative_path)

        def write_file() -> None:
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)

        await anyio.to_thread.run_sync(write_file)
        return tenant_relative_path.as_posix()

    def get_file_path(self, storage_path: str) -> Path:
        """Return the absolute path for a previously returned storage path."""

        return self._resolve_storage_path(PurePosixPath(storage_path))

    def _resolve_storage_path(self, relative_path: PurePosixPath) -> Path:
        """Resolve a storage path and reject traversal outside the storage root."""

        destination = (self.root_path / Path(*relative_path.parts)).resolve()
        if self.root_path != destination and self.root_path not in destination.parents:
            raise ValueError("storage path escapes configured root")
        return destination


def _safe_tenant_relative_path(university_id: UUID, relative_path: str) -> PurePosixPath:
    """Build a normalized tenant-scoped path from untrusted input."""

    candidate = PurePosixPath(relative_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("invalid storage path")
    if not candidate.name:
        raise ValueError("storage filename is required")
    return PurePosixPath(str(university_id), *candidate.parts)
