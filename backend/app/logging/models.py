"""Models for persisted query telemetry."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class QueryLogRecord:
    """Structured query execution telemetry."""

    query: str
    tool_used: str | None
    role: str | None
    confidence: float
    latency_ms: int
    fallback_triggered: bool
    status: str


@dataclass(frozen=True)
class PersistedQueryLog:
    """Query log row returned by analytics APIs."""

    id: int
    query: str
    tool_used: str | None
    role: str | None
    confidence: float
    latency_ms: int
    fallback_triggered: bool
    status: str
    created_at: datetime
