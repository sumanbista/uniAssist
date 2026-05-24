"""Async-safe in-process internal event bus."""

import asyncio
import inspect
import time
from collections import defaultdict
from collections.abc import Sequence
from typing import Any
from uuid import UUID

from pydantic import ValidationError

from app.core.logging import get_logger
from app.shared.events.event_store import EventStore
from app.shared.events.handlers import EventHandler
from app.shared.events.schemas import PlatformEvent

logger = get_logger(__name__)


class EventBus:
    """In-process event bus for deterministic modular-monolith coordination."""

    def __init__(self, event_store: EventStore) -> None:
        self._event_store = event_store
        self._handlers: dict[str, list[EventHandler]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def register_handler(
        self,
        event_type: str,
        handler: EventHandler,
    ) -> None:
        """Register a handler for an event type."""

        normalized_event_type = self._normalize_event_type(event_type)
        async with self._lock:
            self._handlers[normalized_event_type].append(handler)
        logger.info("event_handler_registered event_type=%s", normalized_event_type)

    async def emit_event(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: UUID,
        university_id: UUID,
        payload: dict[str, Any] | None = None,
        actor_id: UUID | None = None,
        correlation_id: UUID | None = None,
        metadata: dict[str, Any] | None = None,
        version: int = 1,
    ) -> PlatformEvent:
        """Persist and dispatch a canonical event."""

        started_at = time.perf_counter()
        event = PlatformEvent(
            event_type=event_type,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            university_id=university_id,
            actor_id=actor_id,
            payload=payload or {},
            metadata=metadata or {},
            correlation_id=correlation_id,
            version=version,
        )
        await self.dispatch_event(event, started_at=started_at)
        return event

    async def dispatch_event(
        self,
        event: PlatformEvent,
        started_at: float | None = None,
    ) -> None:
        """Persist a prepared event and dispatch registered handlers in order."""

        dispatch_started_at = started_at or time.perf_counter()
        try:
            await self._event_store.append(event)
        except Exception as exc:
            logger.error(
                "event_persistence_failed event_id=%s event_type=%s error=%s",
                event.event_id,
                event.event_type,
                type(exc).__name__,
            )
            return

        async with self._lock:
            handlers = list(self._handlers.get(event.event_type, []))

        for handler in handlers:
            await self._run_handler(handler, event)

        latency_ms = round((time.perf_counter() - dispatch_started_at) * 1000, 2)
        logger.info(
            "event_dispatched event_id=%s event_type=%s handlers=%s latency_ms=%s correlation_id=%s",
            event.event_id,
            event.event_type,
            len(handlers),
            latency_ms,
            event.correlation_id,
        )

    async def replay_events(
        self,
        aggregate_id: UUID | None = None,
        event_types: Sequence[str] | None = None,
        university_id: UUID | None = None,
        limit: int = 1000,
    ) -> list[PlatformEvent]:
        """Read stored events in deterministic replay order without consumers."""

        bounded_limit = min(max(limit, 1), 10000)
        started_at = time.perf_counter()
        events = await self._event_store.replay_events(
            aggregate_id=aggregate_id,
            event_types=event_types,
            university_id=university_id,
            limit=bounded_limit,
        )
        latency_ms = round((time.perf_counter() - started_at) * 1000, 2)
        logger.info(
            "events_replayed count=%s aggregate_id=%s event_types=%s latency_ms=%s",
            len(events),
            aggregate_id,
            event_types,
            latency_ms,
        )
        return events

    @staticmethod
    def _normalize_event_type(event_type: str) -> str:
        """Validate and normalize an event type."""

        return PlatformEvent(
            event_type=event_type,
            aggregate_type="validation",
            aggregate_id=UUID("00000000-0000-0000-0000-000000000000"),
            university_id=UUID("00000000-0000-0000-0000-000000000000"),
        ).event_type

    @staticmethod
    async def _run_handler(handler: EventHandler, event: PlatformEvent) -> None:
        """Run sync or async handlers with consistent failure isolation."""

        try:
            result = handler(event)
            if inspect.isawaitable(result):
                await result
        except (ValidationError, ValueError, TypeError) as exc:
            logger.error(
                "event_handler_validation_failed event_id=%s event_type=%s error=%s",
                event.event_id,
                event.event_type,
                type(exc).__name__,
            )
        except Exception as exc:
            logger.error(
                "event_handler_failed event_id=%s event_type=%s error=%s",
                event.event_id,
                event.event_type,
                type(exc).__name__,
            )


async def register_handler(
    event_bus: EventBus,
    event_type: str,
    handler: EventHandler,
) -> None:
    """Register a handler on an explicit event bus instance."""

    await event_bus.register_handler(event_type, handler)


async def emit_event(event_bus: EventBus, **kwargs: Any) -> PlatformEvent:
    """Emit an event on an explicit event bus instance."""

    return await event_bus.emit_event(**kwargs)


async def dispatch_event(event_bus: EventBus, event: PlatformEvent) -> None:
    """Dispatch a prepared event on an explicit event bus instance."""

    await event_bus.dispatch_event(event)


async def replay_events(event_bus: EventBus, **kwargs: Any) -> list[PlatformEvent]:
    """Replay events from an explicit event bus instance."""

    return await event_bus.replay_events(**kwargs)
