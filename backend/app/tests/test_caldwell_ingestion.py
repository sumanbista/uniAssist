"""Tests for Caldwell ingestion foundations."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.ingestion.enums import IngestionContentType
from app.domains.ingestion.normalization import IngestionNormalizer
from app.domains.ingestion.schemas import ParsedHtmlRecord, RawSourceArtifact
from app.domains.ingestion.service import CaldwellIngestionService
from app.domains.ingestion.source_registry import SourceRegistry
from app.shared.events import EventBus, PlatformEvent


class InMemoryEventStore:
    """In-memory event store for ingestion service tests."""

    def __init__(self) -> None:
        self.events: list[PlatformEvent] = []

    async def append(self, event: PlatformEvent) -> PlatformEvent:
        """Append an event to memory."""

        self.events.append(event)
        return event


class FakeAdapter:
    """Deterministic adapter returning one parsed record per source."""

    async def fetch(self, source):
        """Return raw source content without network access."""

        return RawSourceArtifact(
            source=source,
            source_url=source.url,
            html_content="<html><a href='https://www.caldwell.edu/registrar/'>Form</a></html>",
            content_hash="a" * 64,
        )

    async def parse(self, artifact):
        """Return a stable parsed form record."""

        return [
            ParsedHtmlRecord(
                source_url=artifact.source_url,
                title="Add/Drop Form",
                description="Registrar workflow form",
                extracted_at=artifact.captured_at,
                source_hash="b" * 64,
            )
        ]


class FakeRepository:
    """Retry-safe fake repository keyed by source hash."""

    def __init__(self) -> None:
        self.forms_by_hash: dict[str, SimpleNamespace] = {}
        self.raw_hashes: set[str] = set()

    async def capture_raw_page(self, artifact):
        """Record raw capture hashes idempotently."""

        self.raw_hashes.add(artifact.content_hash)
        return SimpleNamespace(id=uuid4(), content_hash=artifact.content_hash)

    async def upsert_form(self, university_id, source_id, extracted_form):
        """Create once, then skip on repeated source hash."""

        if extracted_form.source_hash in self.forms_by_hash:
            return self.forms_by_hash[extracted_form.source_hash], False
        form = SimpleNamespace(
            id=uuid4(),
            university_id=university_id,
            status="pending_review",
        )
        self.forms_by_hash[extracted_form.source_hash] = form
        return form, True


def test_source_registry_exposes_only_caldwell_allowlisted_sources() -> None:
    """The registry should not accept arbitrary URLs."""

    registry = SourceRegistry()
    form_sources = registry.list_sources(IngestionContentType.FORMS)

    assert len(form_sources) == 1
    assert form_sources[0].source_id == "caldwell_registrar_forms"
    assert registry.is_allowlisted_url(str(form_sources[0].url))
    assert not registry.is_allowlisted_url("https://example.com/forms")


def test_normalizer_sanitizes_and_hashes_deterministically() -> None:
    """Canonical normalization should be stable and sanitize text."""

    record = ParsedHtmlRecord(
        source_url="https://www.caldwell.edu/registrar/",
        title="  Add/Drop\x00 Form  ",
        description="  Submit   to the registrar.  ",
        extracted_at="2026-05-28T12:00:00Z",
        source_hash="c" * 64,
    )
    normalizer = IngestionNormalizer()

    first = normalizer.normalize_forms([record])[0]
    second = normalizer.normalize_forms([record])[0]

    assert first.title == "Add/Drop Form"
    assert first.description == "Submit to the registrar."
    assert first.source_hash == second.source_hash


@pytest.mark.anyio
async def test_forms_ingestion_is_retry_safe_and_emits_events() -> None:
    """Repeated ingestion should skip existing source hashes and not duplicate events."""

    store = InMemoryEventStore()
    service = CaldwellIngestionService(
        session=None,
        adapter=FakeAdapter(),
        event_bus=EventBus(store),
    )
    service.repository = FakeRepository()

    first_response = await service.run_forms()
    second_response = await service.run_forms()

    assert first_response.records_created == 1
    assert first_response.records_skipped == 0
    assert second_response.records_created == 0
    assert second_response.records_skipped == 1
    assert [event.event_type for event in store.events] == [
        "entity.created",
        "ingestion.completed",
        "ingestion.completed",
    ]
    assert store.events[0].payload["status"] == "pending_review"
