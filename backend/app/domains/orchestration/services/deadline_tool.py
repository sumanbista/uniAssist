"""Deadline orchestration tool adapter."""

import time
from datetime import date
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.domains.auth.models.roles import UserRole
from app.domains.deadlines.schemas import DeadlineType
from app.domains.deadlines.services import DeadlineService
from app.domains.deadlines.services.deadline_service import deadline_to_dict
from app.domains.orchestration.schemas import (
    ExecutionStep,
    OrchestrationStatus,
    OrchestrationToolName,
    ToolExecutionResult,
)
from app.domains.orchestration.services.tool_registry import OrchestrationTool


class DeadlineQueryTool(OrchestrationTool):
    """Run deterministic governed deadline retrieval."""

    name = OrchestrationToolName.DEADLINE_QUERY

    def __init__(self, service: DeadlineService) -> None:
        self.service = service

    async def run(
        self,
        step: ExecutionStep,
        university_id: UUID,
        prior_results: list[ToolExecutionResult],
        role: UserRole = UserRole.STUDENT,
    ) -> ToolExecutionResult:
        """Execute tenant-scoped deadline retrieval."""

        started_at = time.perf_counter()
        query = _validated_query(step.params)
        limit = _bounded_limit(step.params)
        deadline_type = _deadline_type(step.params, query)
        if _is_upcoming_query(query):
            deadlines = await self.service.upcoming_deadlines(
                university_id=university_id,
                role=role,
                as_of=date.today(),
                limit=limit,
            )
            total = len(deadlines)
        else:
            deadlines, total = await self.service.search_deadlines(
                university_id=university_id,
                role=role,
                query=query,
                limit=limit,
                offset=0,
                deadline_type=deadline_type,
            )
            if not deadlines and deadline_type is not None:
                deadlines, total = await self.service.list_deadlines(
                    university_id=university_id,
                    role=role,
                    limit=limit,
                    offset=0,
                    deadline_type=deadline_type,
                )
        related_deadlines = await self._prior_related_deadlines(
            university_id=university_id,
            role=role,
            prior_results=prior_results,
        )
        existing_ids = {deadline.id for deadline in deadlines}
        for deadline in related_deadlines:
            if deadline.id in existing_ids:
                continue
            deadlines.append(deadline)
            existing_ids.add(deadline.id)
        total = max(total, len(deadlines))
        data = [deadline_to_dict(deadline) for deadline in deadlines]
        return ToolExecutionResult(
            step_id=step.step_id,
            tool_name=step.tool_name,
            status=OrchestrationStatus.SUCCESS,
            data=data,
            metadata={
                "result_count": len(data),
                "total": total,
                "retrieval_type": "deadline_query",
                "deadline_type": deadline_type.value if deadline_type else None,
                "trace": {
                    "tenant_scoped": True,
                    "governance_filtered": True,
                    "source": "deadlines",
                },
            },
            latency_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
            confidence_score=1.0 if data else 0.0,
        )

    async def _prior_related_deadlines(
        self,
        university_id: UUID,
        role: UserRole,
        prior_results: list[ToolExecutionResult],
    ) -> list[Any]:
        """Fetch visible deadline nodes discovered by earlier traversal steps."""

        deadlines = []
        seen: set[UUID] = set()
        for result in prior_results:
            for item in result.data:
                if item.get("entity_type") != "deadline":
                    continue
                raw_id = item.get("entity_id")
                if raw_id is None:
                    continue
                deadline_id = UUID(str(raw_id))
                if deadline_id in seen:
                    continue
                deadline = await self.service.retrieve_deadline(
                    university_id=university_id,
                    deadline_id=deadline_id,
                    role=role,
                )
                if deadline is None:
                    continue
                seen.add(deadline_id)
                deadlines.append(deadline)
        return deadlines


def _validated_query(params: dict[str, Any]) -> str:
    """Return a sanitized query value from step params."""

    query = params.get("query")
    if not isinstance(query, str):
        raise ValueError("query parameter is required")
    normalized_query = " ".join(query.strip().split())
    if not normalized_query:
        raise ValueError("query parameter is required")
    if any(ord(character) < 32 for character in normalized_query):
        raise ValueError("query contains unsupported control characters")
    return normalized_query


def _bounded_limit(params: dict[str, Any]) -> int:
    """Return a bounded positive result limit."""

    raw_limit = params.get("limit", settings.ORCHESTRATION_RESULT_LIMIT)
    if not isinstance(raw_limit, int):
        raise ValueError("limit must be an integer")
    return min(max(raw_limit, 1), settings.ORCHESTRATION_RESULT_LIMIT)


def _deadline_type(params: dict[str, Any], query: str) -> DeadlineType | None:
    """Infer or validate a deadline type from params and query text."""

    raw_deadline_type = params.get("deadline_type")
    if isinstance(raw_deadline_type, str) and raw_deadline_type.strip():
        return DeadlineType(raw_deadline_type.strip())
    normalized_query = query.casefold()
    keyword_map = {
        DeadlineType.ADD_DROP: ("add/drop", "add drop", "drop class"),
        DeadlineType.WITHDRAWAL: ("withdraw", "withdrawal"),
        DeadlineType.GRADUATION_APPLICATION: ("graduation", "graduate"),
        DeadlineType.TUITION_DUE: ("tuition", "payment"),
        DeadlineType.REGISTRATION: ("registration", "register"),
        DeadlineType.HOUSING: ("housing",),
        DeadlineType.FINANCIAL_AID: ("financial aid", "fafsa", "aid"),
    }
    for deadline_type, keywords in keyword_map.items():
        if any(keyword in normalized_query for keyword in keywords):
            return deadline_type
    return None


def _is_upcoming_query(query: str) -> bool:
    """Return whether a query asks for upcoming deadlines."""

    normalized_query = query.casefold()
    return "upcoming" in normalized_query or "next" in normalized_query
