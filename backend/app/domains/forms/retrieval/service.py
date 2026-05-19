"""Forms retrieval service."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domains.forms.repositories import FormsRepository
from app.domains.forms.retrieval.ranking import rank_forms


@dataclass(frozen=True)
class RetrievedForm:
    """Normalized Forms retrieval result."""

    id: UUID
    university_id: UUID
    title: str
    description: str | None
    category: str | None
    source_url: str | None
    verification_status: str
    verification_score: float | None
    last_verified_at: datetime | None
    next_review_at: datetime | None
    expires_at: datetime | None
    staleness_score: float | None
    status: str
    metadata: dict[str, Any]
    ranking_score: float
    ranking_signals: dict[str, float]


class FormsRetrievalService:
    """Coordinate Forms FTS retrieval and deterministic ranking."""

    def __init__(self, repository: FormsRepository) -> None:
        self.repository = repository

    async def retrieve_forms(
        self,
        query: str,
        university_id: UUID,
        limit: int,
    ) -> list[RetrievedForm]:
        """Retrieve and rank tenant-scoped forms."""

        candidate_limit = max(limit * 3, limit)
        candidates = await self.repository.search_forms(
            query=query,
            university_id=university_id,
            limit=candidate_limit,
        )
        ranked_forms = rank_forms(query, candidates)
        return [
            RetrievedForm(
                id=result.form.id,
                university_id=result.form.university_id,
                title=result.form.title,
                description=result.form.description,
                category=result.form.category,
                source_url=result.form.source_url,
                verification_status=result.form.verification_status,
                verification_score=float(result.form.verification_score)
                if result.form.verification_score is not None
                else None,
                last_verified_at=result.form.last_verified_at,
                next_review_at=result.form.next_review_at,
                expires_at=result.form.expires_at,
                staleness_score=float(result.form.staleness_score)
                if result.form.staleness_score is not None
                else None,
                status=result.form.status,
                metadata=result.form.metadata_,
                ranking_score=result.score,
                ranking_signals=result.signals,
            )
            for result in ranked_forms[:limit]
        ]
