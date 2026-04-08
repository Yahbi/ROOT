"""Tests for the Memory Engine — FTS5 search, dedup, decay, strengthen, hybrid search."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest

from backend.models.memory import MemoryEntry, MemoryQuery, MemoryType


class TestMemoryEngineStore:
    def test_store_and_recall(self, memory_engine):
        entry = MemoryEntry(
            content="Python is a programming language",
            memory_type=MemoryType.FACT,
            tags=["python", "programming"],
            source="test",
        )
        stored = memory_engine.store(entry)
        assert stored.id is not None
        assert stored.id.startswith("mem_")

        recalled = memory_engine.recall(stored.id)
        assert recalled is not None
        assert recalled.content == "Python is a programming language"

    def test_store_deduplication(self, memory_engine):
        entry1 = MemoryEntry(
            content="Duplicate content that should be detected and merged together",
            memory_type=MemoryType.FACT,
            source="test",
        )
        entry2 = MemoryEntry(
            content="Duplicate content that should be detected and merged together",
            memory_type=MemoryType.FACT,
            source="test",
        )
        stored1 = memory_engine.store(entry1)
        stored2 = memory_engine.store(entry2)
        # Second store should return existing (dedup)
        assert stored1.id == stored2.id

    def test_count(self, memory_engine):
        assert memory_engine.count() == 0
        memory_engine.store(MemoryEntry(
            content="First memory entry for counting test",
            memory_type=MemoryType.FACT, source="test",
        ))
        assert memory_engine.count() == 1


class TestMemoryEngineSearch:
    def test_fts_search(self, memory_engine):
        memory_engine.store(MemoryEntry(
            content="FastAPI is a modern web framework for Python",
            memory_type=MemoryType.FACT, source="test",
        ))
        memory_engine.store(MemoryEntry(
            content="Django is a traditional web framework for Python",
            memory_type=MemoryType.FACT, source="test",
        ))
        results = memory_engine.search(MemoryQuery(query="FastAPI", limit=10))
        assert len(results) >= 1
        assert any("FastAPI" in r.content for r in results)

    def test_search_with_type_filter(self, memory_engine):
        memory_engine.store(MemoryEntry(
            content="A fact about testing that should appear in search",
            memory_type=MemoryType.FACT, source="test",
        ))
        memory_engine.store(MemoryEntry(
            content="A learning about testing that should not appear here",
            memory_type=MemoryType.LEARNING, source="test",
        ))
        results = memory_engine.search(MemoryQuery(
            query="testing", memory_type=MemoryType.FACT, limit=10,
        ))
        assert all(r.memory_type == MemoryType.FACT for r in results)


class TestMemoryEngineMaintenance:
    def test_decay(self, memory_engine):
        memory_engine.store(MemoryEntry(
            content="Memory that will decay over time naturally here",
            memory_type=MemoryType.FACT, source="test", confidence=0.5,
        ))
        affected = memory_engine.decay(factor=0.5)
        assert affected >= 1

    def test_strengthen(self, memory_engine):
        entry = memory_engine.store(MemoryEntry(
            content="Memory to strengthen for retention testing purposes",
            memory_type=MemoryType.FACT, source="test", confidence=0.5,
        ))
        memory_engine.strengthen(entry.id, boost=0.2)
        recalled = memory_engine.recall(entry.id)
        assert recalled.confidence >= 0.7

    def test_supersede(self, memory_engine):
        old = memory_engine.store(MemoryEntry(
            content="Old knowledge about something outdated here now",
            memory_type=MemoryType.FACT, source="test",
        ))
        new_entry = MemoryEntry(
            content="Updated knowledge about something current now",
            memory_type=MemoryType.FACT, source="test",
        )
        new = memory_engine.supersede(old.id, new_entry)
        assert new.id != old.id
        # Old memory should be superseded
        old_recalled = memory_engine.recall(old.id)
        assert old_recalled is not None  # Still exists but superseded


class TestFTSSanitization:
    def test_sanitize_special_chars(self, memory_engine):
        # Should not crash with special FTS chars
        safe = memory_engine._sanitize_fts_query('What do you know about "Python"?')
        assert safe  # Should produce something

    def test_sanitize_empty(self, memory_engine):
        assert memory_engine._sanitize_fts_query("") == ""
        assert memory_engine._sanitize_fts_query("   ") == ""

    def test_sanitize_preserves_hyphens(self, memory_engine):
        result = memory_engine._sanitize_fts_query("python-async")
        assert result  # Should not be empty


# ── Hybrid Search Tests ────────────────────────────────────────────


@pytest.fixture
def hybrid_engine(tmp_path: Path):
    """Provide a MemoryEngine with VectorStore + TextEmbedder attached."""
    from backend.core.memory_engine import MemoryEngine
    from backend.core.vector_store import TextEmbedder, VectorStore

    db_path = tmp_path / "hybrid_mem.db"
    vec_path = tmp_path / "hybrid_vec.db"

    engine = MemoryEngine(db_path=db_path)
    engine.start()

    vs = VectorStore(db_path=vec_path)
    vs.start()

    embedder = TextEmbedder(dimension=128)
    embedder.fit([
        "machine learning algorithms for classification",
        "deep neural network architectures",
        "cooking pasta and italian recipes",
        "financial trading strategies for stocks",
        "python web framework comparison",
    ])

    engine.set_vector_store(vs, embedder)

    yield engine

    engine.stop()
    vs.stop()


class TestHybridSearchIntegration:
    """Tests for MemoryEngine.hybrid_search with real FTS5 + vector store."""

    def test_hybrid_search_returns_results(self, hybrid_engine):
        """Hybrid search should return entries that match either FTS5 or vector."""
        hybrid_engine.store(MemoryEntry(
            content="Machine learning is a subset of artificial intelligence",
            memory_type=MemoryType.FACT, source="test",
        ))
        hybrid_engine.store(MemoryEntry(
            content="Deep learning uses neural network architectures",
            memory_type=MemoryType.FACT, source="test",
        ))

        results = hybrid_engine.search(MemoryQuery(
            query="machine learning", hybrid=True, limit=10,
        ))
        assert len(results) >= 1
        assert any("machine learning" in r.content.lower() for r in results)

    def test_hybrid_false_uses_fts_only(self, hybrid_engine):
        """When hybrid=False, only FTS5 keyword search should run."""
        hybrid_engine.store(MemoryEntry(
            content="Python is a great programming language for scripting",
            memory_type=MemoryType.FACT, source="test",
        ))

        results = hybrid_engine.search(MemoryQuery(
            query="Python", hybrid=False, limit=10,
        ))
        assert len(results) >= 1
        # Should still find results via FTS
        assert any("Python" in r.content for r in results)

    def test_hybrid_search_deduplicates(self, hybrid_engine):
        """Same memory found by both FTS5 and vector should appear only once."""
        hybrid_engine.store(MemoryEntry(
            content="Financial trading strategies for stock markets",
            memory_type=MemoryType.FACT, source="test",
        ))

        results = hybrid_engine.search(MemoryQuery(
            query="financial trading strategies", hybrid=True, limit=10,
        ))
        ids = [r.id for r in results]
        assert len(ids) == len(set(ids)), "Duplicate IDs found in hybrid results"

    def test_hybrid_search_respects_limit(self, hybrid_engine):
        """Hybrid search should not return more than the requested limit."""
        for i in range(10):
            hybrid_engine.store(MemoryEntry(
                content=f"Unique fact number {i} about programming languages",
                memory_type=MemoryType.FACT, source="test",
            ))

        results = hybrid_engine.search(MemoryQuery(
            query="programming", hybrid=True, limit=3,
        ))
        assert len(results) <= 3

    def test_hybrid_search_respects_min_confidence(self, hybrid_engine):
        """Results below min_confidence should be excluded even from vector results."""
        hybrid_engine.store(MemoryEntry(
            content="Low confidence memory about uncertain programming facts",
            memory_type=MemoryType.FACT, source="test", confidence=0.1,
        ))
        hybrid_engine.store(MemoryEntry(
            content="High confidence memory about reliable programming facts",
            memory_type=MemoryType.FACT, source="test", confidence=0.9,
        ))

        results = hybrid_engine.search(MemoryQuery(
            query="programming facts", hybrid=True, min_confidence=0.5, limit=10,
        ))
        for r in results:
            assert r.confidence >= 0.5

    def test_hybrid_search_respects_memory_type_filter(self, hybrid_engine):
        """Hybrid search should filter by memory_type for both FTS and vector results."""
        hybrid_engine.store(MemoryEntry(
            content="A fact about algorithms and data structures",
            memory_type=MemoryType.FACT, source="test",
        ))
        hybrid_engine.store(MemoryEntry(
            content="A learning about algorithms and data structures",
            memory_type=MemoryType.LEARNING, source="test",
        ))

        results = hybrid_engine.search(MemoryQuery(
            query="algorithms", hybrid=True,
            memory_type=MemoryType.FACT, limit=10,
        ))
        for r in results:
            assert r.memory_type == MemoryType.FACT

    def test_hybrid_search_excludes_superseded(self, hybrid_engine):
        """Superseded memories should not appear in hybrid results."""
        old = hybrid_engine.store(MemoryEntry(
            content="Old knowledge about superseded web frameworks",
            memory_type=MemoryType.FACT, source="test",
        ))
        new_entry = MemoryEntry(
            content="Updated knowledge about current web frameworks",
            memory_type=MemoryType.FACT, source="test",
        )
        hybrid_engine.supersede(old.id, new_entry)

        results = hybrid_engine.search(MemoryQuery(
            query="web frameworks", hybrid=True, limit=10,
        ))
        for r in results:
            assert r.superseded_by is None

    def test_hybrid_boosts_entries_found_by_both(self, hybrid_engine):
        """Entries found by both FTS5 and vector should rank higher via RRF."""
        # Store two entries; the one matching both keyword and semantic should rank first
        hybrid_engine.store(MemoryEntry(
            content="Machine learning algorithms for classification tasks",
            memory_type=MemoryType.FACT, source="test",
        ))
        hybrid_engine.store(MemoryEntry(
            content="Cooking pasta is an art form in Italian cuisine",
            memory_type=MemoryType.FACT, source="test",
        ))

        results = hybrid_engine.search(MemoryQuery(
            query="machine learning classification", hybrid=True, limit=10,
        ))
        if len(results) >= 2:
            # The ML entry should rank above the cooking entry
            assert "machine learning" in results[0].content.lower()


class TestHybridSearchFallback:
    """Tests for fallback behavior when vector store is unavailable."""

    def test_no_vector_store_falls_back_to_fts(self, memory_engine):
        """When no vector store is attached, hybrid=True should still work via FTS5."""
        memory_engine.store(MemoryEntry(
            content="Fallback test for FTS only search without vectors",
            memory_type=MemoryType.FACT, source="test",
        ))

        results = memory_engine.search(MemoryQuery(
            query="fallback FTS", hybrid=True, limit=10,
        ))
        # Should not crash, should return FTS results
        assert len(results) >= 1

    def test_hybrid_search_falls_back_when_vector_search_empty(self, hybrid_engine):
        """hybrid_search returns FTS results even when vector search finds nothing."""
        hybrid_engine.store(MemoryEntry(
            content="Obscure fact about rare programming paradigms xyz",
            memory_type=MemoryType.FACT, source="test",
        ))

        # Query should hit FTS via keyword match on "xyz" even if vector
        # similarity is low — hybrid_search should still return results
        results = hybrid_engine.hybrid_search(MemoryQuery(
            query="xyz", hybrid=True, limit=10,
        ))
        assert len(results) >= 1


class TestVectorSearchHelper:
    """Tests for MemoryEngine._vector_search helper."""

    def test_vector_search_without_store_returns_empty(self, memory_engine):
        """_vector_search returns [] when no vector store is attached."""
        results = memory_engine._vector_search("anything", top_k=5)
        assert results == []

    def test_vector_search_returns_tuples(self, hybrid_engine):
        """_vector_search should return (id, score) tuples."""
        hybrid_engine.store(MemoryEntry(
            content="Test entry for vector search validation",
            memory_type=MemoryType.FACT, source="test",
        ))

        results = hybrid_engine._vector_search("test vector search", top_k=5)
        # May or may not find results depending on similarity threshold,
        # but should not crash
        assert isinstance(results, list)
        for item in results:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)
            assert isinstance(item[1], float)


class TestSemanticSearch:
    """Tests for MemoryEngine.semantic_search (pure vector search)."""

    def test_semantic_search_without_store_returns_empty(self, memory_engine):
        """semantic_search returns [] when no vector store is configured."""
        results = memory_engine.semantic_search("anything", top_k=5)
        assert results == []

    def test_semantic_search_returns_memory_entries(self, hybrid_engine):
        """semantic_search should return full MemoryEntry objects."""
        hybrid_engine.store(MemoryEntry(
            content="Semantic search test entry about neural networks",
            memory_type=MemoryType.FACT, source="test",
        ))

        results = hybrid_engine.semantic_search("neural networks", top_k=5)
        for r in results:
            assert isinstance(r, MemoryEntry)
            assert r.id is not None


class TestMemoryQueryModel:
    """Tests for the MemoryQuery hybrid field."""

    def test_hybrid_defaults_to_true(self):
        q = MemoryQuery(query="test")
        assert q.hybrid is True

    def test_hybrid_can_be_disabled(self):
        q = MemoryQuery(query="test", hybrid=False)
        assert q.hybrid is False
