"""Structured logging helpers with request context support."""

import contextvars
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import Response

REQUEST_ID_CONTEXT: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)


class StructuredLogFormatter(logging.Formatter):
    """Render log records as compact JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with optional request ID context."""

        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = get_request_id()
        if request_id is not None:
            payload["request_id"] = request_id
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_structured_logging(level: int = logging.INFO) -> None:
    """Configure root logging for structured JSON output."""

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredLogFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)


def bind_request_id(request_id: str) -> contextvars.Token[str | None]:
    """Bind a request ID to the current context."""

    return REQUEST_ID_CONTEXT.set(request_id)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    """Reset request ID context using a token returned by bind_request_id."""

    REQUEST_ID_CONTEXT.reset(token)


def get_request_id() -> str | None:
    """Return the request ID bound to the current context, if any."""

    return REQUEST_ID_CONTEXT.get()


async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Bind a request ID for a FastAPI request lifecycle."""

    request_id = request.headers.get("x-request-id") or str(uuid4())
    token = bind_request_id(request_id)
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = request_id
        return response
    finally:
        reset_request_id(token)
