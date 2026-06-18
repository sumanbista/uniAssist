"""Service tests for Forms and Deadlines relationship links."""

from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.deadlines.schemas import DeadlineCreate
from app.domains.deadlines.services.deadline_service import InvalidRelatedFormError
from app.domains.relationships.enums import ProvenanceType, RelationshipType
from app.tests.deadline_helpers import InMemoryEventStore, deadline_record
from app.tests.forms_deadlines_helpers import build_deadline_service
from app.tests.relationship_traversal_fakes import form


@pytest.mark.anyio
async def test_valid_related_form_auto_creates_relationship() -> None:
    """Valid related_form_id should create one admin-verified deadline_for edge."""

    university_id = uuid4()
    form_id = uuid4()
    store = InMemoryEventStore()
    service, relationship_repo = build_deadline_service(
        {form_id: form(form_id, university_id, status="verified")},
        store=store,
    )

    created = await service.create_deadline(
        DeadlineCreate(
            title="Withdrawal Deadline",
            deadline_type="withdrawal",
            due_date=date.today(),
            related_form_id=form_id,
        ),
        university_id=university_id,
        actor_id=uuid4(),
        event_context=SimpleNamespace(actor_id=uuid4(), correlation_id=uuid4()),
    )

    assert created.related_form_id == form_id
    assert len(relationship_repo.relationships) == 1
    relationship = relationship_repo.relationships[0]
    assert relationship.source_entity_type == "form"
    assert relationship.target_entity_type == "deadline"
    assert relationship.relationship_type == RelationshipType.DEADLINE_FOR.value
    assert relationship.provenance_type == ProvenanceType.ADMIN_VERIFIED.value
    assert relationship.confidence_score == 1.0
    assert "relationship.created" in [event.event_type for event in store.events]


@pytest.mark.anyio
async def test_cross_tenant_or_blocked_related_form_rejected() -> None:
    """Cross-tenant and rejected form references should fail closed."""

    university_id = uuid4()
    cross_tenant_form_id = uuid4()
    rejected_form_id = uuid4()
    service, _relationship_repo = build_deadline_service(
        {
            cross_tenant_form_id: form(cross_tenant_form_id, uuid4()),
            rejected_form_id: form(
                rejected_form_id,
                university_id,
                status="rejected",
                verification_status="rejected",
            ),
        },
    )

    for form_id in (cross_tenant_form_id, rejected_form_id):
        with pytest.raises(InvalidRelatedFormError):
            await service.create_deadline(
                DeadlineCreate(
                    title="Unsafe Deadline",
                    due_date=date.today(),
                    related_form_id=form_id,
                ),
                university_id=university_id,
                actor_id=uuid4(),
                event_context=SimpleNamespace(actor_id=uuid4(), correlation_id=uuid4()),
            )


@pytest.mark.anyio
async def test_duplicate_relationship_not_created() -> None:
    """Creating the same deadline link twice should not duplicate the edge."""

    university_id = uuid4()
    form_id = uuid4()
    service, relationship_repo = build_deadline_service(
        {form_id: form(form_id, university_id, status="published")},
    )
    deadline = deadline_record(university_id=university_id, related_form_id=form_id)
    context = SimpleNamespace(actor_id=uuid4(), correlation_id=uuid4())

    await service.relationships.upsert_deadline_relationship(deadline, university_id, context)
    await service.relationships.upsert_deadline_relationship(deadline, university_id, context)

    assert len(relationship_repo.relationships) == 1
