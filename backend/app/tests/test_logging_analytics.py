"""Tests for Sprint 6 query logging and analytics."""

import tempfile
import unittest
from pathlib import Path

from app.domains.analytics.services.analytics_service import AnalyticsService
from app.shared.observability.query_logger import QueryLogger
from app.shared.observability.models import QueryLogRecord


class LoggingAnalyticsTests(unittest.TestCase):
    """Validate SQLite persistence and analytics aggregation."""

    def setUp(self) -> None:
        """Create isolated telemetry storage."""

        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "query_logs.sqlite3"
        self.logger = QueryLogger(self.db_path)
        self.analytics = AnalyticsService(self.db_path)

    def tearDown(self) -> None:
        """Clean up isolated telemetry storage."""

        self.temp_dir.cleanup()

    def test_logger_writes_records(self) -> None:
        """Query logger should persist records for analytics."""

        self.logger.write(
            QueryLogRecord(
                query="When is add/drop?",
                request_id="req-1",
                tool_used="deadline_query",
                role="student",
                confidence=0.94,
                latency_ms=12,
                fallback_triggered=False,
                status="success",
            )
        )

        recent_logs = self.analytics.recent_queries()
        self.assertEqual(len(recent_logs), 1)
        self.assertEqual(recent_logs[0]["query"], "When is add/drop?")
        self.assertEqual(recent_logs[0]["request_id"], "req-1")
        self.assertEqual(recent_logs[0]["tool_used"], "deadline_query")

    def test_summary_calculates_metrics(self) -> None:
        """Analytics summary should compute totals, fallback rate, and latency."""

        records = [
            QueryLogRecord(
                query="When is add/drop?",
                request_id="req-1",
                tool_used="deadline_query",
                role="student",
                confidence=0.94,
                latency_ms=10,
                fallback_triggered=False,
                status="success",
            ),
            QueryLogRecord(
                query="Tell me a joke",
                request_id="req-2",
                tool_used=None,
                role="student",
                confidence=0.2,
                latency_ms=30,
                fallback_triggered=True,
                status="fallback",
            ),
            QueryLogRecord(
                query="How do I register?",
                request_id="req-3",
                tool_used="reg_faq",
                role="admin",
                confidence=0.91,
                latency_ms=20,
                fallback_triggered=False,
                status="success",
            ),
        ]
        for record in records:
            self.logger.write(record)

        summary = self.analytics.summary()
        self.assertEqual(summary["total_queries"], 3)
        self.assertEqual(summary["average_latency_ms"], 20)
        self.assertEqual(summary["fallback_count"], 1)
        self.assertAlmostEqual(summary["fallback_rate"], 0.3333)
        self.assertIn(summary["most_used_tool"], {"deadline_query", "reg_faq"})

    def test_tool_and_role_counts(self) -> None:
        """Analytics should aggregate counts by tool and role."""

        self.logger.write(
            QueryLogRecord(
                query="When is add/drop?",
                request_id="req-1",
                tool_used="deadline_query",
                role="student",
                confidence=0.94,
                latency_ms=10,
                fallback_triggered=False,
                status="success",
            )
        )
        self.logger.write(
            QueryLogRecord(
                query="When is add/drop?",
                request_id="req-2",
                tool_used="deadline_query",
                role="admin",
                confidence=0.94,
                latency_ms=10,
                fallback_triggered=False,
                status="success",
            )
        )

        self.assertEqual(self.analytics.tool_counts()["deadline_query"], 2)
        self.assertEqual(self.analytics.role_counts()["student"], 1)
        self.assertEqual(self.analytics.role_counts()["admin"], 1)

    def test_recent_queries_include_request_ids(self) -> None:
        """Recent query analytics should expose request IDs for debugging."""

        self.logger.write(
            QueryLogRecord(
                query="When is add/drop?",
                request_id="traceable-request",
                tool_used="deadline_query",
                role="student",
                confidence=0.94,
                latency_ms=10,
                fallback_triggered=False,
                status="success",
            )
        )

        recent_logs = self.analytics.recent_queries()
        self.assertEqual(recent_logs[0]["request_id"], "traceable-request")


if __name__ == "__main__":
    unittest.main()
