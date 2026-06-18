"""Bounded breadth-first relationship traversal service."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.domains.deadlines.repositories import DeadlineRepository
from app.domains.forms.repositories import FormsRepository
from app.domains.relationships.enums import RelationshipType
from app.domains.relationships.services import RelationshipsService
from app.domains.relationships.traversal.scoring import (
    RELATIONSHIP_WEIGHTS,
    ordered_relationships,
    other_endpoint,
    relationship_type_or_none,
    to_traversal_edge,
)
from app.domains.relationships.traversal.schemas import (
    TraversalNode,
    TraversalRequest,
    TraversalResult,
    TraversalStatus,
    TraversalTrace,
)

logger = get_logger(__name__)

@dataclass(frozen=True)
class _QueueItem:
    """Internal queue item for iterative traversal."""

    entity_type: str
    entity_id: UUID
    depth: int
    traversal_score: float


class RelationshipTraversalService:
    """Coordinate bounded deterministic relationship graph expansion."""

    def __init__(
        self,
        relationships_service: RelationshipsService,
        forms_repository: FormsRepository,
        deadlines_repository: DeadlineRepository | None = None,
    ) -> None:
        self.relationships_service = relationships_service
        self.forms_repository = forms_repository
        self.deadlines_repository = deadlines_repository

    async def traverse_related_entities(
        self,
        request: TraversalRequest,
        university_id: UUID,
    ) -> TraversalResult:
        """Traverse related entities using bounded breadth-first expansion."""

        started_at = time.perf_counter()
        max_hops = min(request.max_hops, settings.TRAVERSAL_MAX_HOPS)
        max_nodes = min(request.max_nodes, settings.TRAVERSAL_MAX_NODES)
        timeout_ms = min(request.traversal_timeout_ms, settings.TRAVERSAL_TIMEOUT_MS)
        allowed_types = _allowed_relationship_types(request)
        root_key = (request.entity_type, request.entity_id)
        visited_keys: set[tuple[str, UUID]] = set()
        queued_keys: set[tuple[str, UUID]] = {root_key}
        visited_nodes: list[TraversalNode] = []
        traversed_edges: list[TraversalEdge] = []
        queue: deque[_QueueItem] = deque(
            [
                _QueueItem(
                    entity_type=request.entity_type,
                    entity_id=request.entity_id,
                    depth=0,
                    traversal_score=1.0,
                )
            ]
        )
        status = TraversalStatus.SUCCESS

        logger.info(
            "relationship_traversal_started university_id=%s entity_type=%s entity_id=%s max_hops=%s max_nodes=%s",
            university_id,
            request.entity_type,
            request.entity_id,
            max_hops,
            max_nodes,
        )
        while queue and len(visited_nodes) < max_nodes:
            if _elapsed_ms(started_at) > timeout_ms:
                status = TraversalStatus.PARTIAL
                break
            current = queue.popleft()
            current_key = (current.entity_type, current.entity_id)
            queued_keys.discard(current_key)
            if current_key in visited_keys:
                continue
            if not await self._can_visit_node(current.entity_type, current.entity_id, university_id):
                continue
            visited_keys.add(current_key)
            visited_nodes.append(
                TraversalNode(
                    entity_id=current.entity_id,
                    entity_type=current.entity_type,
                    depth=current.depth,
                    traversal_score=round(current.traversal_score, 4),
                )
            )
            if current.depth >= max_hops:
                continue
            remaining_seconds = _remaining_timeout_seconds(started_at, timeout_ms)
            if remaining_seconds <= 0:
                status = TraversalStatus.PARTIAL
                break
            try:
                relationships = await asyncio.wait_for(
                    self.relationships_service.retrieve_related_entities(
                        current.entity_type,
                        current.entity_id,
                    ),
                    timeout=remaining_seconds,
                )
            except TimeoutError:
                status = TraversalStatus.PARTIAL
                break
            for relationship in ordered_relationships(relationships):
                if len(visited_nodes) + len(queue) >= max_nodes:
                    status = TraversalStatus.PARTIAL
                    break
                relationship_type = relationship_type_or_none(relationship.relationship_type)
                if relationship_type is None or relationship_type not in allowed_types:
                    continue
                next_type, next_id = other_endpoint(
                    relationship,
                    current.entity_type,
                    current.entity_id,
                )
                next_key = (next_type, next_id)
                if next_key in visited_keys or next_key in queued_keys:
                    continue
                if not await self._can_visit_node(next_type, next_id, university_id):
                    continue
                edge = to_traversal_edge(relationship, current.depth + 1)
                traversed_edges.append(edge)
                queue.append(
                    _QueueItem(
                        entity_type=next_type,
                        entity_id=next_id,
                        depth=current.depth + 1,
                        traversal_score=edge.traversal_score,
                    )
                )
                queued_keys.add(next_key)

        latency_ms = _elapsed_ms(started_at)
        trace = TraversalTrace(
            root_entity_id=request.entity_id,
            root_entity_type=request.entity_type,
            visited_nodes=visited_nodes,
            traversed_edges=traversed_edges,
            traversal_depth=max((node.depth for node in visited_nodes), default=0),
            scoring_metadata={
                "relationship_weights": {
                    relationship_type.value: weight
                    for relationship_type, weight in RELATIONSHIP_WEIGHTS.items()
                },
                "max_hops": max_hops,
                "max_nodes": max_nodes,
                "allowed_relationship_types": [
                    relationship_type.value for relationship_type in allowed_types
                ],
            },
            latency_ms=latency_ms,
            status=status,
        )
        logger.info(
            "relationship_traversal_completed university_id=%s entity_type=%s entity_id=%s status=%s nodes=%s edges=%s latency_ms=%s",
            university_id,
            request.entity_type,
            request.entity_id,
            status.value,
            len(visited_nodes),
            len(traversed_edges),
            latency_ms,
        )
        return TraversalResult(
            related_entities=[
                node for node in visited_nodes if (node.entity_type, node.entity_id) != root_key
            ],
            trace=trace,
            metadata={
                "status": status.value,
                "node_count": len(visited_nodes),
                "edge_count": len(traversed_edges),
                "latency_ms": latency_ms,
            },
        )

    async def _can_visit_node(
        self,
        entity_type: str,
        entity_id: UUID,
        university_id: UUID,
    ) -> bool:
        """Apply tenant and governance filtering for supported entities."""

        if entity_type == "deadline":
            return await self._can_visit_deadline(entity_id, university_id)
        if entity_type != "form":
            return True
        form = await self.forms_repository.get_form_by_id(
            university_id=university_id,
            form_id=entity_id,
        )
        if form is None:
            return False
        return (
            form.status not in self.forms_repository.EXCLUDED_RETRIEVAL_STATUSES
            and form.verification_status not in {"rejected", "archived"}
        )

    async def _can_visit_deadline(
        self,
        deadline_id: UUID,
        university_id: UUID,
    ) -> bool:
        """Apply tenant and governance filtering for deadline nodes."""

        if self.deadlines_repository is None:
            return True
        deadline = await self.deadlines_repository.get_deadline_by_id(
            university_id=university_id,
            deadline_id=deadline_id,
            visible_statuses=("pending_review", "stale", "verified", "published"),
            visible_verification_statuses=(
                "pending_review",
                "stale",
                "verified",
                "published",
            ),
        )
        return deadline is not None


def _allowed_relationship_types(
    request: TraversalRequest,
) -> list[RelationshipType]:
    """Resolve request relationship allowlist against global config."""

    configured_types = [
        RelationshipType(value)
        for value in settings.TRAVERSAL_ALLOWED_RELATIONSHIP_TYPES
    ]
    requested_types = request.allowed_relationship_types or configured_types
    return [
        relationship_type
        for relationship_type in requested_types
        if relationship_type in configured_types
    ]


def _elapsed_ms(started_at: float) -> int:
    """Return elapsed wall-clock time in milliseconds."""

    return max(0, round((time.perf_counter() - started_at) * 1000))


def _remaining_timeout_seconds(started_at: float, timeout_ms: int) -> float:
    """Return the remaining traversal budget in seconds."""

    return max(0.0, (timeout_ms - _elapsed_ms(started_at)) / 1000)
