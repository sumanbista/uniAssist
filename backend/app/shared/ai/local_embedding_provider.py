"""Local sentence-transformers embedding provider."""

import asyncio
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.shared.ai.embedding_provider import EmbeddingProvider

logger = get_logger(__name__)


class LocalEmbeddingProvider(EmbeddingProvider):
    """Lazy singleton wrapper around a local sentence-transformers model."""

    _model: Any | None = None
    _model_lock = asyncio.Lock()

    def __init__(
        self,
        model_name: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME
        self.dimensions = dimensions or settings.EMBEDDING_DIMENSIONS

    async def embed_text(self, text: str) -> list[float]:
        """Generate a local normalized embedding for text."""

        normalized_text = _normalize_text(text)
        model = await self._get_model()
        vector = await asyncio.to_thread(
            model.encode,
            normalized_text,
            normalize_embeddings=True,
        )
        embedding = [float(value) for value in vector.tolist()]
        if len(embedding) != self.dimensions:
            raise ValueError("Embedding dimension mismatch")
        return embedding

    async def _get_model(self) -> Any:
        """Load the sentence-transformers model once per process."""

        if self.__class__._model is not None:
            return self.__class__._model
        async with self.__class__._model_lock:
            if self.__class__._model is None:
                logger.info("Loading local embedding model: %s", self.model_name)
                self.__class__._model = await asyncio.to_thread(
                    _load_sentence_transformer,
                    self.model_name,
                )
        return self.__class__._model


def _load_sentence_transformer(model_name: str) -> Any:
    """Import and load sentence-transformers lazily."""

    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def _normalize_text(text: str) -> str:
    """Normalize text before embedding generation."""

    normalized_text = " ".join(text.strip().split())
    if not normalized_text:
        raise ValueError("text is required for embedding")
    return normalized_text
