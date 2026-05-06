"""Schemas for natural language query handling."""

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    """Request accepted by the natural language query endpoint."""

    query: str = Field(default="")


class RoutingDecision(BaseModel):
    """Validated structured output from the router."""

    tool: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)


class QueryResponse(BaseModel):
    """Structured response returned by the query endpoint."""

    answer: str
    tool_used: str | None = None
    confidence: float = 0.0
    data: Any = Field(default_factory=dict)
    status: str = "success"
