"""Constrained retrieval orchestration service."""

import asyncio
import time
from uuid import UUID, uuid4

from app.core.logging import get_logger
from app.domains.auth.models.roles import UserRole
from app.domains.orchestration.schemas import (
    ExecutionStep,
    OrchestrationResponse,
    OrchestrationStatus,
    OrchestrationTrace,
    ToolExecutionResult,
)
from app.domains.orchestration.services.planner import RetrievalPlanner
from app.domains.orchestration.services.tool_registry import ToolRegistry

logger = get_logger(__name__)


class RetrievalOrchestrator:
    """Execute bounded retrieval plans with deterministic tool coordination."""

    def __init__(
        self,
        planner: RetrievalPlanner,
        tool_registry: ToolRegistry,
    ) -> None:
        self.planner = planner
        self.tool_registry = tool_registry

    async def execute_query(
        self,
        query: str,
        university_id: UUID,
        role: UserRole = UserRole.STUDENT,
        correlation_id: UUID | None = None,
    ) -> OrchestrationResponse:
        """Execute a tenant-scoped query through a bounded retrieval plan."""

        started_at = time.perf_counter()
        request_id = uuid4()
        resolved_correlation_id = correlation_id or request_id
        plan = self.planner.build_plan(
            request_id=request_id,
            correlation_id=resolved_correlation_id,
            query=query,
        )
        logger.info(
            "orchestration_started request_id=%s correlation_id=%s university_id=%s steps=%s",
            request_id,
            resolved_correlation_id,
            university_id,
            len(plan.execution_steps),
        )
        step_results: list[ToolExecutionResult] = []
        for step in plan.execution_steps:
            try:
                result = await asyncio.wait_for(
                    self.tool_registry.execute(
                        step=step,
                        university_id=university_id,
                        prior_results=step_results,
                        role=role,
                    ),
                    timeout=step.timeout_seconds,
                )
            except TimeoutError:
                result = _timeout_result(step)
                logger.error(
                    "orchestration_tool_timeout request_id=%s tool=%s step_id=%s",
                    request_id,
                    step.tool_name.value,
                    step.step_id,
                )
            step_results.append(result)

        latency_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        status = _status_from_results(step_results)
        confidence_score = _aggregate_confidence(step_results)
        trace = OrchestrationTrace(
            request_id=request_id,
            correlation_id=resolved_correlation_id,
            query=query,
            selected_tools=plan.selected_tools,
            execution_order=[result.tool_name for result in step_results],
            step_results=step_results,
            retrieval_metadata=_retrieval_metadata(step_results),
            confidence_metadata=_confidence_metadata(step_results),
            latency_ms=latency_ms,
            confidence_score=confidence_score,
            status=status,
        )
        logger.info(
            "orchestration_completed request_id=%s status=%s latency_ms=%s confidence=%s",
            request_id,
            status.value,
            latency_ms,
            confidence_score,
        )
        return OrchestrationResponse(
            trace=trace,
            results={
                result.tool_name.value: result.data
                for result in step_results
            },
            metadata={
                "request_id": str(request_id),
                "correlation_id": str(resolved_correlation_id),
                "latency_ms": latency_ms,
                "max_steps": plan.max_steps,
            },
        )


def _status_from_results(
    results: list[ToolExecutionResult],
) -> OrchestrationStatus:
    """Derive orchestration status from step results."""

    if not results or all(result.status == OrchestrationStatus.ERROR for result in results):
        return OrchestrationStatus.ERROR
    if any(result.status == OrchestrationStatus.ERROR for result in results):
        return OrchestrationStatus.PARTIAL
    return OrchestrationStatus.SUCCESS


def _timeout_result(step: ExecutionStep) -> ToolExecutionResult:
    """Build a structured result for a bounded tool timeout."""

    return ToolExecutionResult(
        step_id=step.step_id,
        tool_name=step.tool_name,
        status=OrchestrationStatus.ERROR,
        latency_ms=max(0, round(step.timeout_seconds * 1000)),
        confidence_score=0.0,
        error_message="Tool execution timed out safely.",
        metadata={"error_type": "TimeoutError"},
    )


def _aggregate_confidence(results: list[ToolExecutionResult]) -> float:
    """Aggregate step confidence scores deterministically."""

    successful_scores = [
        result.confidence_score
        for result in results
        if result.status == OrchestrationStatus.SUCCESS
    ]
    if not successful_scores:
        return 0.0
    return round(sum(successful_scores) / len(successful_scores), 4)


def _retrieval_metadata(results: list[ToolExecutionResult]) -> dict[str, object]:
    """Build replay-safe retrieval metadata."""

    return {
        result.tool_name.value: result.metadata
        for result in results
    }


def _confidence_metadata(results: list[ToolExecutionResult]) -> dict[str, object]:
    """Build deterministic confidence metadata by tool."""

    return {
        result.tool_name.value: {
            "confidence_score": result.confidence_score,
            "status": result.status.value,
        }
        for result in results
    }
