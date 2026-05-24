"""Request-scoped event emission context."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EventContext(BaseModel):
    """Actor and trace metadata for audit-ready event emission."""

    model_config = ConfigDict(frozen=True)

    actor_id: UUID | None = None
    correlation_id: UUID | None = None
