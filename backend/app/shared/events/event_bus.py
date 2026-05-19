"""Minimal async-safe internal event bus."""

import asyncio
import inspect
from collections import defaultdict
from typing import Any

from app.core.logging import get_logger
from app.shared.events.event_store import EventStore, StoredEvent
from app.shared.events.handlers import EventHandler

logger = get_logger(__name__)


class EventBus:
    """In-process event bus for modular-monolith coordination."""

    def __init__(self, event_store: EventStore | None = None) -> None:
        self._event_store = event_store or EventStore()
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
        logger.info("Event handler registered: %s", normalized_event_type)

    async def emit_event(self, event_type: str, payload: dict[str, Any]) -> StoredEvent:
        """Persist and dispatch an event to registered handlers."""

        normalized_event_type = self._normalize_event_type(event_type)
        event = StoredEvent(event_type=normalized_event_type, payload=payload)
        await self._event_store.append(event)

        async with self._lock:
            handlers = list(self._handlers.get(normalized_event_type, []))

        logger.info(
            "Event emitted: %s handlers=%s",
            normalized_event_type,
            len(handlers),
        )
        for handler in handlers:
            await self._run_handler(handler, event.payload)
        return event

    @staticmethod
    def _normalize_event_type(event_type: str) -> str:
        """Validate and normalize an event type."""

        normalized_event_type = event_type.strip()
        if not normalized_event_type:
            raise ValueError("event_type is required")
        return normalized_event_type

    @staticmethod
    async def _run_handler(
        handler: EventHandler,
        payload: dict[str, Any],
    ) -> None:
        """Run sync or async handlers with consistent error logging."""

        try:
            result = handler(payload)
            if inspect.isawaitable(result):
                await result
        except Exception as exc:
            logger.error("Event handler failed: %s", exc)


_default_event_bus = EventBus()


async def register_handler(event_type: str, handler: EventHandler) -> None:
    """Register a handler on the default event bus."""

    await _default_event_bus.register_handler(event_type, handler)


async def emit_event(event_type: str, payload: dict[str, Any]) -> StoredEvent:
    """Emit an event on the default event bus."""

    return await _default_event_bus.emit_event(event_type, payload)
