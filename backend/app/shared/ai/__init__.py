"""Shared AI provider abstractions."""

from app.shared.ai.embedding_provider import EmbeddingProvider
from app.shared.ai.local_embedding_provider import LocalEmbeddingProvider

__all__ = ["EmbeddingProvider", "LocalEmbeddingProvider"]
