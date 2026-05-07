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
) -> QueryResponse:
    """Return a safe response when no reliable tool answer is available."""

    return QueryResponse(
        answer=FALLBACK_ANSWER,
        tool_used=None,
        confidence=confidence,
        data=data or {},
        status="fallback",
        trace=ToolTrace(
            tool_name=tool_name,
            confidence=confidence,
            parameters=parameters or {},
            status="fallback",
            message=message or FALLBACK_ANSWER,
        ),
    )
