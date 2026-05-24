"""Append-only event persistence and replay access."""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.events.models import EventStoreRecord
from app.shared.events.schemas import PlatformEvent


class EventStore:
    """Persistent event store backed by Supabase Postgres."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(self, event: PlatformEvent) -> PlatformEvent:
        """Append an immutable event record."""

        record = EventStoreRecord(
            event_id=event.event_id,
            event_type=event.event_type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            university_id=event.university_id,
            actor_id=event.actor_id,
            payload=event.payload,
            metadata_=event.metadata,
            occurred_at=event.occurred_at,
            version=event.version,
            correlation_id=event.correlation_id,
        )
        self.session.add(record)
        await self.session.commit()
        return event

    async def replay_events(
        self,
        aggregate_id: UUID | None = None,
        event_types: Sequence[str] | None = None,
        university_id: UUID | None = None,
        limit: int = 1000,
    ) -> list[PlatformEvent]:
        """Return stored events in deterministic replay order."""

        bounded_limit = _bounded_replay_limit(limit)
        query = self._replay_query(
            aggregate_id=aggregate_id,
            event_types=event_types,
            university_id=university_id,
        )
        rows = await self.session.execute(
            query.order_by(
                EventStoreRecord.occurred_at.asc(),
                EventStoreRecord.event_id.asc(),
            ).limit(bounded_limit)
        )
        return [_record_to_event(record) for record in rows.scalars().all()]

    @staticmethod
    def _replay_query(
        aggregate_id: UUID | None = None,
        event_types: Sequence[str] | None = None,
        university_id: UUID | None = None,
    ) -> Select[tuple[EventStoreRecord]]:
        """Build a replay query with optional deterministic filters."""

        query = select(EventStoreRecord)
        if aggregate_id is not None:
            query = query.where(EventStoreRecord.aggregate_id == aggregate_id)
        if university_id is not None:
            query = query.where(EventStoreRecord.university_id == university_id)
        if event_types is not None:
            normalized_event_types = [
                event_type.strip().lower()
                for event_type in event_types
                if event_type.strip()
            ]
            if normalized_event_types:
                query = query.where(EventStoreRecord.event_type.in_(normalized_event_types))
        return query


def _record_to_event(record: EventStoreRecord) -> PlatformEvent:
    """Convert a durable event record into the canonical event schema."""

    return PlatformEvent(
        event_id=record.event_id,
        event_type=record.event_type,
        aggregate_type=record.aggregate_type,
        aggregate_id=record.aggregate_id,
        university_id=record.university_id,
        actor_id=record.actor_id,
        payload=record.payload,
        metadata=record.metadata_,
        occurred_at=record.occurred_at,
        version=record.version,
        correlation_id=record.correlation_id,
    )


def _bounded_replay_limit(limit: int) -> int:
    """Clamp replay size to a safe deterministic range."""

    return min(max(limit, 1), 10000)
