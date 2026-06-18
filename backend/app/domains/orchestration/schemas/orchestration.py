"""Canonical schemas for constrained retrieval orchestration."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OrchestrationStatus(StrEnum):
    """Lifecycle states for an orchestration request or step."""

    SUCCESS = "success"
    ERROR = "error"
    PARTIAL = "partial"


class OrchestrationToolName(StrEnum):
    """Explicit allowlisted tools supported by the foundational orchestrator."""

    CONTACT_LOOKUP = "contact_lookup"
    FORMS_SEARCH = "forms_search"
    SEMANTIC_FORMS_SEARCH = "semantic_forms_search"
    RELATIONSHIP_LOOKUP = "relationship_lookup"
    CALENDAR_QUERY = "calendar_query"
    DEADLINE_QUERY = "deadline_query"


class OrchestrationRequest(BaseModel):
    """Request body for deterministic retrieval orchestration."""

    query: str = Field(min_length=1, max_length=255)

    @field_validator("query")
    @classmethod
    def sanitize_query(cls, value: str) -> str:
        """Normalize whitespace and reject control characters."""

        normalized_query = " ".join(value.strip().split())
        if not normalized_query:
            raise ValueError("query is required")
        if any(ord(character) < 32 for character in normalized_query):
            raise ValueError("query contains unsupported control characters")
        return normalized_query


class ExecutionStep(BaseModel):
    """Single deterministic tool execution step."""

    step_id: int = Field(ge=1)
    tool_name: OrchestrationToolName
    params: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[int] = Field(default_factory=list)
    timeout_seconds: float = Field(gt=0)


class ExecutionPlan(BaseModel):
    """Bounded linear plan produced by the deterministic planner."""

    request_id: UUID
    query: str
    selected_tools: list[OrchestrationToolName]
    execution_steps: list[ExecutionStep]
    max_steps: int = Field(ge=1)
    correlation_id: UUID
    status: OrchestrationStatus = OrchestrationStatus.SUCCESS


class ToolExecutionResult(BaseModel):
    """Replay-safe result envelope for one tool invocation."""

    step_id: int
    tool_name: OrchestrationToolName
    status: OrchestrationStatus
    data: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = Field(ge=0)
    confidence_score: float = Field(ge=0, le=1)
    error_message: str | None = None


class OrchestrationTrace(BaseModel):
    """Deterministic trace for orchestration replay and inspection."""

    request_id: UUID
    correlation_id: UUID
    query: str
    selected_tools: list[OrchestrationToolName]
    execution_order: list[OrchestrationToolName]
    step_results: list[ToolExecutionResult]
    retrieval_metadata: dict[str, Any] = Field(default_factory=dict)
    confidence_metadata: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = Field(ge=0)
    confidence_score: float = Field(ge=0, le=1)
    status: OrchestrationStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OrchestrationResponse(BaseModel):
    """API response for the constrained orchestrator."""

    model_config = ConfigDict(use_enum_values=True)

    trace: OrchestrationTrace
    results: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
