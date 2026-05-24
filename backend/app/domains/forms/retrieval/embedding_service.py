"""Embedding generation and storage for Forms retrieval."""

from datetime import UTC, datetime
from uuid import UUID

from app.domains.forms.models import Form
from app.domains.forms.repositories import FormsRepository
from app.shared.ai import EmbeddingProvider, LocalEmbeddingProvider


class FormsEmbeddingService:
    """Coordinate explicit form embedding generation and persistence."""

    def __init__(
        self,
        repository: FormsRepository,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.repository = repository
        self.embedding_provider = embedding_provider or LocalEmbeddingProvider()

    async def generate_form_embedding(self, form: Form) -> list[float]:
        """Generate a deterministic embedding input from canonical form fields."""

        embedding_text = _form_embedding_text(form)
        return await self.embedding_provider.embed_text(embedding_text)

    async def update_form_embedding(
        self,
        university_id: UUID,
        form_id: UUID,
    ) -> Form | None:
        """Generate and persist an embedding for a tenant-scoped form."""

        form = await self.repository.get_form_by_id(
            university_id=university_id,
            form_id=form_id,
            include_inactive=True,
        )
        if form is None:
            return None
        embedding = await self.generate_form_embedding(form)
        return await self.repository.update_form_embedding(
            university_id=university_id,
            form_id=form_id,
            embedding=embedding,
            embedding_updated_at=datetime.now(UTC),
        )


def _form_embedding_text(form: Form) -> str:
    """Build the canonical text representation for Forms embeddings."""

    parts = [
        form.title,
        form.description or "",
        form.category or "",
    ]
    return " ".join(part.strip() for part in parts if part and part.strip())
