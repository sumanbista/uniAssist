"""Deterministic normalization for Caldwell extracted records."""

from app.domains.ingestion.enums import IngestionContentType
from app.domains.ingestion.schemas import (
    ExtractedCalendarEntry,
    ExtractedForm,
    ParsedHtmlRecord,
)
from app.domains.ingestion.security import sanitize_text, source_hash


class NormalizationError(ValueError):
    """Raised when parsed content cannot become canonical content."""


class IngestionNormalizer:
    """Convert parsed Caldwell records into canonical extracted entities."""

    def normalize_forms(self, records: list[ParsedHtmlRecord]) -> list[ExtractedForm]:
        """Normalize parsed records into canonical forms."""

        return [
            ExtractedForm(
                source_url=record.source_url,
                title=_title(record.title),
                description=_description(record.description),
                extracted_at=record.extracted_at,
                source_hash=_canonical_hash(IngestionContentType.FORMS, record),
            )
            for record in records
        ]

    def normalize_calendar_entries(
        self,
        records: list[ParsedHtmlRecord],
    ) -> list[ExtractedCalendarEntry]:
        """Normalize parsed records into canonical calendar entries."""

        return [
            ExtractedCalendarEntry(
                source_url=record.source_url,
                title=_title(record.title),
                description=_description(record.description),
                extracted_at=record.extracted_at,
                source_hash=_canonical_hash(IngestionContentType.CALENDAR, record),
            )
            for record in records
        ]


def _title(value: str) -> str:
    """Normalize and validate a canonical title."""

    normalized_title = sanitize_text(value, max_length=255)
    if not normalized_title:
        raise NormalizationError("canonical title is required")
    return normalized_title


def _description(value: str) -> str:
    """Normalize a canonical description."""

    return sanitize_text(value, max_length=2000)


def _canonical_hash(content_type: IngestionContentType, record: ParsedHtmlRecord) -> str:
    """Return deterministic canonical entity hash."""

    return source_hash(
        content_type.value,
        str(record.source_url),
        _title(record.title).lower(),
        _description(record.description),
    )

