"""Tests for internal event schema, bus, and replay foundations."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.shared.events import EventBus, PlatformEvent


class InMemoryEventStore:
    """Test event store that preserves append order in memory."""

    def __init__(self) -> None:
        self.events: list[PlatformEvent] = []

    async def append(self, event: PlatformEvent) -> PlatformEvent:
        """Append an event without mutation."""

        self.events.append(event)
        return event

    async def replay_events(
        self,
        aggregate_id=None,
        event_types=None,
        university_id=None,
        limit: int = 1000,
    ) -> list[PlatformEvent]:
        """Replay events with the same filters as the persistent store."""

        normalized_event_types = {
            event_type.strip().lower() for event_type in event_types or []
        }
        events = [
            event
            for event in self.events
            if aggregate_id is None or event.aggregate_id == aggregate_id
            if university_id is None or event.university_id == university_id
            if not normalized_event_types or event.event_type in normalized_event_types
        ]
        return sorted(events, key=lambda event: (event.occurred_at, event.event_id))[:limit]


def test_platform_event_is_immutable_and_deterministic() -> None:
    """Canonical events should be immutable and serialize deterministically."""

    event = PlatformEvent(
        event_type=" Forms.Verified ",
        aggregate_type=" Form ",
        aggregate_id=uuid4(),
        university_id=uuid4(),
        payload={"b": 2, "a": 1},
    )

    assert event.event_type == "forms.verified"
    assert event.aggregate_type == "form"
    assert event.deterministic_json() == event.deterministic_json()
    with pytest.raises(ValidationError):
        event.event_type = "forms.archived"


@pytest.mark.anyio
async def test_event_bus_dispatches_handlers_in_registration_order() -> None:
    """Handlers should run deterministically and isolated failures should not stop dispatch."""

    store = InMemoryEventStore()
    bus = EventBus(store)
    calls: list[str] = []

    async def first_handler(event: PlatformEvent) -> None:
        calls.append(f"first:{event.event_type}")

    async def failing_handler(event: PlatformEvent) -> None:
        calls.append(f"failing:{event.event_type}")
        raise RuntimeError("handler failed")

    async def second_handler(event: PlatformEvent) -> None:
        calls.append(f"second:{event.event_type}")

    await bus.register_handler("forms.verified", first_handler)
    await bus.register_handler("forms.verified", failing_handler)
    await bus.register_handler("forms.verified", second_handler)

    event = await bus.emit_event(
        event_type="forms.verified",
        aggregate_type="form",
        aggregate_id=uuid4(),
        university_id=uuid4(),
    )

    assert store.events == [event]
    assert calls == [
        "first:forms.verified",
        "failing:forms.verified",
        "second:forms.verified",
    ]


@pytest.mark.anyio
async def test_event_bus_replays_with_filters() -> None:
    """Replay should support deterministic aggregate and event-type filtering."""

    store = InMemoryEventStore()
    bus = EventBus(store)
    aggregate_id = uuid4()
    university_id = uuid4()
    await bus.emit_event(
        event_type="forms.verified",
        aggregate_type="form",
        aggregate_id=aggregate_id,
        university_id=university_id,
    )
    await bus.emit_event(
        event_type="forms.archived",
        aggregate_type="form",
        aggregate_id=aggregate_id,
        university_id=university_id,
    )
    await bus.emit_event(
        event_type="relationships.created",
        aggregate_type="relationship",
        aggregate_id=uuid4(),
        university_id=university_id,
    )

    events = await bus.replay_events(
        aggregate_id=aggregate_id,
        event_types=["forms.archived"],
        university_id=university_id,
    )

    assert [event.event_type for event in events] == ["forms.archived"]
