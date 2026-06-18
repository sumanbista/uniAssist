"""Deterministic retrieval planner for constrained orchestration."""

from uuid import UUID

from app.core.config import settings
from app.domains.orchestration.schemas import (
    ExecutionPlan,
    ExecutionStep,
    OrchestrationStatus,
    OrchestrationToolName,
)


class RetrievalPlanner:
    """Build bounded retrieval execution plans without LLM planning."""

    def __init__(
        self,
        allowed_tools: list[str] | None = None,
        max_steps: int | None = None,
        timeout_seconds: float | None = None,
        result_limit: int | None = None,
    ) -> None:
        self.allowed_tools = {
            OrchestrationToolName(tool_name)
            for tool_name in (allowed_tools or settings.ORCHESTRATION_ALLOWED_TOOLS)
        }
        self.max_steps = max(1, max_steps or settings.ORCHESTRATION_MAX_STEPS)
        self.timeout_seconds = (
            timeout_seconds or settings.ORCHESTRATION_TOOL_TIMEOUT_SECONDS
        )
        self.result_limit = result_limit or settings.ORCHESTRATION_RESULT_LIMIT

    def build_plan(
        self,
        request_id: UUID,
        correlation_id: UUID,
        query: str,
    ) -> ExecutionPlan:
        """Build a fixed, allowlisted execution plan for the query."""

        tool_order = self._tool_order(query)
        selected_tools = [
            tool_name
            for tool_name in tool_order
            if tool_name in self.allowed_tools
        ][: self.max_steps]
        execution_steps = [
            ExecutionStep(
                step_id=index,
                tool_name=tool_name,
                params={"query": query, "limit": self.result_limit},
                depends_on=[] if index == 1 else [index - 1],
                timeout_seconds=self.timeout_seconds,
            )
            for index, tool_name in enumerate(selected_tools, start=1)
        ]
        return ExecutionPlan(
            request_id=request_id,
            query=query,
            selected_tools=selected_tools,
            execution_steps=execution_steps,
            max_steps=self.max_steps,
            correlation_id=correlation_id,
            status=OrchestrationStatus.SUCCESS,
        )

    @staticmethod
    def _tool_order(query: str) -> list[OrchestrationToolName]:
        """Choose a deterministic tool order from lightweight query signals."""

        normalized_query = query.casefold()
        calendar_keywords = (
            "calendar",
            "semester",
            "holiday",
            "break",
            "final",
            "registration period",
            "term date",
        )
        deadline_keywords = (
            "deadline",
            "due",
            "add/drop",
            "withdraw",
            "graduation",
            "tuition",
            "financial aid",
        )
        form_keywords = ("form", "application", "request")
        has_deadline = any(keyword in normalized_query for keyword in deadline_keywords)
        has_form = any(keyword in normalized_query for keyword in form_keywords)
        if has_deadline and has_form:
            return [
                OrchestrationToolName.FORMS_SEARCH,
                OrchestrationToolName.RELATIONSHIP_LOOKUP,
                OrchestrationToolName.DEADLINE_QUERY,
                OrchestrationToolName.SEMANTIC_FORMS_SEARCH,
            ]
        if has_deadline:
            return [
                OrchestrationToolName.DEADLINE_QUERY,
                OrchestrationToolName.FORMS_SEARCH,
                OrchestrationToolName.RELATIONSHIP_LOOKUP,
                OrchestrationToolName.SEMANTIC_FORMS_SEARCH,
            ]
        if any(keyword in normalized_query for keyword in calendar_keywords):
            return [
                OrchestrationToolName.CALENDAR_QUERY,
                OrchestrationToolName.FORMS_SEARCH,
                OrchestrationToolName.SEMANTIC_FORMS_SEARCH,
                OrchestrationToolName.RELATIONSHIP_LOOKUP,
            ]
        return [
            OrchestrationToolName.FORMS_SEARCH,
            OrchestrationToolName.SEMANTIC_FORMS_SEARCH,
            OrchestrationToolName.RELATIONSHIP_LOOKUP,
            OrchestrationToolName.CALENDAR_QUERY,
            OrchestrationToolName.DEADLINE_QUERY,
        ]
