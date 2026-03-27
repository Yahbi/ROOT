"""Tests for Knowledge Bootstrap — seeding ROOT's memory."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from backend.core.knowledge_bootstrap import CORE_KNOWLEDGE, bootstrap_memory
from backend.models.memory import MemoryType


# ── CORE_KNOWLEDGE corpus ──────────────────────────────────────


class TestCoreKnowledge:
    def test_corpus_not_empty(self):
        assert len(CORE_KNOWLEDGE) > 0

    def test_entries_have_correct_structure(self):
        for content, mem_type, tags, source in CORE_KNOWLEDGE:
            assert isinstance(content, str)
            assert len(content) > 0
            assert isinstance(mem_type, MemoryType)
            assert isinstance(tags, list)
            assert len(tags) > 0
            assert isinstance(source, str)

    def test_contains_root_identity(self):
        identity_entries = [
            c for c, _, tags, _ in CORE_KNOWLEDGE if "identity" in tags
        ]
        assert len(identity_entries) > 0

    def test_contains_hermes_knowledge(self):
        hermes_entries = [
            c for c, _, tags, _ in CORE_KNOWLEDGE if "hermes" in tags
        ]
        assert len(hermes_entries) > 0

    def test_contains_ecc_knowledge(self):
        ecc_entries = [c for c, _, tags, _ in CORE_KNOWLEDGE if "ecc" in tags]
        assert len(ecc_entries) > 0

    def test_contains_miro_knowledge(self):
        miro_entries = [c for c, _, tags, _ in CORE_KNOWLEDGE if "miro" in tags]
        assert len(miro_entries) > 0

    def test_contains_trading_knowledge(self):
        trading_entries = [
            c for c, _, tags, _ in CORE_KNOWLEDGE if "trading" in tags
        ]
        assert len(trading_entries) > 0

    def test_contains_openclaw_knowledge(self):
        openclaw_entries = [
            c for c, _, tags, _ in CORE_KNOWLEDGE if "openclaw" in tags
        ]
        assert len(openclaw_entries) > 0

    def test_contains_goals(self):
        goal_entries = [
            (c, mt) for c, mt, _, _ in CORE_KNOWLEDGE if mt == MemoryType.GOAL
        ]
        assert len(goal_entries) > 0

    def test_contains_facts(self):
        fact_entries = [
            (c, mt) for c, mt, _, _ in CORE_KNOWLEDGE if mt == MemoryType.FACT
        ]
        assert len(fact_entries) > 0

    def test_contains_learnings(self):
        learning_entries = [
            (c, mt) for c, mt, _, _ in CORE_KNOWLEDGE if mt == MemoryType.LEARNING
        ]
        assert len(learning_entries) > 0

    def test_contains_mission_bootstrap(self):
        mission_entries = [
            c for c, _, _, source in CORE_KNOWLEDGE if source == "mission_bootstrap"
        ]
        assert len(mission_entries) > 0


# ── bootstrap_memory function ──────────────────────────────────


class TestBootstrapMemory:
    def test_bootstrap_stores_all_entries(self, memory_engine):
        stored = bootstrap_memory(memory_engine)
        assert stored == len(CORE_KNOWLEDGE)
        assert memory_engine.count() == len(CORE_KNOWLEDGE)

    def test_bootstrap_skips_when_already_populated(self, memory_engine):
        # First bootstrap
        bootstrap_memory(memory_engine)
        count_after_first = memory_engine.count()

        # Second bootstrap should skip
        stored = bootstrap_memory(memory_engine)
        assert stored == 0
        assert memory_engine.count() == count_after_first

    def test_bootstrap_returns_count(self, memory_engine):
        count = bootstrap_memory(memory_engine)
        assert count == len(CORE_KNOWLEDGE)
        assert count > 0

    def test_bootstrap_entries_have_high_confidence(self, memory_engine):
        bootstrap_memory(memory_engine)
        from backend.models.memory import MemoryQuery
        results = memory_engine.search(
            MemoryQuery(query="ROOT", limit=5)
        )
        for entry in results:
            assert entry.confidence >= 0.9

    def test_bootstrap_entries_searchable(self, memory_engine):
        bootstrap_memory(memory_engine)
        from backend.models.memory import MemoryQuery
        # Search for HERMES knowledge
        results = memory_engine.search(
            MemoryQuery(query="HERMES self-improving agent", limit=5)
        )
        assert len(results) > 0

    def test_bootstrap_partial_population(self, memory_engine):
        """If memory has some entries but fewer than CORE_KNOWLEDGE, it should re-bootstrap."""
        from backend.models.memory import MemoryEntry
        # Add a few entries (fewer than CORE_KNOWLEDGE)
        for i in range(3):
            memory_engine.store(MemoryEntry(
                content=f"Pre-existing entry {i}",
                memory_type=MemoryType.FACT,
                tags=["pre-existing"],
            ))
        # Should still bootstrap since count < len(CORE_KNOWLEDGE)
        stored = bootstrap_memory(memory_engine)
        assert stored == len(CORE_KNOWLEDGE)


# ── Edge cases ─────────────────────────────────────────────────


class TestEdgeCases:
    def test_all_memory_types_used(self):
        """Verify the corpus uses diverse memory types."""
        types_used = {mt for _, mt, _, _ in CORE_KNOWLEDGE}
        assert MemoryType.FACT in types_used
        assert MemoryType.LEARNING in types_used
        assert MemoryType.GOAL in types_used

    def test_all_entries_have_source(self):
        sources = {source for _, _, _, source in CORE_KNOWLEDGE}
        assert len(sources) > 1  # Multiple sources

    def test_no_empty_tags(self):
        for _, _, tags, _ in CORE_KNOWLEDGE:
            assert all(len(t) > 0 for t in tags)

    def test_no_empty_content(self):
        for content, _, _, _ in CORE_KNOWLEDGE:
            assert len(content.strip()) > 10  # Meaningful content
