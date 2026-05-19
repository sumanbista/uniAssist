"""Event handler types and registration records."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

EventPayload = dict[str, Any]
EventHandler = Callable[[EventPayload], Awaitable[None] | None]


@dataclass(frozen=True)
class HandlerRegistration:
    """Registered handler metadata for an event type."""

    event_type: str
    handler: EventHandler
