"""Central registry for all structured tools."""

import time
from typing import Any

from app.core.logging import get_logger
from app.domains.retrieval.schemas.trace import ToolTrace
from app.domains.retrieval.schemas.tool import ToolMetadata
from app.domains.retrieval.services.tool_interface import Tool

logger = get_logger(__name__)


class ToolRegistry:
    """Register and retrieve tools by name."""

    def __init__(self, tools: list[Tool]) -> None:
        self._tools = {tool.name: tool for tool in tools}

    def list_tools(self) -> list[ToolMetadata]:
        """Return metadata for every registered tool."""

        return [
            ToolMetadata(
                name=tool.name,
                description=tool.description,
                allowed_roles=tool.allowed_roles,
            )
            for tool in self._tools.values()
        ]

    def get_tool(self, tool_name: str) -> Tool | None:
        """Return a tool by name, if it exists."""

        return self._tools.get(tool_name)

    def run_tool(self, tool_name: str, params: dict[str, Any]) -> dict[str, Any]:
        """Execute a registered tool and return a structured response."""

        tool = self.get_tool(tool_name)
        if tool is None:
            return {"status": "error", "message": f"Unknown tool: {tool_name}"}

        return tool.run(params)

    def run_tool_with_trace(
        self,
        tool_name: str,
        params: dict[str, Any],
        confidence: float,
        role: str | None = None,
        authorized: bool = True,
    ) -> tuple[dict[str, Any], ToolTrace]:
        """Execute a registered tool and return its result with trace metadata."""

        start_time = time.perf_counter()
        tool = self.get_tool(tool_name)
        if tool is None:
            return self._error_result_with_trace(
                tool_name=tool_name,
                params=params,
                confidence=confidence,
                role=role,
                authorized=False,
                start_time=start_time,
                message=f"Unknown tool: {tool_name}",
                error_type="invalid_tool",
            )

        try:
            result = tool.run(params)
        except Exception as exc:
            logger.error("Tool execution failed for %s: %s", tool_name, exc)
            return self._error_result_with_trace(
                tool_name=tool_name,
                params=params,
                confidence=confidence,
                role=role,
                authorized=authorized,
                start_time=start_time,
                message="Tool execution failed",
                error_type="tool_execution_failed",
            )

        trace = ToolTrace(
            tool_name=tool_name,
            confidence=confidence,
            parameters=params,
            execution_time_ms=self._elapsed_ms(start_time),
            status=str(result.get("status", "error")),
            source=result.get("source"),
            last_updated=result.get("last_updated"),
            message=result.get("message"),
            role=role,
            authorized=authorized and result.get("status") == "success",
            error_type=None if result.get("status") == "success" else "tool_error",
        )
        return result, trace

    def _error_result_with_trace(
        self,
        tool_name: str,
        params: dict[str, Any],
        confidence: float,
        role: str | None,
        authorized: bool,
        start_time: float,
        message: str,
        error_type: str,
    ) -> tuple[dict[str, Any], ToolTrace]:
        """Create a safe error result and matching trace."""

        return (
            {"status": "error", "message": message, "error_type": error_type},
            ToolTrace(
                tool_name=tool_name,
                confidence=confidence,
                parameters=params,
                execution_time_ms=self._elapsed_ms(start_time),
                status="error",
                message=message,
                role=role,
                authorized=authorized,
                error_type=error_type,
            ),
        )

    def _elapsed_ms(self, start_time: float) -> int:
        """Return elapsed time in whole milliseconds."""

        return max(0, round((time.perf_counter() - start_time) * 1000))
