"""
Unit tests for Stage 1: Embedding Service & Validation.

Tests contract, dimension validation, error conditions, and deterministic mock behavior.
Guarantees tests never download models or make network calls.
"""
import math
import pytest

from app.services.embedding_service import (
    DEFAULT_EMBEDDING_DIMENSION,
    DEFAULT_EMBEDDING_MODEL,
    EmbeddingProvider,
    EmbeddingServiceError,
    MockEmbeddingProvider,
    SentenceTransformerEmbeddingProvider,
    get_embedding_provider,
    set_embedding_provider,
    validate_embedding_vector,
)


@pytest.fixture(autouse=True)
def ensure_mock_provider():
    """Ensure every test in this module operates with MockEmbeddingProvider."""
    provider = MockEmbeddingProvider(dimension=384, model_name="test-mock-384")
    set_embedding_provider(provider)
    yield provider
    set_embedding_provider(None)


class TestVectorValidation:
    def test_valid_384_dimension_vector(self):
        vec = [0.1] * 384
        validated = validate_embedding_vector(vec, expected_dim=384)
        assert len(validated) == 384
        assert all(isinstance(x, float) for x in validated)

    def test_dimension_mismatch_too_short(self):
        vec = [0.1] * 128
        with pytest.raises(EmbeddingServiceError, match="dimension mismatch"):
            validate_embedding_vector(vec, expected_dim=384)

    def test_dimension_mismatch_too_long(self):
        vec = [0.1] * 512
        with pytest.raises(EmbeddingServiceError, match="dimension mismatch"):
            validate_embedding_vector(vec, expected_dim=384)

    def test_rejects_nan(self):
        vec = [0.1] * 383 + [float("nan")]
        with pytest.raises(EmbeddingServiceError, match="invalid.*NaN"):
            validate_embedding_vector(vec, expected_dim=384)

    def test_rejects_inf(self):
        vec = [0.1] * 383 + [float("inf")]
        with pytest.raises(EmbeddingServiceError, match="invalid.*Inf"):
            validate_embedding_vector(vec, expected_dim=384)

    def test_rejects_non_numeric_elements(self):
        vec = [0.1] * 383 + ["string_element"]  # type: ignore
        with pytest.raises(EmbeddingServiceError, match="not a float"):
            validate_embedding_vector(vec, expected_dim=384)

    def test_rejects_all_zero_vector(self):
        vec = [0.0] * 384
        with pytest.raises(EmbeddingServiceError, match="cannot be an all-zero vector"):
            validate_embedding_vector(vec, expected_dim=384)

    def test_rejects_non_sequence(self):
        with pytest.raises(EmbeddingServiceError, match="must be a sequence"):
            validate_embedding_vector("not a vector", expected_dim=384)  # type: ignore


class TestMockEmbeddingProvider:
    def test_protocol_conformance(self):
        provider = MockEmbeddingProvider()
        assert isinstance(provider, EmbeddingProvider)
        assert provider.dimension == 384
        assert provider.model_name == "mock-mini-lm-384"

    def test_embed_text_dimensions_and_normalization(self):
        provider = MockEmbeddingProvider()
        vec = provider.embed_text("Senior Python Developer with FastAPI and PostgreSQL skills")
        assert len(vec) == 384
        assert all(isinstance(v, float) for v in vec)
        # Verify L2 norm is ~1.0 (normalized unit vector)
        l2_norm = math.sqrt(sum(v * v for v in vec))
        assert abs(l2_norm - 1.0) < 1e-3

    def test_deterministic_embedding(self):
        provider = MockEmbeddingProvider()
        v1 = provider.embed_text("Same input text")
        v2 = provider.embed_text("Same input text")
        assert v1 == v2

    def test_different_texts_produce_different_embeddings(self):
        provider = MockEmbeddingProvider()
        v1 = provider.embed_text("Senior Python Backend Engineer")
        v2 = provider.embed_text("Junior Graphic Designer UI/UX")
        assert v1 != v2

    def test_embed_empty_or_whitespace_raises_error(self):
        provider = MockEmbeddingProvider()
        with pytest.raises(EmbeddingServiceError, match="empty or whitespace"):
            provider.embed_text("")

        with pytest.raises(EmbeddingServiceError, match="empty or whitespace"):
            provider.embed_text("   \n\t  ")

    def test_embed_batch(self):
        provider = MockEmbeddingProvider()
        texts = ["Text one", "Text two", "Text three"]
        batch_vecs = provider.embed_batch(texts)
        assert len(batch_vecs) == 3
        for i, text in enumerate(texts):
            assert batch_vecs[i] == provider.embed_text(text)

    def test_embed_batch_with_empty_item_raises_error(self):
        provider = MockEmbeddingProvider()
        with pytest.raises(EmbeddingServiceError, match="Cannot embed batch"):
            provider.embed_batch(["Valid text", "   "])


class TestProviderRegistry:
    def test_custom_provider_injection(self):
        custom = MockEmbeddingProvider(dimension=384, model_name="custom-test")
        set_embedding_provider(custom)
        active = get_embedding_provider()
        assert active is custom
        assert active.model_name == "custom-test"

    def test_sentence_transformer_provider_lazy_loading(self):
        # Initializing the provider must NOT load the model immediately
        st_provider = SentenceTransformerEmbeddingProvider(model_name=DEFAULT_EMBEDDING_MODEL, dimension=384)
        assert st_provider._model is None
        assert st_provider.model_name == DEFAULT_EMBEDDING_MODEL
        assert st_provider.dimension == 384
