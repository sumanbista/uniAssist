"""Shared API schemas for observable query execution."""

from typing import Any

from pydantic import BaseModel, Field


class ToolTrace(BaseModel):
    """Trace metadata for router selection and tool execution."""

    tool_name: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    parameters: dict[str, Any] = Field(default_factory=dict)
    execution_time_ms: int = 0
    status: str
    source: str | None = None
    last_updated: str | None = None
    request_id: str | None = None
    message: str | None = None
    role: str | None = None
    authorized: bool = False
    error_type: str | None = None
