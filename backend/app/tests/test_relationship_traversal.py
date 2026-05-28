"""Tests for bounded relationship traversal foundations."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.domains.orchestration.schemas import (
    ExecutionStep,
    OrchestrationToolName,
    ToolExecutionResult,
)
from app.domains.orchestration.services.tools import RelationshipLookupTool
from app.domains.relationships.api.relationships import get_relationship_traversal_service
from app.domains.relationships.enums import RelationshipType
from app.domains.relationships.traversal import (
    RelationshipTraversalService,
    TraversalRequest,
    TraversalStatus,
)
from app.main import app
from app.tests.relationship_traversal_fakes import (
    FakeFormsRepository,
    FakeRelationshipsService,
    FakeTraversalService,
    SlowRelationshipsService,
    form,
    relationship,
    traversal_service,
)


@pytest.mark.anyio
async def test_traversal_is_bounded_breadth_first_and_weighted() -> None:
    """Traversal should honor depth, node limits, and deterministic weighting."""

    university_id = uuid4()
    root_id = uuid4()
    high_priority_id = uuid4()
    low_priority_id = uuid4()
    service = traversal_service(
        university_id=university_id,
        root_id=root_id,
        relationships=[
            relationship(root_id, low_priority_id, RelationshipType.REFERENCES, 1.0),
            relationship(root_id, high_priority_id, RelationshipType.REQUIRES, 0.8),
        ],
    )

    result = await service.traverse_related_entities(
        request=TraversalRequest(entity_id=root_id, entity_type="form", max_nodes=2),
        university_id=university_id,
    )

    assert result.trace.status == TraversalStatus.PARTIAL
    assert [node.entity_id for node in result.related_entities] == [high_priority_id]
    assert result.trace.traversed_edges[0].relationship_type == RelationshipType.REQUIRES
    assert result.trace.traversed_edges[0].traversal_score == 0.8


@pytest.mark.anyio
async def test_traversal_prevents_cycles() -> None:
    """Traversal should not revisit nodes in cyclic relationship data."""

    university_id = uuid4()
    root_id = uuid4()
    child_id = uuid4()
    service = traversal_service(
        university_id=university_id,
        root_id=root_id,
        extra_form_ids=[child_id],
        relationships=[
            relationship(root_id, child_id, RelationshipType.REQUIRES),
            relationship(child_id, root_id, RelationshipType.RELATED_TO),
        ],
    )

    result = await service.traverse_related_entities(
        request=TraversalRequest(entity_id=root_id, entity_type="form", max_hops=2),
        university_id=university_id,
    )

    assert result.metadata["node_count"] == 2
    assert [node.entity_id for node in result.trace.visited_nodes].count(root_id) == 1


@pytest.mark.anyio
async def test_traversal_filters_cross_tenant_or_rejected_forms() -> None:
    """Traversal should not include form nodes outside tenant or governance policy."""

    university_id = uuid4()
    other_university_id = uuid4()
    root_id = uuid4()
    cross_tenant_id = uuid4()
    rejected_id = uuid4()
    service = RelationshipTraversalService(
        relationships_service=FakeRelationshipsService(
            [
                relationship(root_id, cross_tenant_id),
                relationship(root_id, rejected_id),
            ]
        ),
        forms_repository=FakeFormsRepository(
            {
                root_id: form(root_id, university_id),
                cross_tenant_id: form(cross_tenant_id, other_university_id),
                rejected_id: form(
                    rejected_id,
                    university_id,
                    verification_status="rejected",
                ),
            }
        ),
    )

    result = await service.traverse_related_entities(
        request=TraversalRequest(entity_id=root_id, entity_type="form"),
        university_id=university_id,
    )

    assert result.related_entities == []
    assert result.trace.traversed_edges == []


@pytest.mark.anyio
async def test_traversal_timeout_returns_partial_trace() -> None:
    """Traversal should stop safely when relationship lookup exceeds its budget."""

    university_id = uuid4()
    root_id = uuid4()
    service = RelationshipTraversalService(
        relationships_service=SlowRelationshipsService(),
        forms_repository=FakeFormsRepository({root_id: form(root_id, university_id)}),
    )

    result = await service.traverse_related_entities(
        request=TraversalRequest(
            entity_id=root_id,
            entity_type="form",
            traversal_timeout_ms=1,
        ),
        university_id=university_id,
    )

    assert result.trace.status == TraversalStatus.PARTIAL
    assert result.metadata["node_count"] == 1


def test_relationship_traverse_endpoint_contract() -> None:
    """Traversal endpoint should expose related entities, trace, and metadata."""

    university_id = uuid4()
    root_id = uuid4()
    target_id = uuid4()

    def override_service() -> RelationshipTraversalService:
        return traversal_service(
            university_id=university_id,
            root_id=root_id,
            extra_form_ids=[target_id],
            relationships=[
                relationship(root_id, target_id, RelationshipType.DEADLINE_FOR)
            ],
        )

    app.dependency_overrides[get_relationship_traversal_service] = override_service
    client = TestClient(app)
    response = client.post(
        "/relationships/traverse",
        headers={"X-University-ID": str(university_id)},
        json={"entity_id": str(root_id), "entity_type": "form"},
    )
    app.dependency_overrides.clear()

    body = response.json()
    assert response.status_code == 200
    assert body["metadata"]["node_count"] == 2
    assert body["trace"]["traversed_edges"][0]["relationship_type"] == "deadline_for"
    assert body["related_entities"][0]["entity_id"] == str(target_id)


@pytest.mark.anyio
async def test_orchestration_relationship_tool_includes_traversal_traces() -> None:
    """Relationship orchestration step should aggregate bounded traversal traces."""

    form_id = uuid4()
    tool = RelationshipLookupTool(
        service=FakeRelationshipsService([]),
        traversal_service=FakeTraversalService(),
    )

    result = await tool.run(
        step=ExecutionStep(
            step_id=1,
            tool_name=OrchestrationToolName.RELATIONSHIP_LOOKUP,
            params={},
            timeout_seconds=1.0,
        ),
        university_id=uuid4(),
        prior_results=[
            ToolExecutionResult(
                step_id=1,
                tool_name=OrchestrationToolName.FORMS_SEARCH,
                status="success",
                data=[{"id": str(form_id)}],
                latency_ms=1,
                confidence_score=1.0,
            )
        ],
    )

    assert result.metadata["retrieval_type"] == "bounded_relationship_traversal"
    assert result.metadata["traversal_traces"]
    assert result.data[0]["entity_type"] == "form"
