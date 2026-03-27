"""Tests for the Memory Engine — FTS5 search, dedup, decay, strengthen."""

from __future__ import annotations

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
