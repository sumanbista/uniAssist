"""Placeholder event persistence abstraction."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class StoredEvent:
    """Internal event record prepared for future database persistence."""

    event_type: str
    payload: dict[str, Any]
    event_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class EventStore:
    """Interface for event persistence.

    The initial implementation is intentionally a no-op so domains can emit
    events before durable persistence is introduced.
    """

    async def append(self, event: StoredEvent) -> None:
        """Persist an event record."""

        return None
