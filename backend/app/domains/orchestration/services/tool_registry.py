"""Explicit tool registry for deterministic orchestration dispatch."""

import time
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

from app.core.logging import get_logger
from app.domains.orchestration.schemas import (
    ExecutionStep,
    OrchestrationStatus,
    OrchestrationToolName,
    ToolExecutionResult,
)

logger = get_logger(__name__)


class OrchestrationTool(ABC):
    """Typed async interface for orchestration tools."""

    name: OrchestrationToolName

    @abstractmethod
    async def run(
        self,
        step: ExecutionStep,
        university_id: UUID,
        prior_results: list[ToolExecutionResult],
    ) -> ToolExecutionResult:
        """Execute the tool and return a structured result."""


class ToolRegistry:
    """Register and execute orchestration tools without dynamic imports."""

    def __init__(self) -> None:
        self._tools: dict[OrchestrationToolName, OrchestrationTool] = {}

    def register(self, tool: OrchestrationTool) -> None:
        """Register a tool by explicit name."""

        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        self._tools[tool.name] = tool

    def require_registered(self, tool_name: OrchestrationToolName) -> None:
        """Validate that the tool is explicitly registered."""

        if tool_name not in self._tools:
            raise ValueError(f"Tool not registered: {tool_name}")

    async def execute(
        self,
        step: ExecutionStep,
        university_id: UUID,
        prior_results: list[ToolExecutionResult],
    ) -> ToolExecutionResult:
        """Dispatch a registered tool deterministically."""

        started_at = time.perf_counter()
        try:
            self.require_registered(step.tool_name)
            logger.info(
                "orchestration_tool_started tool=%s step_id=%s university_id=%s",
                step.tool_name.value,
                step.step_id,
                university_id,
            )
            return await self._tools[step.tool_name].run(
                step=step,
                university_id=university_id,
                prior_results=prior_results,
            )
        except Exception as exc:
            latency_ms = max(0, round((time.perf_counter() - started_at) * 1000))
            logger.error(
                "orchestration_tool_failed tool=%s step_id=%s error=%s",
                step.tool_name.value,
                step.step_id,
                exc,
            )
            return ToolExecutionResult(
                step_id=step.step_id,
                tool_name=step.tool_name,
                status=OrchestrationStatus.ERROR,
                latency_ms=latency_ms,
                confidence_score=0.0,
                error_message="Tool execution failed safely.",
                metadata={"error_type": exc.__class__.__name__},
            )

    def registered_tool_names(self) -> list[OrchestrationToolName]:
        """Return registered tools in deterministic order."""

        return sorted(self._tools, key=lambda tool_name: tool_name.value)
