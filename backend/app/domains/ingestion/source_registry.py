"""Explicit Caldwell source registry with no arbitrary URL ingestion."""

from app.core.config import settings
from app.domains.ingestion.enums import IngestionContentType
from app.domains.ingestion.schemas import SourceDefinition


class UnknownSourceError(ValueError):
    """Raised when an ingestion request targets an unregistered source."""


class SourceRegistry:
    """In-memory allowlist for Caldwell University ingestion sources."""

    def __init__(self) -> None:
        self._sources = _build_caldwell_sources()

    def list_sources(
        self,
        content_type: IngestionContentType | None = None,
    ) -> list[SourceDefinition]:
        """Return allowlisted sources, optionally filtered by content type."""

        sources = list(self._sources.values())
        if content_type is None:
            return sources
        return [source for source in sources if source.content_type == content_type]

    def get_source(self, source_id: str) -> SourceDefinition:
        """Return a single allowlisted source by stable ID."""

        normalized_source_id = source_id.strip().lower()
        source = self._sources.get(normalized_source_id)
        if source is None:
            raise UnknownSourceError(f"Unknown ingestion source: {source_id}")
        return source

    def is_allowlisted_url(self, url: str) -> bool:
        """Return whether a URL is directly configured for ingestion."""

        normalized_url = url.strip()
        return any(str(source.url) == normalized_url for source in self._sources.values())


def _build_caldwell_sources() -> dict[str, SourceDefinition]:
    """Build the fixed Caldwell source allowlist."""

    definitions = [
        SourceDefinition(
            source_id="caldwell_registrar_forms",
            university_id=settings.CALDWELL_UNIVERSITY_ID,
            source_name="Caldwell Registrar Forms",
            content_type=IngestionContentType.FORMS,
            url=settings.CALDWELL_FORMS_SOURCE_URL,
            parser_config={
                "record_link_keywords": ["form", "forms"],
                "fallback_title": "Registrar Forms",
                "category": "registrar",
            },
        ),
        SourceDefinition(
            source_id="caldwell_academic_calendar",
            university_id=settings.CALDWELL_UNIVERSITY_ID,
            source_name="Caldwell Downloadable Academic Calendars",
            content_type=IngestionContentType.CALENDAR,
            url=settings.CALDWELL_CALENDAR_SOURCE_URL,
            parser_config={
                "record_link_keywords": ["calendar", "fall", "spring", "summer"],
                "fallback_title": "Academic Calendar",
                "category": "academic_calendar",
            },
        ),
    ]
    return {source.source_id: source for source in definitions}
