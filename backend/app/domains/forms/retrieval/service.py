"""Forms retrieval service."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.core.logging import get_logger
from app.domains.forms.repositories import FormsRepository
from app.domains.forms.retrieval.ranking import rank_forms
from app.shared.ai import EmbeddingProvider, LocalEmbeddingProvider

logger = get_logger(__name__)


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
    similarity_score: float | None = None


class FormsRetrievalService:
    """Coordinate Forms FTS, semantic, and hybrid retrieval."""

    def __init__(
        self,
        repository: FormsRepository,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.repository = repository
        self.embedding_provider = embedding_provider or LocalEmbeddingProvider()

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
            _to_retrieved_form(
                form=result.form,
                ranking_score=result.score,
                ranking_signals=result.signals,
            )
            for result in ranked_forms[:limit]
        ]

    async def retrieve_semantic_forms(
        self,
        query: str,
        university_id: UUID,
        limit: int,
    ) -> list[RetrievedForm]:
        """Retrieve tenant-scoped forms using local embeddings and pgvector."""

        normalized_query = _normalize_query(query)
        embedding = await self.embedding_provider.embed_text(normalized_query)
        semantic_results = await self.repository.semantic_search_forms(
            embedding=embedding,
            university_id=university_id,
            limit=limit,
        )
        logger.info(
            "forms_semantic_search query_length=%s university_id=%s results=%s",
            len(normalized_query),
            university_id,
            len(semantic_results),
        )
        return [
            _to_retrieved_form(
                form=form,
                ranking_score=round(max(0.0, min(1.0, similarity_score)), 4),
                ranking_signals={"semantic_similarity": round(similarity_score, 4)},
                similarity_score=round(similarity_score, 4),
            )
            for form, similarity_score in semantic_results
        ]

    async def retrieve_hybrid_forms(
        self,
        query: str,
        university_id: UUID,
        limit: int,
    ) -> list[RetrievedForm]:
        """Retrieve forms with deterministic FTS and semantic score fusion."""

        normalized_query = _normalize_query(query)
        candidate_limit = max(limit * 3, limit)
        fts_results = await self.retrieve_forms(
            query=normalized_query,
            university_id=university_id,
            limit=candidate_limit,
        )
        semantic_results = await self.retrieve_semantic_forms(
            query=normalized_query,
            university_id=university_id,
            limit=candidate_limit,
        )
        merged_results = _merge_hybrid_results(fts_results, semantic_results)
        logger.info(
            "forms_hybrid_search query_length=%s university_id=%s results=%s",
            len(normalized_query),
            university_id,
            len(merged_results),
        )
        return merged_results[:limit]


def _to_retrieved_form(
    form: Any,
    ranking_score: float,
    ranking_signals: dict[str, float],
    similarity_score: float | None = None,
) -> RetrievedForm:
    """Convert a Form model into a retrieval DTO."""

    return RetrievedForm(
        id=form.id,
        university_id=form.university_id,
        title=form.title,
        description=form.description,
        category=form.category,
        source_url=form.source_url,
        verification_status=form.verification_status,
        verification_score=float(form.verification_score)
        if form.verification_score is not None
        else None,
        last_verified_at=form.last_verified_at,
        next_review_at=form.next_review_at,
        expires_at=form.expires_at,
        staleness_score=float(form.staleness_score)
        if form.staleness_score is not None
        else None,
        status=form.status,
        metadata=form.metadata_,
        ranking_score=round(ranking_score, 4),
        ranking_signals=ranking_signals,
        similarity_score=similarity_score,
    )


def _merge_hybrid_results(
    fts_results: list[RetrievedForm],
    semantic_results: list[RetrievedForm],
) -> list[RetrievedForm]:
    """Merge FTS and semantic candidates with explainable score fusion."""

    merged: dict[UUID, RetrievedForm] = {}
    semantic_by_id = {result.id: result for result in semantic_results}
    fts_by_id = {result.id: result for result in fts_results}
    for form_id in set(fts_by_id) | set(semantic_by_id):
        fts_result = fts_by_id.get(form_id)
        semantic_result = semantic_by_id.get(form_id)
        base_result = fts_result or semantic_result
        if base_result is None:
            continue
        fts_score = fts_result.ranking_score if fts_result else 0.0
        semantic_score = (
            max(0.0, min(1.0, semantic_result.similarity_score or 0.0))
            if semantic_result
            else 0.0
        )
        hybrid_score = (
            fts_score * settings.FORMS_FTS_WEIGHT
            + semantic_score * settings.FORMS_SEMANTIC_WEIGHT
        )
        signals = dict(base_result.ranking_signals)
        signals.update(
            {
                "fts_score": round(fts_score, 4),
                "semantic_similarity": round(semantic_score, 4),
                "fts_weight": settings.FORMS_FTS_WEIGHT,
                "semantic_weight": settings.FORMS_SEMANTIC_WEIGHT,
            }
        )
        merged[form_id] = RetrievedForm(
            **{
                **base_result.__dict__,
                "ranking_score": round(hybrid_score, 4),
                "ranking_signals": signals,
                "similarity_score": semantic_result.similarity_score
                if semantic_result
                else None,
            }
        )
    return sorted(
        merged.values(),
        key=lambda result: (-result.ranking_score, result.title.lower(), str(result.id)),
    )


def _normalize_query(query: str) -> str:
    """Normalize retrieval query text."""

    normalized_query = " ".join(query.strip().split())
    if not normalized_query:
        raise ValueError("query is required")
    return normalized_query
