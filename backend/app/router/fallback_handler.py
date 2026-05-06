"""Fallback responses for low-confidence or failed routing."""

from typing import Any

from app.models.query import QueryResponse

FALLBACK_ANSWER = (
    "I'm not confident about that request. You can ask about deadlines, "
    "events, contacts, calendar dates, or registration help."
)


def fallback_response(
    confidence: float = 0.0,
    data: Any | None = None,
) -> QueryResponse:
    """Return a safe response when no reliable tool answer is available."""

    return QueryResponse(
        answer=FALLBACK_ANSWER,
        tool_used=None,
        confidence=confidence,
        data=data or {},
        status="fallback",
    )
