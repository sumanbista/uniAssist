"""Governance lifecycle service for Forms."""

from datetime import UTC, datetime
from uuid import UUID

from app.domains.forms.governance.enums import LifecycleStatus, VerificationStatus
from app.domains.forms.models import Form
from app.domains.forms.repositories import FormsRepository
from app.shared.events import EventBus, EventContext

INVALID_TRANSITIONS: dict[LifecycleStatus, set[LifecycleStatus]] = {
    LifecycleStatus.ARCHIVED: {
        LifecycleStatus.PUBLISHED,
        LifecycleStatus.VERIFIED,
        LifecycleStatus.STALE,
    },
    LifecycleStatus.REJECTED: {
        LifecycleStatus.PUBLISHED,
        LifecycleStatus.VERIFIED,
    },
    LifecycleStatus.DEPRECATED: {
        LifecycleStatus.PUBLISHED,
        LifecycleStatus.VERIFIED,
    },
}


class InvalidLifecycleTransitionError(ValueError):
    """Raised when a lifecycle transition violates governance rules."""


class FormsGovernanceService:
    """Apply deterministic governance rules to canonical forms."""

    def __init__(
        self,
        repository: FormsRepository,
        event_bus: EventBus | None = None,
    ) -> None:
        self.repository = repository
        self.event_bus = event_bus

    async def verify_form(
        self,
        university_id: UUID,
        form_id: UUID,
        verified_by: UUID | None = None,
        verification_score: float | None = None,
        review_notes: str | None = None,
        expires_at: datetime | None = None,
        next_review_at: datetime | None = None,
        event_context: EventContext | None = None,
    ) -> Form | None:
        """Mark a form as verified after transition validation."""

        form = await self.repository.get_form_by_id(
            university_id,
            form_id,
            include_inactive=True,
        )
        if form is None:
            return None

        self._validate_transition(form.status, LifecycleStatus.VERIFIED)
        now = datetime.now(UTC)
        form.status = LifecycleStatus.VERIFIED.value
        form.verification_status = VerificationStatus.VERIFIED.value
        form.last_verified_at = now
        form.verified_by = verified_by
        form.verification_score = (
            verification_score if verification_score is not None else 1.0
        )
        form.review_notes = review_notes
        form.expires_at = expires_at
        form.next_review_at = next_review_at
        form.review_count = form.review_count + 1
        form.staleness_score = 0.0
        saved_form = await self.repository.save_form(form)
        await self._emit_form_event(
            event_type="forms.verified",
            form=saved_form,
            event_context=event_context,
            payload={
                "verification_status": saved_form.verification_status,
                "verification_score": float(saved_form.verification_score)
                if saved_form.verification_score is not None
                else None,
                "review_count": saved_form.review_count,
            },
        )
        return saved_form

    async def publish_form(
        self,
        university_id: UUID,
        form_id: UUID,
        review_notes: str | None = None,
        event_context: EventContext | None = None,
    ) -> Form | None:
        """Publish a verified form for retrieval."""

        form = await self.repository.get_form_by_id(
            university_id,
            form_id,
            include_inactive=True,
        )
        if form is None:
            return None

        self._validate_transition(form.status, LifecycleStatus.PUBLISHED)
        if form.status != LifecycleStatus.VERIFIED.value:
            raise InvalidLifecycleTransitionError("Only verified forms can be published")
        form.status = LifecycleStatus.PUBLISHED.value
        form.verification_status = VerificationStatus.VERIFIED.value
        if review_notes is not None:
            form.review_notes = review_notes
        saved_form = await self.repository.save_form(form)
        await self._emit_form_event(
            event_type="forms.published",
            form=saved_form,
            event_context=event_context,
            payload={
                "status": saved_form.status,
                "verification_status": saved_form.verification_status,
            },
        )
        return saved_form

    async def archive_form(
        self,
        university_id: UUID,
        form_id: UUID,
        review_notes: str | None = None,
        event_context: EventContext | None = None,
    ) -> Form | None:
        """Archive a form and remove it from active retrieval."""

        form = await self.repository.get_form_by_id(
            university_id,
            form_id,
            include_inactive=True,
        )
        if form is None:
            return None

        self._validate_transition(form.status, LifecycleStatus.ARCHIVED)
        form.status = LifecycleStatus.ARCHIVED.value
        form.verification_status = VerificationStatus.ARCHIVED.value
        form.is_active = False
        if review_notes is not None:
            form.review_notes = review_notes
        saved_form = await self.repository.save_form(form)
        await self._emit_form_event(
            event_type="forms.archived",
            form=saved_form,
            event_context=event_context,
            payload={
                "status": saved_form.status,
                "verification_status": saved_form.verification_status,
                "is_active": saved_form.is_active,
            },
        )
        return saved_form

    async def mark_stale_forms(
        self,
        university_id: UUID,
        as_of: datetime | None = None,
        limit: int = 100,
    ) -> list[Form]:
        """Find stale candidates and mark them stale without background jobs."""

        checked_at = as_of or datetime.now(UTC)
        candidates = await self.repository.list_stale_candidates(
            university_id=university_id,
            as_of=checked_at,
            limit=limit,
        )
        stale_forms: list[Form] = []
        for form in candidates:
            self._validate_transition(form.status, LifecycleStatus.STALE)
            form.status = LifecycleStatus.STALE.value
            form.verification_status = VerificationStatus.STALE.value
            form.staleness_score = self.calculate_staleness_score(form, checked_at)
            stale_forms.append(await self.repository.save_form(form, commit=False))
        await self.repository.commit()
        return stale_forms

    @staticmethod
    def is_stale_candidate(form: Form, as_of: datetime | None = None) -> bool:
        """Return whether a form requires revalidation."""

        checked_at = as_of or datetime.now(UTC)
        expires_at = _as_aware(form.expires_at)
        next_review_at = _as_aware(form.next_review_at)
        return (
            expires_at is not None
            and expires_at <= checked_at
            or next_review_at is not None
            and next_review_at <= checked_at
        )

    @staticmethod
    def calculate_staleness_score(form: Form, as_of: datetime | None = None) -> float:
        """Return a deterministic staleness score in the 0..1 range."""

        checked_at = as_of or datetime.now(UTC)
        relevant_dates = [
            governance_date
            for governance_date in (
                _as_aware(form.expires_at),
                _as_aware(form.next_review_at),
            )
            if governance_date is not None and governance_date <= checked_at
        ]
        if not relevant_dates:
            return 0.0
        oldest_due_date = min(relevant_dates)
        overdue_days = max(0, (checked_at - oldest_due_date).days)
        return round(min(1.0, overdue_days / 365), 4)

    @staticmethod
    def _validate_transition(
        current_status: str,
        target_status: LifecycleStatus,
    ) -> None:
        """Prevent invalid lifecycle transitions."""

        current = LifecycleStatus(current_status)
        invalid_targets = INVALID_TRANSITIONS.get(current, set())
        if target_status in invalid_targets:
            raise InvalidLifecycleTransitionError(
                f"Invalid lifecycle transition: {current.value} -> {target_status.value}"
            )

    async def _emit_form_event(
        self,
        event_type: str,
        form: Form,
        payload: dict[str, object],
        event_context: EventContext | None = None,
    ) -> None:
        """Emit an audit-ready form governance event when a bus is configured."""

        if self.event_bus is None:
            return
        await self.event_bus.emit_event(
            event_type=event_type,
            aggregate_type="form",
            aggregate_id=form.id,
            university_id=form.university_id,
            actor_id=event_context.actor_id if event_context else None,
            correlation_id=event_context.correlation_id if event_context else None,
            payload=payload,
            metadata={"source": "forms_governance_service"},
        )


def _as_aware(value: datetime | None) -> datetime | None:
    """Return timezone-aware datetimes for deterministic comparisons."""

    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
