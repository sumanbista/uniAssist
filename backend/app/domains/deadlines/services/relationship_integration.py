"""Forms and Deadlines relationship integration helpers."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from app.core.logging import get_logger
from app.domains.auth.models.roles import UserRole
from app.domains.deadlines.models import Deadline
from app.domains.deadlines.schemas import RelatedFormSummary
from app.domains.forms.repositories import FormsRepository
from app.domains.forms.schemas import RelatedDeadlineSummary
from app.domains.relationships.enums import ProvenanceType, RelationshipType
from app.domains.relationships.schemas import RelationshipCreate
from app.domains.relationships.services import RelationshipsService
from app.shared.events import EventContext

logger = get_logger(__name__)
BLOCKED_FORM_STATUSES = frozenset({"archived", "rejected", "deprecated"})
DeadlineFetcher = Callable[[UUID, UUID, UserRole], Awaitable[Deadline | None]]


class InvalidRelatedFormError(ValueError):
    """Raised when a deadline attempts to link an invalid form."""


class DeadlineRelationshipIntegration:
    """Coordinate safe form-deadline validation, summaries, and edge creation."""

    def __init__(
        self,
        forms_repository: FormsRepository | None,
        relationships_service: RelationshipsService | None,
        fetch_deadline: DeadlineFetcher,
    ) -> None:
        self.forms_repository = forms_repository
        self.relationships_service = relationships_service
        self.fetch_deadline = fetch_deadline

    async def validate_related_form(self, university_id: UUID, form_id: UUID) -> None:
        """Validate that a related form is tenant-local and linkable."""

        if self.forms_repository is None:
            raise InvalidRelatedFormError("Related form validation is unavailable")
        form = await self.forms_repository.get_form_by_id(
            university_id=university_id,
            form_id=form_id,
            include_inactive=True,
        )
        if form is None:
            logger.warning(
                "deadline_related_form_rejected reason=not_found_or_cross_tenant university_id=%s form_id=%s",
                university_id,
                form_id,
            )
            raise InvalidRelatedFormError("Related form is not available")
        if _is_blocked_form(form.status, form.verification_status):
            logger.warning(
                "deadline_related_form_rejected reason=blocked_status university_id=%s form_id=%s status=%s verification_status=%s",
                university_id,
                form_id,
                form.status,
                form.verification_status,
            )
            raise InvalidRelatedFormError("Related form cannot be linked")

    async def upsert_deadline_relationship(
        self,
        deadline: Deadline,
        university_id: UUID,
        event_context: EventContext,
    ) -> None:
        """Create a deadline_for relationship once when a related form exists."""

        if self.relationships_service is None or deadline.related_form_id is None:
            return
        created = await self.relationships_service.upsert_relationship(
            relationship_data=RelationshipCreate(
                source_entity_type="form",
                source_entity_id=deadline.related_form_id,
                target_entity_type="deadline",
                target_entity_id=deadline.id,
                relationship_type=RelationshipType.DEADLINE_FOR,
                provenance_type=ProvenanceType.ADMIN_VERIFIED,
                confidence_score=1.0,
            ),
            university_id=university_id,
            event_context=event_context,
            event_type="relationship.created",
        )
        if created is not None:
            logger.info(
                "deadline_relationship_created university_id=%s form_id=%s deadline_id=%s relationship_id=%s",
                university_id,
                deadline.related_form_id,
                deadline.id,
                created.id,
            )

    async def related_form_summary(
        self,
        university_id: UUID,
        deadline: Deadline,
    ) -> RelatedFormSummary | None:
        """Return a safe related form summary for a deadline."""

        if deadline.related_form_id is None or self.forms_repository is None:
            return None
        form = await self.forms_repository.get_form_by_id(
            university_id=university_id,
            form_id=deadline.related_form_id,
            include_inactive=True,
        )
        if form is None or _is_blocked_form(form.status, form.verification_status):
            return None
        return RelatedFormSummary(
            form_id=form.id,
            title=form.title,
            category=form.category,
            status=form.status,
            verification_status=form.verification_status,
        )

    async def related_deadline_summaries_for_form(
        self,
        university_id: UUID,
        form_id: UUID,
        role: UserRole,
    ) -> list[RelatedDeadlineSummary]:
        """Return visible related deadline summaries for a form."""

        if self.relationships_service is None:
            return []
        relationships = await self.relationships_service.retrieve_related_entities(
            entity_type="form",
            entity_id=form_id,
        )
        summaries: list[RelatedDeadlineSummary] = []
        seen: set[UUID] = set()
        for relationship in relationships:
            if relationship.relationship_type != RelationshipType.DEADLINE_FOR.value:
                continue
            deadline_id = _deadline_id_from_relationship(relationship, form_id)
            if deadline_id is None or deadline_id in seen:
                continue
            deadline = await self.fetch_deadline(university_id, deadline_id, role)
            if deadline is None:
                continue
            seen.add(deadline.id)
            summaries.append(
                RelatedDeadlineSummary(
                    deadline_id=deadline.id,
                    title=deadline.title,
                    deadline_type=deadline.deadline_type,
                    due_date=deadline.due_date,
                    status=deadline.status,
                    verification_status=deadline.verification_status,
                )
            )
        return summaries


def _is_blocked_form(status: str, verification_status: str) -> bool:
    """Return whether a form lifecycle state prevents linking."""

    return status in BLOCKED_FORM_STATUSES or verification_status in BLOCKED_FORM_STATUSES


def _deadline_id_from_relationship(relationship, form_id: UUID) -> UUID | None:
    """Return the deadline endpoint for a form deadline_for relationship."""

    if relationship.source_entity_type == "form" and relationship.source_entity_id == form_id:
        if relationship.target_entity_type == "deadline":
            return relationship.target_entity_id
        return None
    if relationship.target_entity_type == "form" and relationship.target_entity_id == form_id:
        if relationship.source_entity_type == "deadline":
            return relationship.source_entity_id
    return None
