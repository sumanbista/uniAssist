"""Shared file storage provider contract."""

from abc import ABC, abstractmethod
from pathlib import Path
from uuid import UUID


class StorageProvider(ABC):
    """Async storage abstraction for durable non-database file blobs."""

    @abstractmethod
    async def save_file(
        self,
        *,
        university_id: UUID,
        relative_path: str,
        content: bytes,
    ) -> str:
        """Persist bytes and return the normalized storage path."""

    @abstractmethod
    def get_file_path(self, storage_path: str) -> Path:
        """Return a local filesystem path for a normalized storage path."""
