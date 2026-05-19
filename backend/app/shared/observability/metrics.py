"""Placeholder metrics abstraction for shared infrastructure."""

from collections import defaultdict
from dataclasses import dataclass

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class MetricPoint:
    """Single in-memory metric point."""

    name: str
    value: float
    tags: dict[str, str]


class MetricsRecorder:
    """Minimal metrics recorder until an exporter is selected."""

    def __init__(self) -> None:
        self._counters: dict[str, float] = defaultdict(float)
        self._observations: list[MetricPoint] = []

    def increment(
        self,
        name: str,
        value: float = 1,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Increment a named counter."""

        metric_name = self._validate_metric_name(name)
        self._counters[metric_name] += value
        logger.info("Metric counter incremented: %s value=%s", metric_name, value)

    def observe(
        self,
        name: str,
        value: float,
        tags: dict[str, str] | None = None,
    ) -> None:
        """Record a numeric metric observation."""

        metric_name = self._validate_metric_name(name)
        self._observations.append(
            MetricPoint(name=metric_name, value=value, tags=tags or {})
        )
        logger.info("Metric observed: %s value=%s", metric_name, value)

    def snapshot(self) -> dict[str, object]:
        """Return an in-memory snapshot for tests and local diagnostics."""

        return {
            "counters": dict(self._counters),
            "observations": list(self._observations),
        }

    @staticmethod
    def _validate_metric_name(name: str) -> str:
        """Validate a metric name."""

        metric_name = name.strip()
        if not metric_name:
            raise ValueError("metric name is required")
        return metric_name


metrics_recorder = MetricsRecorder()
