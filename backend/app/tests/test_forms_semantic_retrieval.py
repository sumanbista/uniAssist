"""Tests for Forms semantic and hybrid retrieval foundations."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domains.forms.retrieval import FormsRetrievalService
from app.domains.forms.retrieval.embedding_service import FormsEmbeddingService


class FakeEmbeddingProvider:
    """Deterministic embedding provider for tests."""

    dimensions = 3

    def __init__(self) -> None:
        self.last_text: str | None = None

    async def embed_text(self, text: str) -> list[float]:
        """Return a stable fake vector."""

        self.last_text = text
        return [0.1, 0.2, 0.3]


class FakeFormsRepository:
    """In-memory repository for retrieval service tests."""

    def __init__(self, forms: list[SimpleNamespace]) -> None:
        self.forms = forms
        self.updated_embedding: list[float] | None = None

    async def search_forms(self, query, university_id, limit):
        """Return FTS candidates."""

        return self.forms[:limit]

    async def semantic_search_forms(self, embedding, university_id, limit):
        """Return semantic candidates with deterministic similarity scores."""

        return [(form, 0.8 - index * 0.1) for index, form in enumerate(self.forms[:limit])]

    async def get_form_by_id(self, university_id, form_id, include_inactive=False):
        """Return a matching fake form."""

        for form in self.forms:
            if form.id == form_id and form.university_id == university_id:
                return form
        return None

    async def update_form_embedding(
        self,
        university_id,
        form_id,
        embedding,
        embedding_updated_at,
    ):
        """Record the embedding update."""

        self.updated_embedding = embedding
        return await self.get_form_by_id(university_id, form_id, include_inactive=True)


@pytest.mark.anyio
async def test_semantic_retrieval_returns_similarity_score() -> None:
    """Semantic retrieval should expose pgvector similarity in ranking metadata."""

    university_id = uuid4()
    form = _fake_form(university_id=university_id, title="Withdrawal Form")
    provider = FakeEmbeddingProvider()
    service = FormsRetrievalService(
        repository=FakeFormsRepository([form]),
        embedding_provider=provider,
    )

    results = await service.retrieve_semantic_forms(
        query="  withdrawal   request ",
        university_id=university_id,
        limit=5,
    )

    assert provider.last_text == "withdrawal request"
    assert len(results) == 1
    assert results[0].similarity_score == 0.8
    assert results[0].ranking_signals["semantic_similarity"] == 0.8


@pytest.mark.anyio
async def test_hybrid_retrieval_fuses_fts_and_semantic_scores() -> None:
    """Hybrid retrieval should deterministically fuse FTS and semantic signals."""

    university_id = uuid4()
    form = _fake_form(university_id=university_id, title="Withdrawal Form")
    service = FormsRetrievalService(
        repository=FakeFormsRepository([form]),
        embedding_provider=FakeEmbeddingProvider(),
    )

    results = await service.retrieve_hybrid_forms(
        query="withdrawal",
        university_id=university_id,
        limit=5,
    )

    assert len(results) == 1
    assert results[0].ranking_score > 0
    assert results[0].ranking_signals["fts_weight"] == 0.55
    assert results[0].ranking_signals["semantic_weight"] == 0.45
    assert results[0].ranking_signals["semantic_similarity"] == 0.8


@pytest.mark.anyio
async def test_forms_embedding_service_updates_embedding() -> None:
    """Embedding service should generate and persist explicit form embeddings."""

    university_id = uuid4()
    form = _fake_form(university_id=university_id, title="Graduation Application")
    repository = FakeFormsRepository([form])
    service = FormsEmbeddingService(
        repository=repository,
        embedding_provider=FakeEmbeddingProvider(),
    )

    updated_form = await service.update_form_embedding(
        university_id=university_id,
        form_id=form.id,
    )

    assert updated_form == form
    assert repository.updated_embedding == [0.1, 0.2, 0.3]


def _fake_form(university_id, title):
    """Create a fake Form-like object for retrieval tests."""

    return SimpleNamespace(
        id=uuid4(),
        university_id=university_id,
        title=title,
        description="Use this form for student workflow requests.",
        category="registrar",
        source_url="https://example.edu/form",
        verification_status="verified",
        verification_score=1.0,
        last_verified_at=datetime.now(UTC),
        next_review_at=None,
        expires_at=None,
        staleness_score=0.0,
        status="published",
        metadata_={},
    )
