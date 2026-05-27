"""Explicit orchestration tool adapters."""

import time
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.domains.forms.api.serializers import retrieved_form_to_response
from app.domains.forms.retrieval import FormsRetrievalService
from app.domains.orchestration.schemas import (
    ExecutionStep,
    OrchestrationStatus,
    OrchestrationToolName,
    ToolExecutionResult,
)
from app.domains.orchestration.services.tool_registry import OrchestrationTool
from app.domains.relationships.services import RelationshipsService


class FormsSearchTool(OrchestrationTool):
    """Run deterministic full-text Forms retrieval."""

    name = OrchestrationToolName.FORMS_SEARCH

    def __init__(self, service: FormsRetrievalService) -> None:
        self.service = service

    async def run(
        self,
        step: ExecutionStep,
        university_id: UUID,
        prior_results: list[ToolExecutionResult],
    ) -> ToolExecutionResult:
        """Execute tenant-scoped FTS retrieval."""

        started_at = time.perf_counter()
        query = _validated_query(step.params)
        limit = _bounded_limit(step.params)
        forms = await self.service.retrieve_forms(
            query=query,
            university_id=university_id,
            limit=limit,
        )
        data = [
            retrieved_form_to_response(form).model_dump(mode="json")
            for form in forms
        ]
        return _success_result(
            step=step,
            started_at=started_at,
            data=data,
            confidence_score=_average_score(data),
            metadata={"result_count": len(data), "retrieval_type": "full_text"},
        )


class SemanticFormsSearchTool(OrchestrationTool):
    """Run deterministic semantic Forms retrieval."""

    name = OrchestrationToolName.SEMANTIC_FORMS_SEARCH

    def __init__(self, service: FormsRetrievalService) -> None:
        self.service = service

    async def run(
        self,
        step: ExecutionStep,
        university_id: UUID,
        prior_results: list[ToolExecutionResult],
    ) -> ToolExecutionResult:
        """Execute tenant-scoped semantic retrieval."""

        started_at = time.perf_counter()
        query = _validated_query(step.params)
        limit = _bounded_limit(step.params)
        forms = await self.service.retrieve_semantic_forms(
            query=query,
            university_id=university_id,
            limit=limit,
        )
        data = [
            retrieved_form_to_response(form).model_dump(mode="json")
            for form in forms
        ]
        return _success_result(
            step=step,
            started_at=started_at,
            data=data,
            confidence_score=_average_score(data),
            metadata={"result_count": len(data), "retrieval_type": "semantic"},
        )


class RelationshipLookupTool(OrchestrationTool):
    """Run bounded one-hop relationship lookup for retrieved forms."""

    name = OrchestrationToolName.RELATIONSHIP_LOOKUP

    def __init__(self, service: RelationshipsService) -> None:
        self.service = service

    async def run(
        self,
        step: ExecutionStep,
        university_id: UUID,
        prior_results: list[ToolExecutionResult],
    ) -> ToolExecutionResult:
        """Execute one-hop lookups for prior form results."""

        started_at = time.perf_counter()
        form_ids = _prior_form_ids(prior_results)
        relationship_rows: list[dict[str, Any]] = []
        for form_id in form_ids[: settings.ORCHESTRATION_RELATIONSHIP_LOOKUP_LIMIT]:
            relationships = await self.service.retrieve_related_entities(
                entity_type="form",
                entity_id=form_id,
            )
            relationship_rows.extend(
                {
                    "source_entity_type": relationship.source_entity_type,
                    "source_entity_id": str(relationship.source_entity_id),
                    "target_entity_type": relationship.target_entity_type,
                    "target_entity_id": str(relationship.target_entity_id),
                    "relationship_type": relationship.relationship_type,
                    "confidence_score": float(relationship.confidence_score)
                    if relationship.confidence_score is not None
                    else None,
                    "provenance_type": relationship.provenance_type,
                    "metadata": relationship.metadata_,
                }
                for relationship in relationships
            )
        return _success_result(
            step=step,
            started_at=started_at,
            data=relationship_rows,
            confidence_score=_average_relationship_confidence(relationship_rows),
            metadata={
                "result_count": len(relationship_rows),
                "retrieval_type": "relationship_lookup",
                "looked_up_entities": len(form_ids),
            },
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


def _success_result(
    step: ExecutionStep,
    started_at: float,
    data: list[dict[str, Any]],
    confidence_score: float,
    metadata: dict[str, Any],
) -> ToolExecutionResult:
    """Build a successful tool result with latency metadata."""

    return ToolExecutionResult(
        step_id=step.step_id,
        tool_name=step.tool_name,
        status=OrchestrationStatus.SUCCESS,
        data=data,
        metadata=metadata,
        latency_ms=max(0, round((time.perf_counter() - started_at) * 1000)),
        confidence_score=round(confidence_score, 4),
    )


def _average_score(results: list[dict[str, Any]]) -> float:
    """Calculate a deterministic confidence score from ranking scores."""

    if not results:
        return 0.0
    scores = [
        result.get("ranking_score", 0.0)
        for result in results
        if isinstance(result.get("ranking_score"), (int, float))
    ]
    if not scores:
        return 0.0
    return min(1.0, max(0.0, sum(scores) / len(scores)))


def _average_relationship_confidence(results: list[dict[str, Any]]) -> float:
    """Calculate relationship confidence from explicit relationship scores."""

    scores = [
        result.get("confidence_score", 0.0)
        for result in results
        if isinstance(result.get("confidence_score"), (int, float))
    ]
    if not scores:
        return 0.0
    return min(1.0, max(0.0, sum(scores) / len(scores)))


def _prior_form_ids(prior_results: list[ToolExecutionResult]) -> list[UUID]:
    """Extract unique prior form IDs in replay-safe order."""

    form_ids: list[UUID] = []
    seen: set[UUID] = set()
    for result in prior_results:
        for item in result.data:
            raw_id = item.get("id")
            if raw_id is None:
                continue
            form_id = UUID(str(raw_id))
            if form_id in seen:
                continue
            seen.add(form_id)
            form_ids.append(form_id)
    return form_ids
