"""Embedding provider boundary with lazy local MiniLM loading."""

from __future__ import annotations

import hashlib
from typing import Protocol


EMBEDDING_DIMENSION = 384


class Embedder(Protocol):
    model_name: str

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class MiniLMEmbedder:
    def __init__(self, model_name: str):
        self.model_name = model_name
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        vectors = self._load().encode(texts, normalize_embeddings=True)
        return [vector.tolist() for vector in vectors]


class DeterministicTestEmbedder:
    """Dependency-free 384D vectors for unit tests, never used in production."""

    model_name = "deterministic-test-embedder"

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = []
        for text in texts:
            digest = hashlib.sha256(text.casefold().encode("utf-8")).digest()
            values = [((digest[index % len(digest)] / 255) * 2) - 1 for index in range(EMBEDDING_DIMENSION)]
            norm = sum(value * value for value in values) ** 0.5 or 1
            vectors.append([value / norm for value in values])
        return vectors
