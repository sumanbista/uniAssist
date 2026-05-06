"""Shared schemas for tool requests and responses."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class ToolRequest(BaseModel):
    """Request body accepted by generic tool execution endpoints."""

    params: dict[str, Any] = Field(default_factory=dict)


class ToolSuccessResponse(BaseModel):
    """Standard success response returned by every tool."""

    status: Literal["success"] = "success"
    data: Any
    source: str
    last_updated: str


class ToolErrorResponse(BaseModel):
    """Standard error response returned by every tool."""

    status: Literal["error"] = "error"
    message: str


class ToolMetadata(BaseModel):
    """Public metadata for an available tool."""

    name: str
    description: str
    allowed_roles: list[str]
