"""
Embedding Service for Feature 4 - Hiring Intelligence RAG.

Provides deterministic embedding generation and validation for persistent
vector retrieval. Supports a local SentenceTransformer provider as well as
a zero-dependency Mock provider for unit and regression testing.

Architecture:
- Output dimension is strictly pinned to 384 (matching all-MiniLM-L6-v2).
- Unit tests use MockEmbeddingProvider to guarantee zero network access,
  no weights download, and sub-millisecond execution.
- Real provider lazily loads weights on first actual invocation.
"""
from __future__ import annotations

import hashlib
import logging
import math
import random
from typing import Protocol, Sequence, runtime_checkable

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"
DEFAULT_EMBEDDING_DIMENSION = 384


class EmbeddingServiceError(Exception):
    """Raised when embedding generation, input text, or vector validation fails."""


def validate_embedding_vector(vector: Sequence[float], expected_dim: int = DEFAULT_EMBEDDING_DIMENSION) -> list[float]:
    """
    Validates that the provided vector meets all integrity constraints:
    - Must be a sequence of floats of exact length expected_dim.
    - All elements must be finite numbers (no NaN or Inf).
    - Vector must not be entirely zero or empty.
    Returns the vector as a list of floats.
    """
    if not isinstance(vector, (list, tuple)):
        raise EmbeddingServiceError(f"Embedding must be a sequence, got {type(vector).__name__}")

    if len(vector) != expected_dim:
        raise EmbeddingServiceError(
            f"Embedding dimension mismatch: expected {expected_dim}, got {len(vector)}"
        )

    norm_sq = 0.0
    cleaned: list[float] = []
    for i, val in enumerate(vector):
        if not isinstance(val, (int, float)):
            raise EmbeddingServiceError(f"Embedding element at index {i} is not a float: {val!r}")
        f_val = float(val)
        if math.isnan(f_val) or math.isinf(f_val):
            raise EmbeddingServiceError(f"Embedding element at index {i} is invalid (NaN or Inf): {f_val}")
        cleaned.append(f_val)
        norm_sq += f_val * f_val

    if norm_sq == 0.0:
        raise EmbeddingServiceError("Embedding vector cannot be an all-zero vector.")

    return cleaned


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding generation providers."""

    @property
    def model_name(self) -> str:
        ...

    @property
    def dimension(self) -> int:
        ...

    def embed_text(self, text: str) -> list[float]:
        ...

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        ...


class MockEmbeddingProvider:
    """
    Deterministic mock provider for unit and regression testing.
    
    Generates repeatable 384-dimensional unit vectors based on text hashing.
    Requires no external dependencies, no network access, and executes in microseconds.
    """

    def __init__(
        self,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
        model_name: str = "mock-mini-lm-384",
    ) -> None:
        self._dim = dimension
        self._model = model_name

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dim

    def embed_text(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise EmbeddingServiceError("Cannot embed empty or whitespace-only text.")

        # Create a deterministic seed from the input text
        seed = int(hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()[:16], 16)
        rng = random.Random(seed)
        vec = [rng.gauss(0.0, 1.0) for _ in range(self._dim)]

        # Normalize to unit vector
        norm = math.sqrt(sum(v * v for v in vec))
        if norm == 0.0:
            vec[0] = 1.0
            norm = 1.0
        normalized = [round(v / norm, 6) for v in vec]
        return validate_embedding_vector(normalized, self._dim)

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        cleaned = [t.strip() for t in texts if isinstance(t, str) and t.strip()]
        if len(cleaned) != len(texts):
            raise EmbeddingServiceError("Cannot embed batch containing empty or whitespace-only texts.")
        return [self.embed_text(t) for t in texts]


class SentenceTransformerEmbeddingProvider:
    """
    Production embedding provider using local SentenceTransformer on CPU.
    
    Lazily loads model weights upon first actual embedding request.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_EMBEDDING_MODEL,
        dimension: int = DEFAULT_EMBEDDING_DIMENSION,
    ) -> None:
        self._model_name = model_name
        self._dimension = dimension
        self._model = None

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise EmbeddingServiceError(
                    "sentence-transformers is not installed in the current environment."
                ) from exc
            logger.info("Loading SentenceTransformer model %s (device=cpu)", self._model_name)
            try:
                # Prioritize local cached files for fast sub-second startup without network roundtrips
                self._model = SentenceTransformer(self._model_name, device="cpu", local_files_only=True)
            except Exception:
                # Fallback to standard online download if local cache is not present
                self._model = SentenceTransformer(self._model_name, device="cpu")
        return self._model

    def embed_text(self, text: str) -> list[float]:
        if not text or not text.strip():
            raise EmbeddingServiceError("Cannot embed empty or whitespace-only text.")
        model = self._get_model()
        raw_emb = model.encode(text.strip(), normalize_embeddings=True)
        vec = raw_emb.tolist() if hasattr(raw_emb, "tolist") else list(raw_emb)
        return validate_embedding_vector(vec, self._dimension)

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        cleaned = [t.strip() for t in texts if t and t.strip()]
        if len(cleaned) != len(texts):
            raise EmbeddingServiceError("Cannot embed batch containing empty or whitespace-only texts.")
        if not cleaned:
            return []
        model = self._get_model()
        raw_embs = model.encode(cleaned, normalize_embeddings=True)
        return [
            validate_embedding_vector(e.tolist() if hasattr(e, "tolist") else list(e), self._dimension)
            for e in raw_embs
        ]


# Global provider registry for dependency injection & testing
_current_provider: EmbeddingProvider | None = None


def get_embedding_provider() -> EmbeddingProvider:
    """
    Returns the currently configured EmbeddingProvider.
    Defaults to SentenceTransformerEmbeddingProvider unless overridden (e.g. in tests).
    """
    global _current_provider
    if _current_provider is None:
        model_name = getattr(settings, "embedding_model", DEFAULT_EMBEDDING_MODEL)
        dimension = getattr(settings, "embedding_dimension", DEFAULT_EMBEDDING_DIMENSION)
        _current_provider = SentenceTransformerEmbeddingProvider(
            model_name=model_name,
            dimension=dimension,
        )
    return _current_provider


def set_embedding_provider(provider: EmbeddingProvider | None) -> None:
    """Sets or resets the active EmbeddingProvider (used by tests)."""
    global _current_provider
    _current_provider = provider
