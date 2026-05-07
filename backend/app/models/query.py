"""Schemas for natural language query handling."""

from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.schemas import ToolTrace


class QueryRequest(BaseModel):
    """Request accepted by the natural language query endpoint."""

    query: str = Field(default="")
    message: str = Field(default="")
    role: str | None = None

    @model_validator(mode="after")
    def normalize_query_text(self) -> "QueryRequest":
        """Support both Sprint 2 query and Sprint 4 message request fields."""

        if not self.query and self.message:
            self.query = self.message
        return self


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
    trace: ToolTrace
