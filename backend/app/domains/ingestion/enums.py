"""Ingestion domain enumerations."""

from enum import StrEnum


class IngestionContentType(StrEnum):
    """Supported Caldwell ingestion content categories."""

    FORMS = "forms"
    CALENDAR = "calendar"


class IngestionSourceType(StrEnum):
    """Supported source transport and parser types."""

    HTML = "html"


class IngestionStatus(StrEnum):
    """Synchronous ingestion run status values."""

    COMPLETED = "completed"
    FAILED = "failed"

