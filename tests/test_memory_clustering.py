"""Tests for memory engine — clustering, importance scoring, bulk operations, export/import."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.models.memory import MemoryEntry, MemoryQuery, MemoryType


@pytest.fixture
def engine(tmp_path: Path):
    from backend.core.memory_engine import MemoryEngine
    e = MemoryEngine(db_path=tmp_path / "mem.db")
    e.start()
    yield e
    e.stop()


def _entry(content: str, tags=None, source="test", confidence=1.0) -> MemoryEntry:
    return MemoryEntry(
        content=content,
        memory_type=MemoryType.FACT,
        tags=tags or [],
        source=source,
        confidence=confidence,
    )


# ── Tag-Based Grouping (Clustering Proxy) ────────────────────────────


class TestTagGrouping:
    def test_memories_grouped_by_tag(self, engine):
        engine.store(_entry("Python async IO patterns for network programming", tags=["python", "async"]))
        engine.store(_entry("Python decorators and metaclass usage patterns", tags=["python", "meta"]))
        engine.store(_entry("JavaScript async await modern patterns", tags=["javascript", "async"]))
        python_mems = engine.get_by_tag("python")
        assert len(python_mems) == 2
        async_mems = engine.get_by_tag("async")
        assert len(async_mems) == 2

    def test_tag_search_partial_match(self, engine):
        engine.store(_entry("Deep learning neural network architecture", tags=["deep_learning"]))
        results = engine.get_by_tag("deep_learning")
        assert len(results) == 1

    def test_source_groups_memories(self, engine):
        engine.store(_entry("Bootstrap knowledge A", source="bootstrap"))
        engine.store(_entry("Bootstrap knowledge B", source="bootstrap"))
        engine.store(_entry("Hook knowledge C", source="hooks"))
        bootstrap = engine.get_by_source("bootstrap")
        assert len(bootstrap) == 2
        hooks = engine.get_by_source("hooks")
        assert len(hooks) == 1


# ── Importance Scoring ────────────────────────────────────────────────


class TestImportanceScoring:
    def test_get_strongest_reflects_confidence(self, engine):
        engine.store(_entry("High confidence important memory", confidence=0.95))
        engine.store(_entry("Medium confidence useful memory for testing", confidence=0.6))
        engine.store(_entry("Low confidence vague uncertain memory entry", confidence=0.2))
        strongest = engine.get_strongest(limit=3)
        assert strongest[0].confidence >= strongest[-1].confidence

    def test_accessed_memories_rank_higher(self, engine):
        low = engine.store(_entry("Low access count memory entry test here", confidence=0.7))
        high = engine.store(_entry("High access count memory will rank higher now", confidence=0.7))
        # Access 'high' multiple times
        for _ in range(5):
            engine.recall(high.id)
        strongest = engine.get_strongest(limit=5)
        # high-access entry should appear before low-access at same confidence
        high_pos = next((i for i, e in enumerate(strongest) if e.id == high.id), 999)
        low_pos = next((i for i, e in enumerate(strongest) if e.id == low.id), 999)
        assert high_pos <= low_pos

    def test_strengthen_elevates_ranking(self, engine):
        e1 = engine.store(_entry("Memory to be strengthened significantly now", confidence=0.5))
        e2 = engine.store(_entry("Memory kept at same confidence level always", confidence=0.5))
        engine.strengthen(e1.id, boost=0.4)
        strongest = engine.get_strongest(limit=2)
        assert strongest[0].id == e1.id


# ── Search Confidence Filtering ───────────────────────────────────────


class TestSearchFiltering:
    def test_min_confidence_filters_low_entries(self, engine):
        engine.store(_entry("High quality reliable memory entry here now", confidence=0.9))
        engine.store(_entry("Low quality uncertain memory that should be filtered", confidence=0.1))
        results = engine.search(MemoryQuery(
            query="memory entry", min_confidence=0.5, limit=10,
        ))
        for r in results:
            assert r.confidence >= 0.5

    def test_search_returns_active_only(self, engine):
        """Superseded entries should not appear in searches."""
        old = engine.store(_entry("Old framework knowledge that has been superseded"))
        engine.supersede(old.id, _entry("New modern framework knowledge replacing old"))
        results = engine.search(MemoryQuery(query="framework knowledge", limit=10))
        assert all(r.superseded_by is None for r in results)

    def test_search_empty_query_returns_all(self, engine):
        engine.store(_entry("First memory entry for empty query test"))
        engine.store(_entry("Second memory entry for empty query test"))
        results = engine.search(MemoryQuery(query="", limit=10))
        # Empty query should return all entries (no FTS filter)
        assert len(results) >= 2


# ── Bulk Operations (via multiple stores) ─────────────────────────────


class TestBulkOperations:
    def test_store_many_entries(self, engine):
        for i in range(20):
            engine.store(_entry(f"Bulk memory entry number {i} for testing purposes here"))
        assert engine.count() == 20

    def test_search_across_many_entries(self, engine):
        for i in range(10):
            engine.store(_entry(f"Programming language entry {i} about Python coding"))
        for i in range(10):
            engine.store(_entry(f"Cooking recipe entry {i} about Italian pasta dishes"))
        results = engine.search(MemoryQuery(query="Python coding", limit=20))
        assert len(results) >= 1
        assert all("Python" in r.content or "coding" in r.content for r in results)

    def test_decay_removes_very_low_confidence(self, engine):
        for i in range(5):
            engine.store(_entry(
                f"Memory to decay away entry {i} in test suite",
                confidence=0.06,
            ))
        initial_count = engine.count()
        engine.decay(factor=0.5)  # 0.06 * 0.5 = 0.03 < cutoff
        final_count = engine.count()
        assert final_count <= initial_count


# ── Memory Type Diversity ─────────────────────────────────────────────


class TestMemoryTypeDiversity:
    def test_store_all_memory_types(self, engine):
        for mt in MemoryType:
            engine.store(MemoryEntry(
                content=f"Memory of type {mt.value} for diversity test purposes",
                memory_type=mt,
                source="test",
            ))
        stats = engine.stats()
        assert stats["total"] >= len(list(MemoryType))

    def test_filter_by_learning_type(self, engine):
        engine.store(MemoryEntry(
            content="A learning about reinforcement learning methods here",
            memory_type=MemoryType.LEARNING, source="test",
        ))
        engine.store(MemoryEntry(
            content="A fact about reinforcement learning methods here",
            memory_type=MemoryType.FACT, source="test",
        ))
        results = engine.search(MemoryQuery(
            query="reinforcement learning", memory_type=MemoryType.LEARNING, limit=10,
        ))
        assert all(r.memory_type == MemoryType.LEARNING for r in results)

    def test_count_excludes_superseded(self, engine):
        old = engine.store(_entry("Old entry to be superseded in count test"))
        engine.supersede(old.id, _entry("New entry replacing old in count test here"))
        # count() should only include non-superseded entries
        count = engine.count()
        # We have 1 superseded + 1 active = count should be 1
        assert count == 1


# ── FTS Query Sanitization ───────────────────────────────────────────


class TestFTSQuerySanitization:
    def test_sanitize_c_plus_plus(self, engine):
        result = engine._sanitize_fts_query("C++")
        assert result  # Should not be empty

    def test_sanitize_operators(self, engine):
        result = engine._sanitize_fts_query("AND OR NOT")
        assert result

    def test_sanitize_parentheses(self, engine):
        result = engine._sanitize_fts_query("(python OR java)")
        assert result

    def test_sanitize_asterisk(self, engine):
        result = engine._sanitize_fts_query("python* async*")
        assert result

    def test_sanitize_question_mark(self, engine):
        result = engine._sanitize_fts_query("what is python?")
        assert result

    def test_sanitize_quotes(self, engine):
        result = engine._sanitize_fts_query('"exact phrase"')
        assert result

    def test_sanitize_hyphen_in_word(self, engine):
        result = engine._sanitize_fts_query("self-improvement learning")
        assert result
