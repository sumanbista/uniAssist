"""Routing validation and tool execution orchestration."""

import json
from typing import Any

from pydantic import ValidationError

from app.core.logging import get_logger
from app.models.query import QueryResponse, RoutingDecision
from app.router.fallback_handler import fallback_response
from app.services.response_formatter import ResponseFormatter
from app.services.tool_registry import ToolRegistry

logger = get_logger(__name__)

CONFIDENCE_THRESHOLD = 0.7


class RoutingLogic:
    """Validate router decisions, execute tools, and format responses."""

    def __init__(
        self,
        registry: ToolRegistry,
        response_formatter: ResponseFormatter | None = None,
    ) -> None:
        self.registry = registry
        self.response_formatter = response_formatter or ResponseFormatter()

    def handle_decision(self, query: str, decision: RoutingDecision) -> QueryResponse:
        """Execute a validated decision or return a fallback response."""

        if decision.confidence < CONFIDENCE_THRESHOLD:
            return fallback_response(confidence=decision.confidence)

        tool = self.registry.get_tool(decision.tool)
        if tool is None:
            logger.error("Router selected unknown tool: %s", decision.tool)
            return fallback_response(confidence=decision.confidence)

        if not isinstance(decision.parameters, dict):
            logger.error("Router returned invalid parameters: %s", decision.parameters)
            return fallback_response(confidence=decision.confidence)

        tool_result = tool.run(decision.parameters)
        if tool_result.get("status") != "success":
            return fallback_response(confidence=decision.confidence, data=tool_result)

        answer = self.response_formatter.format_answer(query, decision, tool_result)
        return QueryResponse(
            answer=answer,
            tool_used=decision.tool,
            confidence=decision.confidence,
            data=tool_result.get("data", {}),
        )


def parse_routing_decision(raw_response: str | dict[str, Any]) -> RoutingDecision | None:
    """Parse and validate router output from JSON text or a dictionary."""

    try:
        response_data = json.loads(raw_response) if isinstance(raw_response, str) else raw_response
        return RoutingDecision.model_validate(response_data)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        logger.error("Invalid router output: %s", exc)
        return None
