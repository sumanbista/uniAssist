"""Deterministic ranking for Forms retrieval."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.domains.forms.models import Form

EXACT_TITLE_MATCH_WEIGHT = 0.35
VERIFICATION_SCORE_WEIGHT = 0.30
FRESHNESS_WEIGHT = 0.20
GOVERNANCE_STATUS_WEIGHT = 0.15
FRESHNESS_WINDOW_DAYS = 365

STATUS_BOOSTS: dict[str, float] = {
    "published": 1.0,
    "verified": 0.9,
    "pending_review": 0.45,
    "draft": 0.25,
    "stale": 0.1,
}
VERIFICATION_STATUS_BOOSTS: dict[str, float] = {
    "verified": 1.0,
    "pending_review": 0.45,
    "low_confidence": 0.2,
    "stale": 0.1,
}


@dataclass(frozen=True)
class RankingResult:
    """Ranked form with explainable scoring details."""

    form: Form
    score: float
    signals: dict[str, float]


def rank_forms(query: str, forms: list[Form]) -> list[RankingResult]:
    """Rank forms with deterministic, explainable scoring."""

    ranked_forms = [score_form(query, form) for form in forms]
    return sorted(
        ranked_forms,
        key=lambda result: (
            -result.score,
            result.form.title.lower(),
            str(result.form.id),
        ),
    )


def score_form(query: str, form: Form) -> RankingResult:
    """Calculate a weighted retrieval score for a form."""

    exact_title_match = _exact_title_match_score(query, form.title)
    verification_score = _verification_score(form.verification_score)
    freshness_score = _freshness_score(form.last_verified_at)
    governance_score = _governance_score(form.status, form.verification_status)

    signals = {
        "exact_title_match": exact_title_match,
        "verification_score": verification_score,
        "freshness": freshness_score,
        "governance_status": governance_score,
    }
    weighted_score = (
        exact_title_match * EXACT_TITLE_MATCH_WEIGHT
        + verification_score * VERIFICATION_SCORE_WEIGHT
        + freshness_score * FRESHNESS_WEIGHT
        + governance_score * GOVERNANCE_STATUS_WEIGHT
    )
    return RankingResult(
        form=form,
        score=round(weighted_score, 4),
        signals=signals,
    )


def _exact_title_match_score(query: str, title: str) -> float:
    """Return a title-match boost for exact or contained title matches."""

    normalized_query = query.strip().casefold()
    normalized_title = title.strip().casefold()
    if not normalized_query:
        return 0.0
    if normalized_query == normalized_title:
        return 1.0
    if normalized_query in normalized_title:
        return 0.7
    return 0.0


def _verification_score(value: Decimal | float | None) -> float:
    """Normalize stored verification score to the 0..1 range."""

    if value is None:
        return 0.0
    numeric_value = float(value)
    if numeric_value > 1:
        numeric_value = numeric_value / 100
    return max(0.0, min(1.0, numeric_value))


def _freshness_score(last_verified_at: datetime | None) -> float:
    """Score freshness by recency within the configured review window."""

    if last_verified_at is None:
        return 0.0
    verified_at = last_verified_at
    if verified_at.tzinfo is None:
        verified_at = verified_at.replace(tzinfo=UTC)
    age_days = max(0, (datetime.now(UTC) - verified_at).days)
    freshness = 1 - (age_days / FRESHNESS_WINDOW_DAYS)
    return round(max(0.0, min(1.0, freshness)), 4)


def _governance_score(status: str, verification_status: str) -> float:
    """Score governance quality from lifecycle and verification states."""

    status_score = STATUS_BOOSTS.get(status, 0.0)
    verification_status_score = VERIFICATION_STATUS_BOOSTS.get(
        verification_status,
        0.0,
    )
    return round(max(status_score, verification_status_score), 4)
