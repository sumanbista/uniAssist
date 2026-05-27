"""Tests for the foundational constrained retrieval orchestrator."""

import asyncio
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.domains.orchestration.api.orchestrator import get_retrieval_orchestrator
from app.domains.orchestration.schemas import (
    ExecutionStep,
    OrchestrationRequest,
    OrchestrationStatus,
    OrchestrationToolName,
    ToolExecutionResult,
)
from app.domains.orchestration.services import RetrievalOrchestrator, RetrievalPlanner
from app.domains.orchestration.services.tool_registry import OrchestrationTool, ToolRegistry
from app.main import app


class FakeTool(OrchestrationTool):
    """Deterministic orchestration tool for service tests."""

    def __init__(self, name: OrchestrationToolName) -> None:
        self.name = name

    async def run(
        self,
        step: ExecutionStep,
        university_id: UUID,
        prior_results: list[ToolExecutionResult],
    ) -> ToolExecutionResult:
        """Return a stable tool result."""

        return ToolExecutionResult(
            step_id=step.step_id,
            tool_name=step.tool_name,
            status=OrchestrationStatus.SUCCESS,
            data=[{"id": str(uuid4()), "ranking_score": 0.8}],
            metadata={"result_count": 1},
            latency_ms=1,
            confidence_score=0.8,
        )


class SlowTool(OrchestrationTool):
    """Tool that exceeds the execution budget."""

    name = OrchestrationToolName.FORMS_SEARCH

    async def run(
        self,
        step: ExecutionStep,
        university_id: UUID,
        prior_results: list[ToolExecutionResult],
    ) -> ToolExecutionResult:
        """Sleep longer than the configured timeout."""

        await asyncio.sleep(0.05)
        return ToolExecutionResult(
            step_id=step.step_id,
            tool_name=step.tool_name,
            status=OrchestrationStatus.SUCCESS,
            latency_ms=1,
            confidence_score=1.0,
        )


@pytest.mark.anyio
async def test_planner_builds_bounded_allowlisted_plan() -> None:
    """Planner should emit deterministic steps within the configured budget."""

    planner = RetrievalPlanner(
        allowed_tools=["forms_search", "relationship_lookup"],
        max_steps=1,
        timeout_seconds=1.0,
        result_limit=3,
    )
    request_id = uuid4()
    correlation_id = uuid4()

    plan = planner.build_plan(
        request_id=request_id,
        correlation_id=correlation_id,
        query="withdrawal form",
    )

    assert plan.request_id == request_id
    assert plan.correlation_id == correlation_id
    assert plan.selected_tools == [OrchestrationToolName.FORMS_SEARCH]
    assert len(plan.execution_steps) == 1
    assert plan.execution_steps[0].params["limit"] == 3


@pytest.mark.anyio
async def test_orchestrator_executes_plan_and_builds_trace() -> None:
    """Orchestrator should execute bounded steps and expose replay-safe metadata."""

    registry = ToolRegistry()
    registry.register(FakeTool(OrchestrationToolName.FORMS_SEARCH))
    registry.register(FakeTool(OrchestrationToolName.SEMANTIC_FORMS_SEARCH))
    orchestrator = RetrievalOrchestrator(
        planner=RetrievalPlanner(
            allowed_tools=["forms_search", "semantic_forms_search"],
            max_steps=2,
            timeout_seconds=1.0,
            result_limit=2,
        ),
        tool_registry=registry,
    )

    response = await orchestrator.execute_query(
        query="withdrawal form",
        university_id=uuid4(),
        correlation_id=uuid4(),
    )

    assert response.trace.status == OrchestrationStatus.SUCCESS
    assert response.trace.execution_order == [
        OrchestrationToolName.FORMS_SEARCH,
        OrchestrationToolName.SEMANTIC_FORMS_SEARCH,
    ]
    assert response.trace.confidence_score == 0.8
    assert "forms_search" in response.results


@pytest.mark.anyio
async def test_orchestrator_returns_structured_timeout_result() -> None:
    """Tool timeouts should not escape as unstructured exceptions."""

    registry = ToolRegistry()
    registry.register(SlowTool())
    orchestrator = RetrievalOrchestrator(
        planner=RetrievalPlanner(
            allowed_tools=["forms_search"],
            max_steps=1,
            timeout_seconds=0.01,
            result_limit=1,
        ),
        tool_registry=registry,
    )

    response = await orchestrator.execute_query(
        query="withdrawal form",
        university_id=uuid4(),
    )

    assert response.trace.status == OrchestrationStatus.ERROR
    assert response.trace.step_results[0].error_message == "Tool execution timed out safely."
    assert response.trace.step_results[0].metadata["error_type"] == "TimeoutError"


@pytest.mark.anyio
async def test_orchestrator_handles_unregistered_tool_safely() -> None:
    """Misconfigured allowlists should return structured tool errors."""

    orchestrator = RetrievalOrchestrator(
        planner=RetrievalPlanner(
            allowed_tools=["forms_search"],
            max_steps=1,
            timeout_seconds=1.0,
            result_limit=1,
        ),
        tool_registry=ToolRegistry(),
    )

    response = await orchestrator.execute_query(
        query="withdrawal form",
        university_id=uuid4(),
    )

    assert response.trace.status == OrchestrationStatus.ERROR
    assert response.trace.step_results[0].error_message == "Tool execution failed safely."
    assert response.trace.step_results[0].metadata["error_type"] == "ValueError"


def test_orchestration_request_sanitizes_query() -> None:
    """Request schema should normalize whitespace and reject empty input."""

    request = OrchestrationRequest(query="  withdrawal   form  ")

    assert request.query == "withdrawal form"


def test_orchestrator_query_endpoint_contract() -> None:
    """API endpoint should return trace, retrieval results, and metadata."""

    async def override_orchestrator() -> RetrievalOrchestrator:
        registry = ToolRegistry()
        registry.register(FakeTool(OrchestrationToolName.FORMS_SEARCH))
        return RetrievalOrchestrator(
            planner=RetrievalPlanner(
                allowed_tools=["forms_search"],
                max_steps=1,
                timeout_seconds=1.0,
                result_limit=1,
            ),
            tool_registry=registry,
        )

    app.dependency_overrides[get_retrieval_orchestrator] = override_orchestrator
    client = TestClient(app)
    response = client.post(
        "/orchestrator/query",
        headers={"X-University-ID": str(uuid4())},
        json={"query": "withdrawal form"},
    )
    app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["trace"]["selected_tools"] == ["forms_search"]
    assert body["trace"]["status"] == "success"
    assert "forms_search" in body["results"]
    assert "correlation_id" in body["metadata"]
