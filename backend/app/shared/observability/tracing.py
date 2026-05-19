"""Basic latency tracing hooks for application operations."""

from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from time import perf_counter
from typing import AsyncIterator, Iterator

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class TraceResult:
    """Completed operation timing result."""

    operation: str
    latency_ms: int


@contextmanager
def trace_latency(operation: str) -> Iterator[None]:
    """Trace latency for a synchronous block."""

    start_time = perf_counter()
    try:
        yield
    finally:
        _log_trace(operation, start_time)


@asynccontextmanager
async def async_trace_latency(operation: str) -> AsyncIterator[None]:
    """Trace latency for an asynchronous block."""

    start_time = perf_counter()
    try:
        yield
    finally:
        _log_trace(operation, start_time)


def measure_latency(operation: str, start_time: float) -> TraceResult:
    """Build a latency result from an operation start time."""

    latency_ms = max(0, round((perf_counter() - start_time) * 1000))
    return TraceResult(operation=operation, latency_ms=latency_ms)


def _log_trace(operation: str, start_time: float) -> None:
    """Log a completed operation trace."""

    result = measure_latency(operation, start_time)
    logger.info("Trace completed: %s latency_ms=%s", operation, result.latency_ms)
