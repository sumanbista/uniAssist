"""Embedding provider abstraction."""

from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Async-safe interface for deterministic text embeddings."""

    dimensions: int

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        """Return a normalized embedding vector for text."""

        raise NotImplementedError
