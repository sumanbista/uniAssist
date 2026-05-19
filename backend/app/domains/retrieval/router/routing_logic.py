"""Routing validation and tool execution orchestration."""

import json
from typing import Any

from pydantic import ValidationError

from app.core.logging import get_logger
from app.domains.retrieval.schemas.query import QueryResponse, RoutingDecision
from app.domains.auth.models.roles import UserRole
from app.domains.retrieval.schemas.trace import ToolTrace
from app.domains.retrieval.router.fallback_handler import fallback_response
from app.domains.auth.services.auth_guard import AccessDeniedError, authorize_tool_access
from app.domains.retrieval.services.response_formatter import ResponseFormatter
from app.domains.retrieval.services.tool_registry import ToolRegistry

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

    def handle_decision(
        self,
        query: str,
        decision: RoutingDecision,
        role: UserRole = UserRole.STUDENT,
    ) -> QueryResponse:
        """Execute a validated decision or return a fallback response."""

        if decision.confidence < CONFIDENCE_THRESHOLD:
            return fallback_response(
                confidence=decision.confidence,
                tool_name=decision.tool or None,
                parameters=decision.parameters,
                message="Router confidence was below the execution threshold.",
                role=role.value,
                error_type="low_confidence",
            )

        tool = self.registry.get_tool(decision.tool)
        if tool is None:
            logger.error("Router selected unknown tool: %s", decision.tool)
            return fallback_response(
                confidence=decision.confidence,
                tool_name=decision.tool,
                parameters=decision.parameters,
                message="Router selected an unavailable tool.",
                role=role.value,
                error_type="invalid_tool",
            )

        if not isinstance(decision.parameters, dict):
            logger.error("Router returned invalid parameters: %s", decision.parameters)
            return fallback_response(
                confidence=decision.confidence,
                tool_name=decision.tool,
                message="Router returned invalid tool parameters.",
                role=role.value,
                error_type="invalid_parameters",
            )

        try:
            authorize_tool_access(tool, role)
        except AccessDeniedError as exc:
            return QueryResponse(
                answer=str(exc),
                tool_used=decision.tool,
                confidence=decision.confidence,
                data={
                    "status": "error",
                    "error_type": "access_denied",
                    "message": str(exc),
                },
                status="error",
                trace=ToolTrace(
                    tool_name=decision.tool,
                    confidence=decision.confidence,
                    parameters=decision.parameters,
                    status="error",
                    role=role.value,
                    authorized=False,
                    error_type="access_denied",
                    message=str(exc),
                ),
            )

        tool_result, trace = self.registry.run_tool_with_trace(
            decision.tool,
            decision.parameters,
            decision.confidence,
            role=role.value,
            authorized=True,
        )
        if tool_result.get("status") != "success":
            return QueryResponse(
                answer="I'm not confident about that request. You can ask about deadlines, events, contacts, calendar dates, or registration help.",
                tool_used=decision.tool,
                confidence=decision.confidence,
                data=tool_result,
                status="fallback",
                trace=ToolTrace(
                    tool_name=trace.tool_name,
                    confidence=trace.confidence,
                    parameters=trace.parameters,
                    execution_time_ms=trace.execution_time_ms,
                    status="error",
                    source=trace.source,
                    message=trace.message or "Tool execution failed",
                    role=role.value,
                    authorized=False,
                    error_type=trace.error_type or "tool_error",
                ),
            )

        answer = self.response_formatter.format_answer(query, decision, tool_result)
        return QueryResponse(
            answer=answer,
            tool_used=decision.tool,
            confidence=decision.confidence,
            data=tool_result.get("data", {}),
            trace=trace,
        )


def parse_routing_decision(raw_response: str | dict[str, Any]) -> RoutingDecision | None:
    """Parse and validate router output from JSON text or a dictionary."""

    try:
        response_data = json.loads(raw_response) if isinstance(raw_response, str) else raw_response
        return RoutingDecision.model_validate(response_data)
    except (json.JSONDecodeError, TypeError, ValidationError) as exc:
        logger.error("Invalid router output: %s", exc)
        return None
