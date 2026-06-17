"""Service layer for governance review queues."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.domains.forms.governance.enums import LifecycleStatus, VerificationStatus
from app.domains.forms.models import Form
from app.domains.governance.review_queue.schemas import (
    ReviewDecision,
    ReviewDecisionRequest,
    ReviewDecisionResponse,
    ReviewItemResponse,
)
from app.shared.events import EventBus, EventContext, EventStore

logger = get_logger(__name__)
SUPPORTED_ENTITY_TYPES = frozenset({"form"})


class InvalidReviewDecisionError(ValueError):
    """Raised when a review decision violates lifecycle rules."""


class ReviewQueueService:
    """Coordinate tenant-scoped review queue reads and decisions."""

    def __init__(
        self,
        session: AsyncSession,
        event_bus: EventBus | None = None,
    ) -> None:
        self.session = session
        self.event_bus = event_bus or EventBus(EventStore(session))

    async def list_pending_reviews(
        self,
        *,
        university_id: UUID,
        entity_type: str = "form",
        limit: int = 100,
        offset: int = 0,
    ) -> list[ReviewItemResponse]:
        """List tenant-scoped pending review entities."""

        normalized_entity_type = _normalize_supported_entity_type(entity_type)
        if normalized_entity_type != "form":
            raise InvalidReviewDecisionError("Unsupported review entity type")
        rows = await self.session.execute(
            select(Form)
            .where(
                Form.university_id == university_id,
                Form.is_active.is_(True),
                Form.status == LifecycleStatus.PENDING_REVIEW.value,
                Form.verification_status == VerificationStatus.PENDING_REVIEW.value,
            )
            .order_by(Form.created_at.asc(), Form.id.asc())
            .limit(min(max(limit, 1), 100))
            .offset(max(offset, 0))
        )
        return [
            _form_to_review_item(form)
            for form in rows.scalars().all()
            if _is_pending_review_form(form)
        ]

    async def get_review_item(
        self,
        *,
        university_id: UUID,
        entity_type: str,
        entity_id: UUID,
    ) -> ReviewItemResponse | None:
        """Return one tenant-scoped review item."""

        normalized_entity_type = _normalize_supported_entity_type(entity_type)
        if normalized_entity_type != "form":
            raise InvalidReviewDecisionError("Unsupported review entity type")
        form = await self._get_form(university_id=university_id, form_id=entity_id)
        if form is None:
            return None
        return _form_to_review_item(form)

    async def decide_review(
        self,
        *,
        university_id: UUID,
        request: ReviewDecisionRequest,
        event_context: EventContext,
    ) -> ReviewDecisionResponse | None:
        """Approve or reject a pending-review entity."""

        entity_type = _normalize_supported_entity_type(request.entity_type)
        if entity_type != "form":
            raise InvalidReviewDecisionError("Unsupported review entity type")
        form = await self._get_form(university_id=university_id, form_id=request.entity_id)
        if form is None:
            return None
        self._validate_pending_transition(form)

        if request.decision == ReviewDecision.APPROVE:
            target_status = LifecycleStatus.VERIFIED
            target_verification = VerificationStatus.VERIFIED
            event_type = "review.approved"
            form.last_verified_at = datetime.now(UTC)
            form.verified_by = event_context.actor_id
            form.verification_score = 1.0
            form.staleness_score = 0.0
        else:
            target_status = LifecycleStatus.REJECTED
            target_verification = VerificationStatus.REJECTED
            event_type = "review.rejected"
            form.is_active = False

        form.status = target_status.value
        form.verification_status = target_verification.value
        form.review_notes = request.review_notes
        form.review_count = form.review_count + 1
        self.session.add(form)
        await self.session.commit()
        await self.session.refresh(form)
        await self._emit_review_event(
            event_type=event_type,
            form=form,
            review_notes=request.review_notes,
            event_context=event_context,
        )
        logger.info(
            "review_decision_applied entity_type=form entity_id=%s decision=%s university_id=%s actor_id=%s",
            form.id,
            request.decision.value,
            university_id,
            event_context.actor_id,
        )
        return ReviewDecisionResponse(
            entity_type="form",
            entity_id=form.id,
            decision=request.decision,
            status=form.status,
            verification_status=form.verification_status,
            review_notes=form.review_notes,
        )

    async def _get_form(self, *, university_id: UUID, form_id: UUID) -> Form | None:
        """Return a tenant-scoped form for review."""

        rows = await self.session.execute(
            select(Form).where(
                Form.university_id == university_id,
                Form.id == form_id,
            )
        )
        return rows.scalar_one_or_none()

    @staticmethod
    def _validate_pending_transition(form: Form) -> None:
        """Allow decisions only for pending-review forms."""

        if (
            not _is_pending_review_form(form)
        ):
            raise InvalidReviewDecisionError(
                "Only pending_review forms can be approved or rejected"
            )

    async def _emit_review_event(
        self,
        *,
        event_type: str,
        form: Form,
        review_notes: str | None,
        event_context: EventContext,
    ) -> None:
        """Emit an audit-ready review decision event."""

        payload = {
            "entity_type": "form",
            "entity_id": str(form.id),
            "actor_id": str(event_context.actor_id) if event_context.actor_id else None,
            "university_id": str(form.university_id),
            "review_notes": review_notes,
            "correlation_id": (
                str(event_context.correlation_id)
                if event_context.correlation_id
                else None
            ),
        }
        await self.event_bus.emit_event(
            event_type=event_type,
            aggregate_type="form",
            aggregate_id=form.id,
            university_id=form.university_id,
            actor_id=event_context.actor_id,
            correlation_id=event_context.correlation_id,
            payload=payload,
            metadata={"source": "review_queue_service"},
        )


def _normalize_supported_entity_type(entity_type: str) -> str:
    """Normalize and validate supported review entity types."""

    normalized = entity_type.strip().lower()
    if normalized not in SUPPORTED_ENTITY_TYPES:
        raise InvalidReviewDecisionError("Unsupported review entity type")
    return normalized


def _form_to_review_item(form: Form) -> ReviewItemResponse:
    """Convert a form into a review queue item."""

    return ReviewItemResponse(
        entity_type="form",
        entity_id=form.id,
        title=form.title,
        category=form.category,
        source_url=form.source_url,
        status=form.status,
        verification_status=form.verification_status,
        submitted_at=form.created_at,
        source_metadata=_source_metadata(form.metadata_),
    )


def _is_pending_review_form(form: Form) -> bool:
    """Return whether a form is currently awaiting review."""

    return (
        form.status == LifecycleStatus.PENDING_REVIEW.value
        and form.verification_status == VerificationStatus.PENDING_REVIEW.value
    )


def _source_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Return source-related metadata without mutating stored JSON."""

    if not metadata:
        return {}
    allowed_keys = {
        "source_id",
        "source_hash",
        "original_filename",
        "file_size",
        "page_count",
        "upload_method",
        "department",
        "content_hash",
    }
    return {key: metadata[key] for key in allowed_keys if key in metadata}
