"""Canonical internal platform event schemas."""

import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

EVENT_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_.:-]*$")


class PlatformEvent(BaseModel):
    """Immutable event envelope for replayable internal platform events."""

    model_config = ConfigDict(frozen=True)

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str = Field(min_length=1, max_length=200)
    aggregate_type: str = Field(min_length=1, max_length=100)
    aggregate_id: UUID
    university_id: UUID
    actor_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    version: int = Field(default=1, ge=1)
    correlation_id: UUID | None = None

    @field_validator("event_type", "aggregate_type")
    @classmethod
    def normalize_identifier(cls, value: str) -> str:
        """Normalize stable event identifiers."""

        normalized_value = value.strip().lower()
        if not normalized_value:
            raise ValueError("event identifiers are required")
        if EVENT_IDENTIFIER_PATTERN.fullmatch(normalized_value) is None:
            raise ValueError("event identifiers must be stable machine names")
        return normalized_value

    @field_validator("payload", "metadata")
    @classmethod
    def validate_json_object(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Ensure payloads are deterministic JSON objects."""

        json.dumps(value, sort_keys=True, default=str)
        return value

    @field_serializer("occurred_at")
    def serialize_occurred_at(self, value: datetime) -> str:
        """Serialize timestamps consistently for event replay."""

        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.isoformat()

    def deterministic_json(self) -> str:
        """Return deterministic JSON for hashing, logs, and replay checks."""

        return json.dumps(
            self.model_dump(mode="json", by_alias=False, exclude_none=False),
            sort_keys=True,
            separators=(",", ":"),
        )
