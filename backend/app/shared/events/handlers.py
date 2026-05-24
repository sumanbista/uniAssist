"""Event handler types and registration records."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from app.shared.events.schemas import PlatformEvent

EventHandler = Callable[[PlatformEvent], Awaitable[None] | None]


@dataclass(frozen=True)
class HandlerRegistration:
    """Registered handler metadata for an event type."""

    event_type: str
    handler: EventHandler
