"""Application service for Caldwell ingestion runs."""

import time
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.ingestion.adapters import CaldwellUniversityAdapter
from app.domains.ingestion.enums import IngestionContentType
from app.domains.ingestion.normalization import IngestionNormalizer
from app.domains.ingestion.repository import IngestionRepository
from app.domains.ingestion.schemas import IngestionRunResponse, SourceDefinition
from app.domains.ingestion.source_registry import SourceRegistry
from app.shared.events import EventBus, EventContext, EventStore

logger = get_logger(__name__)


class CaldwellIngestionService:
    """Coordinate Caldwell source ingestion into governed canonical entities."""

    def __init__(
        self,
        session: AsyncSession,
        registry: SourceRegistry | None = None,
        adapter: CaldwellUniversityAdapter | None = None,
        normalizer: IngestionNormalizer | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.registry = registry or SourceRegistry()
        self.adapter = adapter or CaldwellUniversityAdapter()
        self.normalizer = normalizer or IngestionNormalizer()
        self.repository = IngestionRepository(session)
        self.event_bus = event_bus or EventBus(EventStore(session))

    async def run_forms(
        self,
        event_context: EventContext | None = None,
    ) -> IngestionRunResponse:
        """Run Caldwell forms ingestion once."""

        return await self._run_content_type(
            content_type=IngestionContentType.FORMS,
            event_context=event_context,
        )

    async def run_calendar(
        self,
        event_context: EventContext | None = None,
    ) -> IngestionRunResponse:
        """Run Caldwell academic calendar ingestion once."""

        return await self._run_content_type(
            content_type=IngestionContentType.CALENDAR,
            event_context=event_context,
        )

    async def _run_content_type(
        self,
        content_type: IngestionContentType,
        event_context: EventContext | None,
    ) -> IngestionRunResponse:
        """Run all allowlisted sources for one content type."""

        started_at = time.perf_counter()
        sources = self.registry.list_sources(content_type)
        records_processed = 0
        records_created = 0
        records_skipped = 0
        errors: list[str] = []
        university_id = sources[0].university_id

        for source in sources:
            try:
                processed, created, skipped = await self._ingest_source(
                    source=source,
                    event_context=event_context,
                )
                records_processed += processed
                records_created += created
                records_skipped += skipped
            except (httpx.HTTPError, ValueError) as exc:
                errors.append(f"{source.source_id}: {type(exc).__name__}")
                logger.error(
                    "ingestion_source_failed source_id=%s content_type=%s error=%s",
                    source.source_id,
                    content_type.value,
                    type(exc).__name__,
                )
                await self._emit_run_event(
                    event_type="ingestion.failed",
                    source=source,
                    duration_ms=_duration_ms(started_at),
                    event_context=event_context,
                    payload={
                        "source_id": source.source_id,
                        "error_type": type(exc).__name__,
                        "error_message": str(exc),
                    },
                )

        status = "failed" if errors and records_processed == 0 else "completed"
        event_type = "ingestion.failed" if status == "failed" else "ingestion.completed"
        await self._emit_run_event(
            event_type=event_type,
            source=sources[0],
            duration_ms=_duration_ms(started_at),
            event_context=event_context,
            payload={
                "content_type": content_type.value,
                "records_processed": records_processed,
                "records_created": records_created,
                "records_skipped": records_skipped,
                "source_ids": [source.source_id for source in sources],
                "errors_count": len(errors),
            },
        )
        logger.info(
            "ingestion_run_finished content_type=%s status=%s processed=%s created=%s skipped=%s errors=%s",
            content_type.value,
            status,
            records_processed,
            records_created,
            records_skipped,
            len(errors),
        )
        return IngestionRunResponse(
            status=status,
            university_id=university_id,
            content_type=content_type,
            records_processed=records_processed,
            records_created=records_created,
            records_skipped=records_skipped,
            source_ids=[source.source_id for source in sources],
            errors=errors,
        )

    async def _ingest_source(
        self,
        source: SourceDefinition,
        event_context: EventContext | None,
    ) -> tuple[int, int, int]:
        """Ingest one source and return processed, created, skipped counts."""

        logger.info(
            "ingestion_source_started source_id=%s content_type=%s",
            source.source_id,
            source.content_type.value,
        )
        artifact = await self.adapter.fetch(source)
        await self.repository.capture_raw_page(artifact)
        parsed_records = await self.adapter.parse(artifact)

        created = 0
        skipped = 0
        if source.content_type == IngestionContentType.FORMS:
            extracted_forms = self.normalizer.normalize_forms(parsed_records)
            for extracted_form in extracted_forms:
                entity, was_created = await self.repository.upsert_form(
                    university_id=source.university_id,
                    source_id=source.source_id,
                    extracted_form=extracted_form,
                )
                if was_created:
                    created += 1
                    await self._emit_entity_created(
                        entity_type="form",
                        entity_id=entity.id,
                        university_id=source.university_id,
                        source=source,
                        source_hash=extracted_form.source_hash,
                        event_context=event_context,
                    )
                else:
                    skipped += 1
        else:
            extracted_entries = self.normalizer.normalize_calendar_entries(parsed_records)
            for extracted_entry in extracted_entries:
                entity, was_created = await self.repository.upsert_calendar_entry(
                    university_id=source.university_id,
                    source_id=source.source_id,
                    extracted_entry=extracted_entry,
                )
                if was_created:
                    created += 1
                    await self._emit_entity_created(
                        entity_type="academic_calendar_entry",
                        entity_id=entity.id,
                        university_id=source.university_id,
                        source=source,
                        source_hash=extracted_entry.source_hash,
                        event_context=event_context,
                    )
                else:
                    skipped += 1
        return len(parsed_records), created, skipped

    async def _emit_entity_created(
        self,
        entity_type: str,
        entity_id: UUID,
        university_id: UUID,
        source: SourceDefinition,
        source_hash: str,
        event_context: EventContext | None,
    ) -> None:
        """Emit canonical entity.created event."""

        await self.event_bus.emit_event(
            event_type="entity.created",
            aggregate_type=entity_type,
            aggregate_id=entity_id,
            university_id=university_id,
            actor_id=event_context.actor_id if event_context else None,
            correlation_id=event_context.correlation_id if event_context else None,
            payload={
                "entity_type": entity_type,
                "entity_id": str(entity_id),
                "status": "pending_review",
                "source_id": source.source_id,
                "source_hash": source_hash,
            },
            metadata={"source": "caldwell_ingestion_service"},
        )

    async def _emit_run_event(
        self,
        event_type: str,
        source: SourceDefinition,
        duration_ms: int,
        event_context: EventContext | None,
        payload: dict[str, object],
    ) -> None:
        """Emit ingestion run completion or failure event."""

        await self.event_bus.emit_event(
            event_type=event_type,
            aggregate_type="ingestion_source",
            aggregate_id=source.university_id,
            university_id=source.university_id,
            actor_id=event_context.actor_id if event_context else None,
            correlation_id=event_context.correlation_id if event_context else None,
            payload={**payload, "duration_ms": duration_ms},
            metadata={
                "source": "caldwell_ingestion_service",
                "adapter_name": source.adapter_name,
                "adapter_version": source.adapter_version,
            },
        )


def _duration_ms(started_at: float) -> int:
    """Return elapsed milliseconds from a perf-counter start."""

    return max(0, round((time.perf_counter() - started_at) * 1000))
