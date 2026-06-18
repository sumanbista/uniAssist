"""Calendar orchestration tool adapter."""

import time
from datetime import date
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.domains.auth.models.roles import UserRole
from app.domains.calendar.schemas import CalendarEntryType
from app.domains.calendar.services import CalendarService
from app.domains.calendar.services.calendar_service import calendar_entry_to_dict
from app.domains.orchestration.schemas import (
    ExecutionStep,
    OrchestrationStatus,
    OrchestrationToolName,
    ToolExecutionResult,
)
from app.domains.orchestration.services.tool_registry import OrchestrationTool


class CalendarQueryTool(OrchestrationTool):
    """Run deterministic governed academic calendar retrieval."""

    name = OrchestrationToolName.CALENDAR_QUERY

    def __init__(self, service: CalendarService) -> None:
        self.service = service

    async def run(
        self,
        step: ExecutionStep,
        university_id: UUID,
        prior_results: list[ToolExecutionResult],
        role: UserRole = UserRole.STUDENT,
    ) -> ToolExecutionResult:
        """Execute tenant-scoped calendar retrieval."""

        started_at = time.perf_counter()
        query = _validated_query(step.params)
        limit = _bounded_limit(step.params)
        entry_type = _calendar_entry_type(step.params, query)
        if _is_upcoming_query(query):
            entries = await self.service.upcoming_entries(
                university_id=university_id,
                role=role,
                as_of=date.today(),
                limit=limit,
            )
            total = len(entries)
        else:
            entries, total = await self.service.search_entries(
                university_id=university_id,
                role=role,
                query=query,
                limit=limit,
                offset=0,
                entry_type=entry_type,
            )
            if not entries and entry_type is not None:
                entries, total = await self.service.list_entries(
                    university_id=university_id,
                    role=role,
                    limit=limit,
                    offset=0,
                    entry_type=entry_type,
                )
        data = [calendar_entry_to_dict(entry) for entry in entries]
        return ToolExecutionResult(
            step_id=step.step_id,
            tool_name=step.tool_name,
            status=OrchestrationStatus.SUCCESS,
            data=data,
            metadata={
                "result_count": len(data),
                "total": total,
                "retrieval_type": "calendar_query",
                "entry_type": entry_type.value if entry_type else None,
                "trace": {
                    "tenant_scoped": True,
                    "governance_filtered": True,
                    "source": "academic_calendar_entries",
                },
            },
            latency_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
            confidence_score=1.0 if data else 0.0,
        )


def _validated_query(params: dict[str, Any]) -> str:
    """Return a sanitized query value from step params."""

    query = params.get("query")
    if not isinstance(query, str):
        raise ValueError("query parameter is required")
    normalized_query = " ".join(query.strip().split())
    if not normalized_query:
        raise ValueError("query parameter is required")
    return normalized_query


def _bounded_limit(params: dict[str, Any]) -> int:
    """Return a bounded positive result limit."""

    raw_limit = params.get("limit", settings.ORCHESTRATION_RESULT_LIMIT)
    if not isinstance(raw_limit, int):
        raise ValueError("limit must be an integer")
    return min(max(raw_limit, 1), settings.ORCHESTRATION_RESULT_LIMIT)


def _calendar_entry_type(
    params: dict[str, Any],
    query: str,
) -> CalendarEntryType | None:
    """Infer or validate a calendar entry type from params and query text."""

    raw_entry_type = params.get("entry_type")
    if isinstance(raw_entry_type, str) and raw_entry_type.strip():
        return CalendarEntryType(raw_entry_type.strip())
    normalized_query = query.casefold()
    keyword_map = {
        CalendarEntryType.HOLIDAY: ("holiday",),
        CalendarEntryType.BREAK: ("break", "spring break", "winter break"),
        CalendarEntryType.FINALS_WEEK: ("final", "finals"),
        CalendarEntryType.REGISTRATION_PERIOD: ("registration", "register"),
        CalendarEntryType.SEMESTER_START: ("semester start", "term start"),
        CalendarEntryType.SEMESTER_END: ("semester end", "term end"),
    }
    for entry_type, keywords in keyword_map.items():
        if any(keyword in normalized_query for keyword in keywords):
            return entry_type
    return None


def _is_upcoming_query(query: str) -> bool:
    """Return whether a query asks for upcoming calendar entries."""

    normalized_query = query.casefold()
    return "upcoming" in normalized_query or "next" in normalized_query
