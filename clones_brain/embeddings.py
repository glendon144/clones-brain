from __future__ import annotations

from typing import Protocol

from .config import load_settings


class EmbeddingProvider(Protocol):
    def embed(self, text: str) -> list[float] | None:
        ...


class DisabledEmbeddingProvider:
    def embed(self, text: str) -> list[float] | None:
        return None


# TODO: Add a local embedding backend when there is a concrete need.
def get_embedding_provider() -> EmbeddingProvider:
    settings = load_settings()
    if not settings.embeddings_enabled:
        return DisabledEmbeddingProvider()
    return DisabledEmbeddingProvider()
