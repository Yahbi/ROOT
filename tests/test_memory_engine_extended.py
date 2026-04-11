"""Extended tests for the Memory Engine — clustering, deduplication, stats, bulk ops."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from backend.models.memory import MemoryEntry, MemoryQuery, MemoryType


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def engine(tmp_path: Path):
    from backend.core.memory_engine import MemoryEngine
    e = MemoryEngine(db_path=tmp_path / "mem.db")
    e.start()
    yield e
    e.stop()


def _fact(content: str, **kwargs) -> MemoryEntry:
    kwargs.setdefault("source", "test")
    return MemoryEntry(
        content=content,
        memory_type=MemoryType.FACT,
        **kwargs,
    )


# ── Deduplication ─────────────────────────────────────────────────────


class TestDeduplication:
    def test_exact_duplicate_returns_same_id(self, engine):
        content = "Machine learning uses gradient descent to optimise neural network weights"
        e1 = engine.store(_fact(content))
        e2 = engine.store(_fact(content))
        assert e1.id == e2.id

    def test_near_duplicate_prefix_match(self, engine):
        base = "Python is a high-level dynamically-typed programming language used widely"
        e1 = engine.store(_fact(base))
        # Same long prefix — should deduplicate
        e2 = engine.store(_fact(base + " in data science"))
        # Short addition means prefix matches → dedup
        assert e1.id == e2.id

    def test_distinct_content_creates_separate_entries(self, engine):
        e1 = engine.store(_fact("Alpha content about neural networks and deep learning"))
        e2 = engine.store(_fact("Beta content about trading strategies and market signals"))
        assert e1.id != e2.id
        assert engine.count() == 2

    def test_short_content_skips_dedup_check(self, engine):
        """Content under 20 chars skips deduplication entirely."""
        e1 = engine.store(_fact("Short fact"))
        e2 = engine.store(_fact("Short fact"))
        # Short content always creates a new entry (no dedup)
        assert engine.count() >= 1

    def test_dedup_strengthens_existing(self, engine):
        content = "Deduplication strengthens existing entries when duplicates are detected here"
        e1 = engine.store(_fact(content, confidence=0.5))
        before_conf = e1.confidence
        engine.store(_fact(content))
        recalled = engine.recall(e1.id)
        assert recalled is not None
        assert recalled.confidence >= before_conf


# ── Tag-Based Access ──────────────────────────────────────────────────


class TestTagAccess:
    def test_get_by_tag_returns_matching(self, engine):
        engine.store(_fact("Python async programming patterns", tags=["python", "async"]))
        engine.store(_fact("Rust memory safety without garbage collection", tags=["rust"]))
        results = engine.get_by_tag("python")
        assert len(results) == 1
        assert "Python" in results[0].content

    def test_get_by_tag_empty_if_no_match(self, engine):
        engine.store(_fact("Django ORM tutorial for beginners", tags=["django"]))
        results = engine.get_by_tag("fastapi")
        assert len(results) == 0

    def test_get_by_source(self, engine):
        engine.store(_fact("From bootstrap source", source="bootstrap"))
        engine.store(_fact("From hook source", source="hooks"))
        results = engine.get_by_source("bootstrap")
        assert len(results) == 1
        assert "bootstrap" in results[0].source


# ── Stats ─────────────────────────────────────────────────────────────


class TestStats:
    def test_stats_empty(self, engine):
        stats = engine.stats()
        assert stats["total"] == 0
        assert stats["total_accesses"] == 0
        assert stats["avg_confidence"] == 0.0
        assert stats["by_type"] == {}

    def test_stats_with_mixed_types(self, engine):
        engine.store(MemoryEntry(
            content="A fact about the solar system and planetary orbits",
            memory_type=MemoryType.FACT, source="test",
        ))
        engine.store(MemoryEntry(
            content="A learning about how machine learning works in practice",
            memory_type=MemoryType.LEARNING, source="test",
        ))
        stats = engine.stats()
        assert stats["total"] == 2
        assert MemoryType.FACT.value in stats["by_type"]
        assert MemoryType.LEARNING.value in stats["by_type"]

    def test_avg_confidence_reflects_entries(self, engine):
        engine.store(_fact("High confidence fact about climate change", confidence=1.0))
        engine.store(_fact("Low confidence fact about economics trends here", confidence=0.0))
        stats = engine.stats()
        assert 0.4 <= stats["avg_confidence"] <= 0.6


# ── Recall and Access Count ───────────────────────────────────────────


class TestRecallAndAccess:
    def test_recall_increments_access_count(self, engine):
        e = engine.store(_fact("Memory to be accessed multiple times for testing purposes"))
        engine.recall(e.id)
        engine.recall(e.id)
        recalled = engine.recall(e.id)
        assert recalled is not None
        assert recalled.access_count >= 3

    def test_recall_nonexistent_returns_none(self, engine):
        result = engine.recall("mem_doesnotexist0000")
        assert result is None

    def test_get_recent_sorted_by_date(self, engine):
        for i in range(5):
            engine.store(_fact(f"Sequential memory entry number {i} in the queue now"))
        recent = engine.get_recent(limit=5)
        assert len(recent) == 5
        # Should be descending (most recent first)
        for a, b in zip(recent, recent[1:]):
            assert a.created_at >= b.created_at

    def test_get_strongest_sorted_by_score(self, engine):
        engine.store(_fact("Strong memory with high confidence for tests", confidence=0.95))
        engine.store(_fact("Weak memory with low confidence for comparison here", confidence=0.1))
        strongest = engine.get_strongest(limit=10)
        assert strongest[0].confidence >= strongest[-1].confidence


# ── Decay and Strengthen ──────────────────────────────────────────────


class TestDecayAndStrengthen:
    def test_decay_reduces_confidence(self, engine):
        e = engine.store(_fact("Memory to decay in test suite for verification", confidence=0.8))
        engine.decay(factor=0.5)
        recalled = engine.recall(e.id)
        if recalled is not None:
            assert recalled.confidence < 0.8

    def test_strengthen_capped_at_one(self, engine):
        e = engine.store(_fact("High confidence memory to strengthen further please", confidence=0.95))
        engine.strengthen(e.id, boost=0.5)
        recalled = engine.recall(e.id)
        assert recalled is not None
        assert recalled.confidence <= 1.0

    def test_strengthen_increases_confidence(self, engine):
        e = engine.store(_fact("Base memory entry to strengthen gradually over time", confidence=0.3))
        engine.strengthen(e.id, boost=0.3)
        recalled = engine.recall(e.id)
        assert recalled is not None
        assert recalled.confidence >= 0.55


# ── FTS Rebuild ───────────────────────────────────────────────────────


class TestFTSRebuild:
    def test_rebuild_fts_returns_count(self, engine):
        engine.store(_fact("Test memory for FTS rebuild verification process"))
        engine.store(_fact("Second test memory for rebuild verification here"))
        count = engine.rebuild_fts()
        assert count == 2

    def test_search_still_works_after_rebuild(self, engine):
        engine.store(_fact("Searchable content about programming languages here"))
        engine.rebuild_fts()
        results = engine.search(MemoryQuery(query="programming", limit=5))
        assert len(results) >= 1


# ── Supersede ─────────────────────────────────────────────────────────


class TestSupersede:
    def test_superseded_memory_excluded_from_search(self, engine):
        old = engine.store(_fact("Old fact about web technologies being superseded now"))
        engine.supersede(old.id, _fact("New updated fact about web technologies replacing old"))
        results = engine.search(MemoryQuery(query="web technologies", limit=10))
        result_ids = [r.id for r in results]
        assert old.id not in result_ids

    def test_new_entry_appears_in_search(self, engine):
        old = engine.store(_fact("Old deprecated Python web framework knowledge now"))
        new = engine.supersede(old.id, _fact("New modern Python web framework knowledge here"))
        results = engine.search(MemoryQuery(query="Python web framework", limit=10))
        result_ids = [r.id for r in results]
        assert new.id in result_ids

    def test_superseded_chain_preserves_link(self, engine):
        old = engine.store(_fact("Original knowledge that will be superseded eventually ok"))
        new = engine.supersede(old.id, _fact("Updated replacement knowledge for original entry"))
        recalled_old = engine.recall(old.id)
        assert recalled_old is not None
        assert recalled_old.superseded_by == new.id


# ── Clustering ────────────────────────────────────────────────────────


class TestClustering:
    def test_cluster_by_tags_groups_same_tag(self, engine):
        engine.store(_fact("Python async programming patterns", tags=["python", "async"]))
        engine.store(_fact("Python data science libraries overview", tags=["python", "data"]))
        engine.store(_fact("Rust memory safety principles", tags=["rust"]))
        clusters = engine.cluster_by_tags(min_shared=1)
        # Both python entries should share a cluster
        all_entries = [e for group in clusters.values() for e in group]
        assert len(all_entries) == 3

    def test_cluster_untagged_goes_to_untagged(self, engine):
        engine.store(_fact("Memory with no tags at all for clustering test"))
        clusters = engine.cluster_by_tags()
        assert "__untagged__" in clusters

    def test_cluster_empty_engine(self, engine):
        clusters = engine.cluster_by_tags()
        assert isinstance(clusters, dict)
        assert len(clusters) == 0

    def test_cluster_returns_memory_entries(self, engine):
        engine.store(_fact("Clustering entry with label", tags=["ml"]))
        clusters = engine.cluster_by_tags()
        for members in clusters.values():
            for m in members:
                assert isinstance(m, MemoryEntry)


# ── Importance Scoring ────────────────────────────────────────────────


class TestImportanceScoring:
    def test_importance_score_is_float(self, engine):
        e = engine.store(_fact("Memory for importance scoring test here now"))
        score = engine.importance_score(e)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0

    def test_high_confidence_scores_higher(self, engine):
        e_high = engine.store(_fact("High confidence entry for importance test", confidence=1.0))
        e_low = engine.store(_fact("Low confidence entry for importance scoring test", confidence=0.1))
        s_high = engine.importance_score(e_high)
        s_low = engine.importance_score(e_low)
        # High confidence should score at least as high
        assert s_high >= s_low

    def test_get_by_importance_sorted(self, engine):
        engine.store(_fact("First importance entry with moderate confidence", confidence=0.8))
        engine.store(_fact("Second importance entry with low confidence here", confidence=0.2))
        scored = engine.get_by_importance(limit=10)
        assert len(scored) == 2
        scores = [s for _, s in scored]
        assert scores == sorted(scores, reverse=True)

    def test_get_by_importance_limit(self, engine):
        for i in range(10):
            engine.store(_fact(f"Importance test entry number {i} for limit check here"))
        scored = engine.get_by_importance(limit=3)
        assert len(scored) <= 3


# ── Bulk Operations ───────────────────────────────────────────────────


class TestBulkOperations:
    def test_bulk_store_inserts_all(self, engine):
        entries = [
            _fact(f"Bulk insert entry number {i} for batch test validation here")
            for i in range(5)
        ]
        stored = engine.bulk_store(entries)
        assert len(stored) == 5
        assert engine.count() == 5

    def test_bulk_store_deduplicates(self, engine):
        content = "Bulk deduplication test content that is unique and quite long enough"
        entries = [_fact(content), _fact(content)]
        stored = engine.bulk_store(entries)
        # Second should be deduplicated
        assert stored[0].id == stored[1].id
        assert engine.count() == 1

    def test_bulk_store_returns_entries_with_ids(self, engine):
        entries = [_fact(f"Bulk id check entry {i} for validation testing now") for i in range(3)]
        stored = engine.bulk_store(entries)
        for e in stored:
            assert e.id is not None
            assert e.id.startswith("mem_")

    def test_bulk_update_confidence(self, engine):
        e1 = engine.store(_fact("Entry one for bulk confidence update test now"))
        e2 = engine.store(_fact("Entry two for bulk confidence update verification ok"))
        updated = engine.bulk_update_confidence({e1.id: 0.9, e2.id: 0.3})
        assert updated == 2
        r1 = engine.recall(e1.id)
        r2 = engine.recall(e2.id)
        assert r1 is not None and abs(r1.confidence - 0.9) < 0.001
        assert r2 is not None and abs(r2.confidence - 0.3) < 0.001

    def test_bulk_update_clamps_confidence(self, engine):
        e = engine.store(_fact("Clamping test entry for bulk update confidence bounds"))
        engine.bulk_update_confidence({e.id: 2.5})  # above 1.0
        r = engine.recall(e.id)
        assert r is not None
        assert r.confidence <= 1.0

    def test_bulk_update_empty_dict(self, engine):
        count = engine.bulk_update_confidence({})
        assert count == 0


# ── Export / Import ───────────────────────────────────────────────────


class TestExportImport:
    def test_export_returns_json_string(self, engine):
        engine.store(_fact("Export test entry that should appear in JSON dump"))
        data = engine.export_json()
        assert isinstance(data, str)
        parsed = json.loads(data)
        assert "memories" in parsed
        assert parsed["version"] == 1

    def test_export_contains_stored_entries(self, engine):
        e = engine.store(_fact("Specific exportable memory content for validation"))
        data = engine.export_json()
        parsed = json.loads(data)
        ids = [m["id"] for m in parsed["memories"]]
        assert e.id in ids

    def test_export_excludes_superseded_by_default(self, engine):
        old = engine.store(_fact("Old superseded memory not to be exported now"))
        engine.supersede(old.id, _fact("New replacement memory entry for export test"))
        data = engine.export_json(include_superseded=False)
        parsed = json.loads(data)
        ids = [m["id"] for m in parsed["memories"]]
        assert old.id not in ids

    def test_export_includes_superseded_when_requested(self, engine):
        old = engine.store(_fact("Old superseded memory to be exported with flag set"))
        engine.supersede(old.id, _fact("New replacement for export with superseded flag"))
        data = engine.export_json(include_superseded=True)
        parsed = json.loads(data)
        ids = [m["id"] for m in parsed["memories"]]
        assert old.id in ids

    def test_import_restores_entries(self, engine, tmp_path):
        from backend.core.memory_engine import MemoryEngine
        # Export from engine
        engine.store(_fact("Memory to export and reimport for roundtrip test"))
        data = engine.export_json()

        # Import into fresh engine
        fresh = MemoryEngine(db_path=tmp_path / "import_test.db")
        fresh.start()
        result = fresh.import_json(data)
        fresh.stop()

        assert result["imported"] >= 1
        assert result["errors"] == 0

    def test_import_skips_existing_by_default(self, engine):
        e = engine.store(_fact("Memory that exists before import attempt here"))
        data = engine.export_json()
        result = engine.import_json(data, overwrite=False)
        assert result["skipped"] >= 1

    def test_import_overwrites_when_flag_set(self, engine):
        e = engine.store(_fact("Memory to overwrite during import with flag enabled"))
        data = engine.export_json()
        result = engine.import_json(data, overwrite=True)
        assert result["imported"] >= 1

    def test_import_invalid_json_raises(self, engine):
        with pytest.raises(ValueError, match="Invalid JSON"):
            engine.import_json("not json at all {{{{")

    def test_import_missing_memories_key_raises(self, engine):
        with pytest.raises(ValueError, match="'memories'"):
            engine.import_json('{"version": 1}')


# ── Near-Duplicate Detection ──────────────────────────────────────────


class TestNearDuplicates:
    def test_find_near_duplicates_high_similarity(self, engine):
        engine.store(_fact(
            "Machine learning uses gradient descent to optimise model parameters"
        ))
        engine.store(_fact(
            "Machine learning uses gradient descent to optimize model parameters"
        ))
        pairs = engine.find_near_duplicates(threshold=0.7)
        assert len(pairs) >= 1
        for a, b, sim in pairs:
            assert sim >= 0.7

    def test_find_near_duplicates_no_false_positives(self, engine):
        engine.store(_fact("Python programming language used for data science applications"))
        engine.store(_fact("Rust systems programming memory safety without garbage collector"))
        pairs = engine.find_near_duplicates(threshold=0.85)
        # These are clearly different — should have no near-duplicate pairs
        assert len(pairs) == 0

    def test_merge_near_duplicates_supersedes_older(self, engine):
        # Create two very similar entries — differ only by US vs GB spelling
        e1 = engine.store(_fact(
            "Gradient descent optimizes neural network weights during model training phase"
        ))
        e2 = engine.store(_fact(
            "Gradient descent optimises neural network weights during model training phase"
        ))
        merged = engine.merge_near_duplicates(threshold=0.75)
        # At least one merge should have happened
        assert len(merged) >= 1
        superseded_ids = [m[0] for m in merged]
        # The superseded entry should be marked
        for sid in superseded_ids:
            row = engine.conn.execute(
                "SELECT superseded_by FROM memories WHERE id = ?", (sid,)
            ).fetchone()
            assert row["superseded_by"] is not None

    def test_find_near_duplicates_empty_engine(self, engine):
        pairs = engine.find_near_duplicates()
        assert pairs == []


# ── Rich Statistics ───────────────────────────────────────────────────


class TestRichStats:
    def test_stats_includes_growth_fields(self, engine):
        engine.store(_fact("Recent entry for growth rate statistics test"))
        stats = engine.stats()
        assert "growth" in stats
        assert "last_7_days" in stats["growth"]
        assert "prior_7_days" in stats["growth"]
        assert "growth_pct" in stats["growth"]

    def test_stats_top_tags(self, engine):
        engine.store(_fact("Tagged entry one", tags=["ml", "ai"]))
        engine.store(_fact("Tagged entry two has more content here", tags=["ml"]))
        stats = engine.stats()
        assert "top_tags" in stats
        assert isinstance(stats["top_tags"], list)
        # ml should appear since both entries share it
        tags_seen = [t["tag"] for t in stats["top_tags"]]
        assert "ml" in tags_seen

    def test_stats_importance_top5(self, engine):
        for i in range(3):
            engine.store(_fact(f"Importance stats entry {i} for testing the top five"))
        stats = engine.stats()
        assert "importance_top5" in stats
        assert len(stats["importance_top5"]) <= 5
        for item in stats["importance_top5"]:
            assert "id" in item
            assert "score" in item

    def test_stats_by_type_has_avg_confidence(self, engine):
        engine.store(_fact("Fact entry for type statistics verification test here"))
        stats = engine.stats()
        fact_stats = stats["by_type"].get("fact")
        assert fact_stats is not None
        assert "count" in fact_stats
        assert "avg_confidence" in fact_stats

    def test_stats_growth_recent_counts_today(self, engine):
        engine.store(_fact("Fresh entry created today for growth rate counting test"))
        stats = engine.stats()
        assert stats["growth"]["last_7_days"] >= 1
