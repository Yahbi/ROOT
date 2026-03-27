"""Tests for backend.core.vector_store — TextEmbedder and VectorStore."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from backend.core.vector_store import TextEmbedder, VectorStore, SearchResult


# ── TextEmbedder Tests ──────────────────────────────────────────


class TestTextEmbedderTokenize:
    """Tests for TextEmbedder._tokenize (static method)."""

    def test_basic_tokenization(self):
        tokens = TextEmbedder._tokenize("Hello World test")
        assert tokens == ["hello", "world", "test"]

    def test_strips_punctuation(self):
        tokens = TextEmbedder._tokenize("it's a test! right?")
        # Apostrophe replaced by space, "it" (2 chars) kept, "s" (1 char) dropped
        assert "it" in tokens
        assert "test" in tokens
        assert "right" in tokens
        # Single-char fragments from punctuation stripping are excluded
        assert "s" not in tokens

    def test_filters_short_tokens(self):
        tokens = TextEmbedder._tokenize("I am a big cat")
        # "I", "a" are < 2 chars, should be excluded
        assert "am" in tokens
        assert "big" in tokens
        assert "cat" in tokens
        for t in tokens:
            assert len(t) >= 2

    def test_empty_string(self):
        assert TextEmbedder._tokenize("") == []

    def test_only_punctuation(self):
        assert TextEmbedder._tokenize("!!! ???") == []

    def test_numbers_preserved(self):
        tokens = TextEmbedder._tokenize("buy 100 shares at 25")
        assert "100" in tokens
        assert "25" in tokens


class TestTextEmbedderVocab:
    """Tests for TextEmbedder.fit / partial_fit / vocab persistence."""

    def test_fit_builds_vocab(self):
        embedder = TextEmbedder(dimension=64)
        assert not embedder.is_fitted

        embedder.fit(["hello world", "world test", "hello test"])
        assert embedder.is_fitted
        assert embedder._doc_count == 3

    def test_partial_fit_increments(self):
        embedder = TextEmbedder(dimension=64)
        embedder.partial_fit("hello world")
        assert embedder._doc_count == 1
        embedder.partial_fit("another doc")
        assert embedder._doc_count == 2

    def test_save_load_vocab(self, tmp_path: Path):
        embedder = TextEmbedder(dimension=64)
        embedder.fit(["alpha beta", "beta gamma"])

        vocab_path = tmp_path / "vocab.json"
        embedder.save_vocab(vocab_path)
        assert vocab_path.exists()

        loaded = TextEmbedder(dimension=128)  # different dim initially
        result = loaded.load_vocab(vocab_path)
        assert result is True
        assert loaded.dimension == 64
        assert loaded._doc_count == 2

    def test_load_vocab_missing_file(self, tmp_path: Path):
        embedder = TextEmbedder()
        result = embedder.load_vocab(tmp_path / "nonexistent.json")
        assert result is False


class TestTextEmbedderEmbed:
    """Tests for TextEmbedder.embed."""

    def test_embed_returns_numpy_array(self):
        embedder = TextEmbedder(dimension=64)
        embedder.fit(["test document here"])
        vec = embedder.embed("test document")
        assert isinstance(vec, np.ndarray)

    def test_embed_correct_dimension(self):
        dim = 128
        embedder = TextEmbedder(dimension=dim)
        embedder.fit(["some text"])
        vec = embedder.embed("some text")
        assert vec.shape == (dim,)

    def test_embed_empty_text_returns_zeros(self):
        embedder = TextEmbedder(dimension=32)
        vec = embedder.embed("")
        assert np.allclose(vec, np.zeros(32))

    def test_embed_unit_normalized(self):
        embedder = TextEmbedder(dimension=64)
        embedder.fit(["hello world foo bar"])
        vec = embedder.embed("hello world")
        norm = np.linalg.norm(vec)
        if norm > 0:
            assert abs(norm - 1.0) < 1e-5

    def test_embed_dtype_float32(self):
        embedder = TextEmbedder(dimension=32)
        vec = embedder.embed("anything")
        assert vec.dtype == np.float32

    def test_similar_texts_closer_than_unrelated(self):
        embedder = TextEmbedder(dimension=256)
        corpus = [
            "machine learning algorithms",
            "deep learning neural networks",
            "cooking pasta recipe",
        ]
        embedder.fit(corpus)

        v1 = embedder.embed("machine learning algorithms")
        v2 = embedder.embed("deep learning neural networks")
        v3 = embedder.embed("cooking pasta recipe")

        sim_related = float(np.dot(v1, v2))
        sim_unrelated = float(np.dot(v1, v3))
        # Related texts should have higher similarity
        assert sim_related > sim_unrelated


# ── VectorStore Tests ───────────────────────────────────────────


@pytest.fixture
def vector_store(tmp_path: Path):
    """Provide a started VectorStore with a temp database."""
    db_path = tmp_path / "vectors.db"
    store = VectorStore(db_path=db_path)
    store.start()
    yield store
    store.stop()


class TestVectorStoreLifecycle:
    """Tests for VectorStore start/stop/conn."""

    def test_start_creates_db(self, tmp_path: Path):
        db_path = tmp_path / "test_vectors.db"
        store = VectorStore(db_path=db_path)
        store.start()
        assert db_path.exists()
        store.stop()

    def test_conn_raises_when_not_started(self, tmp_path: Path):
        store = VectorStore(db_path=tmp_path / "v.db")
        with pytest.raises(RuntimeError, match="not started"):
            _ = store.conn


class TestVectorStoreOperations:
    """Tests for store/search/delete/count."""

    def test_store_and_count(self, vector_store: VectorStore):
        vec = np.random.randn(64).astype(np.float32)
        vector_store.store("id-1", "hello world", vec)
        assert vector_store.count() == 1

    def test_store_overwrites_on_same_id(self, vector_store: VectorStore):
        vec1 = np.random.randn(64).astype(np.float32)
        vec2 = np.random.randn(64).astype(np.float32)
        vector_store.store("id-1", "text one", vec1)
        vector_store.store("id-1", "text two", vec2)
        assert vector_store.count() == 1

    def test_delete_existing(self, vector_store: VectorStore):
        vec = np.random.randn(64).astype(np.float32)
        vector_store.store("id-del", "delete me", vec)
        assert vector_store.delete("id-del") is True
        assert vector_store.count() == 0

    def test_delete_nonexistent(self, vector_store: VectorStore):
        assert vector_store.delete("nope") is False

    def test_stats(self, vector_store: VectorStore):
        vec = np.random.randn(64).astype(np.float32)
        vector_store.store("s1", "stats test", vec)
        stats = vector_store.stats()
        assert stats["total_vectors"] == 1
        assert "db_path" in stats


class TestVectorStoreSearch:
    """Tests for search and cosine similarity ordering."""

    def test_empty_store_returns_empty(self, vector_store: VectorStore):
        query = np.random.randn(64).astype(np.float32)
        results = vector_store.search(query)
        assert results == []

    def test_zero_query_returns_empty(self, vector_store: VectorStore):
        vec = np.random.randn(64).astype(np.float32)
        vector_store.store("id-1", "text", vec)
        results = vector_store.search(np.zeros(64, dtype=np.float32))
        assert results == []

    def test_search_returns_search_results(self, vector_store: VectorStore):
        vec = np.ones(64, dtype=np.float32)
        vector_store.store("id-1", "test", vec, metadata={"key": "val"})
        results = vector_store.search(vec, threshold=0.0)
        assert len(results) >= 1
        assert isinstance(results[0], SearchResult)
        assert results[0].id == "id-1"

    def test_cosine_similarity_ordering(self, vector_store: VectorStore):
        # Create a query vector
        query = np.zeros(64, dtype=np.float32)
        query[0] = 1.0

        # Store vectors with varying similarity to query
        close_vec = np.zeros(64, dtype=np.float32)
        close_vec[0] = 1.0
        close_vec[1] = 0.1

        far_vec = np.zeros(64, dtype=np.float32)
        far_vec[5] = 1.0
        far_vec[0] = 0.2

        vector_store.store("close", "close", close_vec)
        vector_store.store("far", "far", far_vec)

        results = vector_store.search(query, top_k=10, threshold=0.0)
        assert len(results) == 2
        assert results[0].id == "close"
        assert results[1].id == "far"
        assert results[0].score > results[1].score

    def test_top_k_limits_results(self, vector_store: VectorStore):
        for i in range(5):
            vec = np.random.randn(64).astype(np.float32)
            vector_store.store(f"id-{i}", f"text {i}", vec)

        query = np.random.randn(64).astype(np.float32)
        results = vector_store.search(query, top_k=2, threshold=0.0)
        assert len(results) <= 2

    def test_threshold_filters_low_scores(self, vector_store: VectorStore):
        # Store a vector orthogonal to query
        vec = np.zeros(64, dtype=np.float32)
        vec[0] = 1.0
        vector_store.store("orth", "orthogonal", vec)

        query = np.zeros(64, dtype=np.float32)
        query[32] = 1.0  # orthogonal

        results = vector_store.search(query, threshold=0.5)
        assert len(results) == 0

    def test_metadata_returned_in_search(self, vector_store: VectorStore):
        vec = np.ones(64, dtype=np.float32)
        vector_store.store("m1", "meta test", vec, metadata={"tag": "alpha"})
        results = vector_store.search(vec, threshold=0.0)
        assert results[0].metadata == {"tag": "alpha"}


class TestVectorStoreHybridSearch:
    """Tests for hybrid_search (RRF fusion)."""

    def test_hybrid_search_empty(self, vector_store: VectorStore):
        query_vec = np.random.randn(64).astype(np.float32)
        results = vector_store.hybrid_search(
            query_text="test",
            query_vector=query_vec,
            fts_results=[],
            top_k=5,
        )
        assert results == []

    def test_hybrid_search_combines_fts_and_vector(self, vector_store: VectorStore):
        # Store vectors
        vec1 = np.ones(64, dtype=np.float32)
        vec2 = np.ones(64, dtype=np.float32) * 0.5
        vector_store.store("doc-1", "machine learning", vec1, {"source": "vec"})
        vector_store.store("doc-2", "deep learning", vec2, {"source": "vec"})

        fts_results = [
            {"id": "doc-2", "text": "deep learning", "score": 10.0},
            {"id": "doc-3", "text": "fts only", "score": 5.0},
        ]

        results = vector_store.hybrid_search(
            query_text="learning",
            query_vector=vec1,
            fts_results=fts_results,
            top_k=10,
        )

        result_ids = [r.id for r in results]
        # doc-2 appears in both, should be boosted
        assert "doc-2" in result_ids
        # doc-3 only in FTS
        assert "doc-3" in result_ids

    def test_hybrid_search_respects_top_k(self, vector_store: VectorStore):
        for i in range(10):
            vec = np.random.randn(64).astype(np.float32)
            vector_store.store(f"h-{i}", f"doc {i}", vec)

        fts_results = [{"id": f"h-{i}"} for i in range(10)]
        query_vec = np.random.randn(64).astype(np.float32)

        results = vector_store.hybrid_search(
            query_text="test",
            query_vector=query_vec,
            fts_results=fts_results,
            top_k=3,
        )
        assert len(results) <= 3
