"""Fallback responses for low-confidence or failed routing."""

from typing import Any

from app.models.query import QueryResponse
from app.models.schemas import ToolTrace

FALLBACK_ANSWER = (
    "I'm not confident about that request. You can ask about deadlines, "
    "events, contacts, calendar dates, or registration help."
)


def fallback_response(
    confidence: float = 0.0,
    data: Any | None = None,
    tool_name: str | None = None,
    parameters: dict[str, Any] | None = None,
    message: str | None = None,
    role: str | None = None,
    authorized: bool = False,
    error_type: str | None = None,
    status: str = "fallback",
) -> QueryResponse:
    """Return a safe response when no reliable tool answer is available."""

    answer = message if status == "error" and message else FALLBACK_ANSWER
    return QueryResponse(
        answer=answer,
        tool_used=None,
        confidence=confidence,
        data=data or {},
        status=status,
        trace=ToolTrace(
            tool_name=tool_name,
            confidence=confidence,
            parameters=parameters or {},
            status=status,
            message=message or FALLBACK_ANSWER,
            role=role,
            authorized=authorized,
            error_type=error_type,
        ),
    )
