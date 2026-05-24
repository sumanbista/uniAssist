"""Response serializers for Forms API routes."""

from uuid import UUID

from app.domains.forms.models import Form
from app.domains.forms.retrieval.service import RetrievedForm
from app.domains.forms.schemas import (
    FormResponse,
    FormSearchResult,
    FormVerificationResponse,
    RelatedEntitySummary,
)
from app.domains.relationships.models import EntityRelationship


def form_to_response(
    form: Form,
    related_entities: list[RelatedEntitySummary] | None = None,
) -> FormResponse:
    """Convert a Form ORM model into an API response schema."""

    return FormResponse(
        id=form.id,
        university_id=form.university_id,
        title=form.title,
        description=form.description,
        category=form.category,
        source_url=form.source_url,
        storage_path=form.storage_path,
        verification_status=form.verification_status,
        verification_score=float(form.verification_score)
        if form.verification_score is not None
        else None,
        last_verified_at=form.last_verified_at,
        verified_by=form.verified_by,
        review_notes=form.review_notes,
        expires_at=form.expires_at,
        next_review_at=form.next_review_at,
        review_count=form.review_count,
        staleness_score=float(form.staleness_score)
        if form.staleness_score is not None
        else None,
        status=form.status,
        metadata=form.metadata_,
        related_entities=related_entities or [],
        created_at=form.created_at,
        updated_at=form.updated_at,
    )


def retrieved_form_to_response(form: RetrievedForm) -> FormSearchResult:
    """Convert a retrieved form into a search response schema."""

    return FormSearchResult(
        id=form.id,
        university_id=form.university_id,
        title=form.title,
        description=form.description,
        category=form.category,
        source_url=form.source_url,
        verification_status=form.verification_status,
        verification_score=form.verification_score,
        last_verified_at=form.last_verified_at,
        next_review_at=form.next_review_at,
        expires_at=form.expires_at,
        staleness_score=form.staleness_score,
        status=form.status,
        metadata=form.metadata,
        ranking_score=form.ranking_score,
        ranking_signals=form.ranking_signals,
        similarity_score=form.similarity_score,
    )


def form_to_governance_response(form: Form) -> FormVerificationResponse:
    """Convert a Form ORM model into governance response metadata."""

    return FormVerificationResponse(
        id=form.id,
        university_id=form.university_id,
        verification_status=form.verification_status,
        verification_score=float(form.verification_score)
        if form.verification_score is not None
        else None,
        last_verified_at=form.last_verified_at,
        verified_by=form.verified_by,
        review_notes=form.review_notes,
        expires_at=form.expires_at,
        next_review_at=form.next_review_at,
        review_count=form.review_count,
        staleness_score=float(form.staleness_score)
        if form.staleness_score is not None
        else None,
        status=form.status,
    )


def relationship_to_related_summary(
    relationship: EntityRelationship,
    form_id: UUID,
) -> RelatedEntitySummary:
    """Convert a one-hop relationship into a Forms related entity summary."""

    if (
        relationship.source_entity_id == form_id
        and relationship.source_entity_type == "form"
    ):
        entity_type = relationship.target_entity_type
        entity_id = relationship.target_entity_id
    else:
        entity_type = relationship.source_entity_type
        entity_id = relationship.source_entity_id
    return RelatedEntitySummary(
        entity_type=entity_type,
        entity_id=entity_id,
        relationship_type=relationship.relationship_type,
        confidence_score=float(relationship.confidence_score)
        if relationship.confidence_score is not None
        else None,
        provenance_type=relationship.provenance_type,
        metadata=relationship.metadata_,
    )
