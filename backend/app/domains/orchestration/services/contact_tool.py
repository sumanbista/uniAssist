"""Contacts orchestration tool adapter."""

import time
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.domains.auth.models.roles import UserRole
from app.domains.contacts.services import ContactsService, contact_to_dict
from app.domains.orchestration.schemas import (
    ExecutionStep,
    OrchestrationStatus,
    OrchestrationToolName,
    ToolExecutionResult,
)
from app.domains.orchestration.services.tool_registry import OrchestrationTool


class ContactLookupTool(OrchestrationTool):
    """Run deterministic governed Contacts retrieval."""

    name = OrchestrationToolName.CONTACT_LOOKUP

    def __init__(self, service: ContactsService) -> None:
        self.service = service

    async def run(
        self,
        step: ExecutionStep,
        university_id: UUID,
        prior_results: list[ToolExecutionResult],
        role: UserRole = UserRole.STUDENT,
    ) -> ToolExecutionResult:
        """Execute tenant-scoped contact lookup."""

        started_at = time.perf_counter()
        query = _validated_query(step.params)
        limit = _bounded_limit(step.params)
        contacts, total = await self._lookup_contacts(
            query=query,
            university_id=university_id,
            role=role,
            limit=limit,
        )
        data = [contact_to_dict(contact) for contact in contacts]
        return ToolExecutionResult(
            step_id=step.step_id,
            tool_name=step.tool_name,
            status=OrchestrationStatus.SUCCESS,
            data=data,
            metadata={
                "result_count": len(data),
                "total": total,
                "retrieval_type": "contact_lookup",
                "trace": {
                    "query": query,
                    "university_id": str(university_id),
                    "role": role.value,
                },
            },
            latency_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
            confidence_score=_confidence(data),
        )

    async def _lookup_contacts(
        self,
        query: str,
        university_id: UUID,
        role: UserRole,
        limit: int,
    ) -> tuple[list[Any], int]:
        """Run deterministic query fallbacks for natural-language contact lookups."""

        seen_ids: set[str] = set()
        merged_contacts: list[Any] = []
        total = 0
        for candidate_query in _candidate_queries(query):
            contacts, candidate_total = await self.service.search_contacts(
                university_id=university_id,
                role=role,
                query=candidate_query,
                limit=limit,
                offset=0,
            )
            total += candidate_total
            for contact in contacts:
                contact_id = str(contact.id)
                if contact_id in seen_ids:
                    continue
                seen_ids.add(contact_id)
                merged_contacts.append(contact)
                if len(merged_contacts) >= limit:
                    return merged_contacts, total
        return merged_contacts, total


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


def _confidence(results: list[dict[str, Any]]) -> float:
    """Assign deterministic confidence for exact structured retrieval."""

    if not results:
        return 0.0
    return 0.9


def _candidate_queries(query: str) -> list[str]:
    """Build deterministic contact search candidates from a user question."""

    normalized_query = " ".join(query.strip().split())
    stripped_query = "".join(
        character if character.isalnum() or character.isspace() else " "
        for character in normalized_query.casefold()
    )
    stop_words = {
        "contact",
        "email",
        "is",
        "me",
        "number",
        "of",
        "phone",
        "the",
        "who",
    }
    tokens = [
        token
        for token in stripped_query.split()
        if token and token not in stop_words
    ]
    candidates = [normalized_query]
    if tokens:
        candidates.append(" ".join(tokens))
        candidates.extend(tokens)

    deduped_candidates: list[str] = []
    seen_candidates: set[str] = set()
    for candidate in candidates:
        normalized_candidate = " ".join(candidate.strip().split())
        if not normalized_candidate or normalized_candidate in seen_candidates:
            continue
        seen_candidates.add(normalized_candidate)
        deduped_candidates.append(normalized_candidate)
    return deduped_candidates
