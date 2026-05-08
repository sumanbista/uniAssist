"""Tests for Sprint 2 query routing pipeline."""

import unittest

from fastapi.testclient import TestClient

from app.main import app
from app.models.query import RoutingDecision
from app.router.routing_logic import parse_routing_decision
from app.router.routing_logic import RoutingLogic
from app.services.registry_factory import build_tool_registry


class QueryPipelineTests(unittest.TestCase):
    """Validate router, tool execution, formatting, and fallback behavior."""

    def setUp(self) -> None:
        """Create a test client for each test."""

        self.client = TestClient(app)

    def test_all_tools_route_from_natural_language(self) -> None:
        """Each Phase 1 tool should be reachable through /query."""

        cases = {
            "When is add/drop?": "deadline_query",
            "Who is the CS department chair?": "contact_lookup",
            "What registration events are available?": "events_fetch",
            "When are holidays in Spring 2026?": "calendar_query",
            "How do I register for classes?": "reg_faq",
        }

        correct_routes = 0
        for query, expected_tool in cases.items():
            response = self.client.post("/query", json={"query": query})
            body = response.json()
            self.assertEqual(response.status_code, 200)
            self.assertEqual(body["tool_used"], expected_tool)
            self.assertEqual(body["status"], "success")
            self.assertGreaterEqual(body["confidence"], 0.7)
            self.assertEqual(body["trace"]["tool_name"], expected_tool)
            self.assertEqual(body["trace"]["status"], "success")
            self.assertIn("execution_time_ms", body["trace"])
            self.assertIsInstance(body["trace"]["parameters"], dict)
            correct_routes += int(body["tool_used"] == expected_tool)

        self.assertGreaterEqual(correct_routes / len(cases), 0.8)

    def test_unrelated_query_uses_fallback(self) -> None:
        """Unknown requests should not trigger tool answers."""

        response = self.client.post("/query", json={"query": "Tell me a joke"})
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "fallback")
        self.assertIsNone(body["tool_used"])
        self.assertEqual(body["trace"]["status"], "fallback")
        self.assertLess(body["trace"]["confidence"], 0.7)

    def test_student_can_access_registration_faq(self) -> None:
        """Students should be allowed to execute registration FAQ."""

        response = self.client.post(
            "/query",
            json={"query": "How do I register for classes?", "role": "student"},
        )
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["tool_used"], "reg_faq")
        self.assertTrue(body["trace"]["authorized"])
        self.assertEqual(body["trace"]["role"], "student")

    def test_faculty_cannot_access_registration_faq(self) -> None:
        """Faculty should receive access denied before tool execution."""

        response = self.client.post(
            "/query",
            json={"query": "How do I resolve registration holds?", "role": "faculty"},
        )
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["data"]["error_type"], "access_denied")
        self.assertEqual(body["trace"]["error_type"], "access_denied")
        self.assertFalse(body["trace"]["authorized"])
        self.assertEqual(body["trace"]["role"], "faculty")

    def test_admin_can_access_deadline_query(self) -> None:
        """Admins should be allowed to execute deadline queries."""

        response = self.client.post(
            "/query",
            json={"query": "When is add/drop deadline?", "role": "admin"},
        )
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "success")
        self.assertEqual(body["tool_used"], "deadline_query")
        self.assertTrue(body["trace"]["authorized"])
        self.assertEqual(body["trace"]["role"], "admin")

    def test_invalid_role_returns_structured_error(self) -> None:
        """Unsupported roles should return a frontend-readable error."""

        response = self.client.post(
            "/query",
            json={"query": "When is add/drop deadline?", "role": "guest"},
        )
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["answer"], "Unsupported role. Choose student, faculty, or admin.")
        self.assertEqual(body["trace"]["error_type"], "invalid_role")
        self.assertEqual(body["trace"]["role"], "guest")

    def test_empty_query_uses_fallback(self) -> None:
        """Empty input should return a structured fallback."""

        response = self.client.post("/query", json={"query": ""})
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["status"], "fallback")
        self.assertEqual(body["confidence"], 0.0)
        self.assertEqual(body["trace"]["status"], "fallback")

    def test_message_field_is_supported(self) -> None:
        """Sprint 4 message field should remain compatible with /query."""

        response = self.client.post("/query", json={"message": "When is add/drop?"})
        body = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(body["tool_used"], "deadline_query")
        self.assertEqual(body["trace"]["tool_name"], "deadline_query")

    def test_malformed_router_output_returns_none(self) -> None:
        """Malformed classifier JSON should fail validation predictably."""

        self.assertIsNone(parse_routing_decision("not-json"))
        self.assertIsNone(parse_routing_decision({"tool": "deadline_query"}))

    def test_tool_error_returns_safe_error_trace(self) -> None:
        """Tool failures should expose safe trace metadata without stack traces."""

        routing_logic = RoutingLogic(build_tool_registry())
        response = routing_logic.handle_decision(
            query="When is the deadline?",
            decision=RoutingDecision(
                tool="deadline_query",
                parameters={},
                confidence=0.9,
            ),
        )

        self.assertEqual(response.status, "fallback")
        self.assertEqual(response.trace.status, "error")
        self.assertEqual(response.trace.tool_name, "deadline_query")
        self.assertIsNotNone(response.trace.message)

    def test_query_endpoint_persists_log(self) -> None:
        """Query endpoint should persist telemetry for successful requests."""

        before = self.client.get("/analytics/summary?role=admin").json()["total_queries"]
        response = self.client.post(
            "/query",
            json={"query": "When is add/drop deadline?", "role": "student"},
        )
        after = self.client.get("/analytics/summary?role=admin").json()["total_queries"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(after, before + 1)

    def test_fallback_query_is_logged(self) -> None:
        """Fallback requests should increment fallback analytics."""

        before = self.client.get("/analytics/summary?role=admin").json()["fallback_count"]
        response = self.client.post(
            "/query",
            json={"query": "Tell me a joke", "role": "student"},
        )
        after = self.client.get("/analytics/summary?role=admin").json()["fallback_count"]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(after, before + 1)

    def test_analytics_requires_admin_role(self) -> None:
        """Analytics endpoints should be restricted to admins."""

        response = self.client.get("/analytics/summary?role=student")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json(), {"error": "Access denied"})


if __name__ == "__main__":
    unittest.main()
