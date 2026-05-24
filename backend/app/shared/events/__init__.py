"""Shared internal event infrastructure."""

from app.shared.events.event_bus import (
    EventBus,
    dispatch_event,
    emit_event,
    register_handler,
    replay_events,
)
from app.shared.events.event_store import EventStore
from app.shared.events.handlers import EventHandler
from app.shared.events.schemas import PlatformEvent
from app.shared.events.context import EventContext

__all__ = [
    "EventBus",
    "EventContext",
    "EventHandler",
    "EventStore",
    "PlatformEvent",
    "dispatch_event",
    "emit_event",
    "register_handler",
    "replay_events",
]
