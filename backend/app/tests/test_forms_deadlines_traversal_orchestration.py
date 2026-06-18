"""Traversal and orchestration tests for Forms and Deadlines relationships."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.orchestration.schemas import (
    OrchestrationStatus,
    OrchestrationToolName,
)
from app.domains.orchestration.services import (
    DeadlineQueryTool,
    FormsSearchTool,
    RelationshipLookupTool,
    RetrievalOrchestrator,
    RetrievalPlanner,
    ToolRegistry,
)
from app.domains.relationships.traversal import (
    RelationshipTraversalService,
    TraversalNode,
    TraversalRequest,
    TraversalResult,
    TraversalStatus,
    TraversalTrace,
)
from app.tests.deadline_helpers import FakeDeadlineRepository, deadline_record
from app.tests.relationship_traversal_fakes import FakeFormsRepository, form


class AsyncRelationshipService:
    """Async relationship service fake for traversal tests."""

    def __init__(self, relationships) -> None:
        self.relationships = relationships

    async def retrieve_related_entities(self, entity_type, entity_id):
        return self.relationships


@pytest.mark.anyio
async def test_traversal_supports_form_to_deadline() -> None:
    """Bounded traversal should traverse form to visible deadline nodes."""

    university_id = uuid4()
    form_id = uuid4()
    deadline_id = uuid4()
    relationship = SimpleNamespace(
        id=uuid4(),
        source_entity_type="form",
        source_entity_id=form_id,
        target_entity_type="deadline",
        target_entity_id=deadline_id,
        relationship_type="deadline_for",
        confidence_score=1.0,
        provenance_type="admin_verified",
        metadata_={},
    )
    traversal = RelationshipTraversalService(
        relationships_service=AsyncRelationshipService([relationship]),
        forms_repository=FakeFormsRepository({form_id: form(form_id, university_id)}),
        deadlines_repository=FakeDeadlineRepository(
            [deadline_record(id=deadline_id, university_id=university_id)]
        ),
    )

    result = await traversal.traverse_related_entities(
        request=TraversalRequest(entity_id=form_id, entity_type="form"),
        university_id=university_id,
    )

    assert result.related_entities[0].entity_type == "deadline"
    assert result.related_entities[0].entity_id == deadline_id


@pytest.mark.anyio
async def test_orchestrator_returns_related_deadline_context() -> None:
    """Mixed queries should execute forms, relationship, and deadline tools."""

    university_id = uuid4()
    form_id = uuid4()
    deadline = deadline_record(university_id=university_id, title="Withdrawal Deadline")
    registry = ToolRegistry()
    registry.register(FormsSearchTool(FakeFormsRetrieval(form_id)))
    registry.register(
        RelationshipLookupTool(
            service=AsyncRelationshipService([]),
            traversal_service=FakeTraversal(deadline.id),
        )
    )
    registry.register(DeadlineQueryTool(FakeDeadlineService(deadline)))
    orchestrator = RetrievalOrchestrator(
        planner=RetrievalPlanner(
            allowed_tools=["forms_search", "relationship_lookup", "deadline_query"],
            max_steps=3,
            timeout_seconds=1.0,
            result_limit=5,
        ),
        tool_registry=registry,
    )

    response = await orchestrator.execute_query(
        query="withdrawal form deadline",
        university_id=university_id,
    )

    assert response.trace.execution_order == [
        OrchestrationToolName.FORMS_SEARCH,
        OrchestrationToolName.RELATIONSHIP_LOOKUP,
        OrchestrationToolName.DEADLINE_QUERY,
    ]
    assert response.trace.status == OrchestrationStatus.SUCCESS
    assert response.results["deadline_query"][0]["title"] == "Withdrawal Deadline"


class FakeFormsRetrieval:
    """Forms retrieval fake for orchestration."""

    def __init__(self, form_id) -> None:
        self.form_id = form_id

    async def retrieve_forms(self, query, university_id, limit):
        return [
            SimpleNamespace(
                id=self.form_id,
                university_id=university_id,
                title="Withdrawal Form",
                description="Withdraw from a course",
                category="registrar",
                source_url=None,
                verification_status="verified",
                verification_score=None,
                last_verified_at=None,
                next_review_at=None,
                expires_at=None,
                staleness_score=None,
                status="verified",
                metadata={},
                ranking_score=0.9,
                ranking_signals={"test": 0.9},
                similarity_score=None,
            )
        ]


class FakeTraversal:
    """Traversal fake returning a related deadline node."""

    def __init__(self, deadline_id) -> None:
        self.deadline_id = deadline_id

    async def traverse_related_entities(self, request, university_id):
        node = TraversalNode(
            entity_id=self.deadline_id,
            entity_type="deadline",
            depth=1,
            traversal_score=1.0,
        )
        return TraversalResult(
            related_entities=[node],
            trace=TraversalTrace(
                root_entity_id=request.entity_id,
                root_entity_type=request.entity_type,
                visited_nodes=[],
                traversed_edges=[],
                traversal_depth=1,
                latency_ms=1,
                status=TraversalStatus.SUCCESS,
            ),
        )


class FakeDeadlineService:
    """Deadline service fake returning traversal-discovered deadline."""

    def __init__(self, deadline) -> None:
        self.deadline = deadline

    async def search_deadlines(self, **kwargs):
        return [], 0

    async def list_deadlines(self, **kwargs):
        return [], 0

    async def retrieve_deadline(self, **kwargs):
        return self.deadline
