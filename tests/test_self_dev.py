"""Tests for the Self-Development Engine — ROOT's evolution tracking."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from unittest.mock import MagicMock, patch

from backend.core.self_dev import EvolutionEntry, SelfDevEngine
from backend.models.memory import MemoryType


@pytest.fixture
def mock_skills(tmp_path):
    """Provide a mock SkillEngine."""
    skills = MagicMock()
    skills.list_categories.return_value = {
        "agent-orchestration": [],
        "self-improvement": [],
        "coding-standards": [],
    }
    skills.stats.return_value = {"total": 5, "categories": {"agent-orchestration": 2, "self-improvement": 3}}
    skill_obj = MagicMock()
    skill_obj.path = str(tmp_path / "skills" / "test.md")
    skills.create_skill.return_value = skill_obj
    return skills


@pytest.fixture
def self_dev(memory_engine, mock_skills, tmp_path):
    """Provide a SelfDevEngine with temp data."""
    evo_log = tmp_path / "evolution_log.json"
    with patch("backend.core.self_dev.EVOLUTION_LOG", evo_log):
        engine = SelfDevEngine(memory=memory_engine, skills=mock_skills)
        yield engine


# ── EvolutionEntry ─────────────────────────────────────────────


class TestEvolutionEntry:
    def test_frozen(self):
        e = EvolutionEntry(id="e1", action_type="skill_created", description="test")
        with pytest.raises(AttributeError):
            e.description = "changed"  # type: ignore[misc]

    def test_defaults(self):
        e = EvolutionEntry(id="e1", action_type="test", description="d")
        assert e.details == {}
        assert e.impact_score == 0.0
        assert e.timestamp  # auto-populated


# ── Skill creation ─────────────────────────────────────────────


class TestCreateSkill:
    def test_create_skill_from_pattern(self, self_dev, memory_engine, mock_skills):
        entry = self_dev.create_skill_from_pattern(
            name="test-skill",
            category="testing",
            description="A test skill",
            content="# Test\nSteps...",
            tags=["test"],
        )
        assert isinstance(entry, EvolutionEntry)
        assert entry.action_type == "skill_created"
        assert entry.impact_score == 0.5
        assert "test-skill" in entry.description
        mock_skills.create_skill.assert_called_once()

    def test_create_skill_stores_in_memory(self, self_dev, memory_engine):
        before = memory_engine.count()
        self_dev.create_skill_from_pattern(
            name="mem-skill", category="cat", description="desc", content="content",
        )
        after = memory_engine.count()
        assert after > before

    def test_create_skill_logged_in_evolution(self, self_dev):
        self_dev.create_skill_from_pattern(
            name="evo-skill", category="cat", description="desc", content="c",
        )
        log = self_dev.get_evolution_log()
        assert len(log) >= 1
        assert log[0].action_type == "skill_created"


# ── Knowledge absorption ──────────────────────────────────────


class TestAbsorbFromFile:
    def test_absorb_existing_file(self, self_dev, tmp_path, memory_engine):
        f = tmp_path / "knowledge.txt"
        f.write_text("Important knowledge about AI systems and automation.")
        before = memory_engine.count()
        entry = self_dev.absorb_from_file(str(f))
        assert entry.action_type == "knowledge_absorbed"
        assert entry.impact_score == 0.3
        assert memory_engine.count() > before

    def test_absorb_missing_file(self, self_dev):
        entry = self_dev.absorb_from_file("/nonexistent/file.txt")
        assert entry.action_type == "knowledge_absorbed"
        assert entry.impact_score == -0.1
        assert "not found" in entry.description


# ── Gap analysis ───────────────────────────────────────────────


class TestIdentifyGaps:
    def test_identifies_missing_skill_categories(self, self_dev, mock_skills):
        # Only 3 categories present out of 10 expected
        gaps = self_dev.identify_gaps()
        skill_gaps = [g for g in gaps if g["area"].startswith("skill_")]
        assert len(skill_gaps) > 0

    def test_identifies_low_memory_types(self, self_dev, memory_engine):
        # No memories stored yet — all types should be flagged
        gaps = self_dev.identify_gaps()
        mem_gaps = [g for g in gaps if g["area"].startswith("memory_")]
        assert len(mem_gaps) > 0

    def test_no_gap_when_categories_present(self, self_dev, mock_skills):
        # Provide all expected categories
        expected = {
            "agent-orchestration", "self-improvement", "coding-standards",
            "security", "llm-inference", "swarm-simulation", "trading",
            "multi-platform", "data-analysis", "automation",
        }
        mock_skills.list_categories.return_value = {cat: [] for cat in expected}
        gaps = self_dev.identify_gaps()
        skill_gaps = [g for g in gaps if g["area"].startswith("skill_")]
        assert len(skill_gaps) == 0


# ── Self-assessment ────────────────────────────────────────────


class TestAssess:
    def test_assess_returns_required_fields(self, self_dev):
        result = self_dev.assess()
        assert "maturity_score" in result
        assert "maturity_level" in result
        assert "memories" in result
        assert "skills" in result
        assert "evolution_count" in result
        assert "capability_gaps" in result
        assert "recent_evolution" in result

    def test_maturity_score_in_range(self, self_dev):
        result = self_dev.assess()
        assert 0.0 <= result["maturity_score"] <= 1.0

    def test_maturity_level_embryonic_when_empty(self, self_dev):
        result = self_dev.assess()
        # With minimal data, should be low maturity
        assert result["maturity_level"] in ("embryonic", "nascent", "developing")

    def test_maturity_level_increases_with_data(self, self_dev, memory_engine, mock_skills):
        from backend.models.memory import MemoryEntry
        # Add many memories
        for i in range(200):
            memory_engine.store(MemoryEntry(
                content=f"Memory {i}", memory_type=MemoryType.FACT, tags=["test"],
            ))
        # Add many skills
        mock_skills.stats.return_value = {"total": 30, "categories": {}}
        # Add evolution entries
        for i in range(35):
            self_dev._evolution_log.append(
                EvolutionEntry(id=f"e{i}", action_type="skill_created", description=f"test {i}")
            )
        # All categories present
        expected = {
            "agent-orchestration", "self-improvement", "coding-standards",
            "security", "llm-inference", "swarm-simulation", "trading",
            "multi-platform", "data-analysis", "automation",
        }
        mock_skills.list_categories.return_value = {cat: [] for cat in expected}

        result = self_dev.assess()
        assert result["maturity_score"] > 0.5

    def test_recent_evolution_in_assessment(self, self_dev):
        self_dev.create_skill_from_pattern(
            name="s1", category="c", description="d", content="c",
        )
        result = self_dev.assess()
        assert len(result["recent_evolution"]) >= 1


# ── Propose improvement ────────────────────────────────────────


class TestProposeImprovement:
    def test_propose_creates_evolution_entry(self, self_dev):
        entry = self_dev.propose_improvement(
            area="memory", description="Add more fact memories", rationale="Coverage is low",
        )
        assert entry.action_type == "code_proposed"
        assert entry.impact_score == 0.0
        assert "memory" in entry.description

    def test_propose_stores_in_memory(self, self_dev, memory_engine):
        before = memory_engine.count()
        self_dev.propose_improvement(area="x", description="d", rationale="r")
        assert memory_engine.count() > before


# ── Evolution log ──────────────────────────────────────────────


class TestEvolutionLog:
    def test_get_evolution_log_empty(self, self_dev):
        log = self_dev.get_evolution_log()
        assert log == []

    def test_get_evolution_log_ordered(self, self_dev):
        self_dev.create_skill_from_pattern(name="s1", category="c", description="first", content="c")
        self_dev.create_skill_from_pattern(name="s2", category="c", description="second", content="c")
        log = self_dev.get_evolution_log()
        assert len(log) == 2
        # Most recent first
        assert "second" in log[0].description

    def test_get_evolution_log_limit(self, self_dev):
        for i in range(10):
            self_dev._evolution_log.append(
                EvolutionEntry(id=f"e{i}", action_type="test", description=f"entry {i}")
            )
        assert len(self_dev.get_evolution_log(limit=3)) == 3

    def test_evolution_stats(self, self_dev):
        self_dev._evolution_log = [
            EvolutionEntry(id="e1", action_type="skill_created", description="a", impact_score=0.5),
            EvolutionEntry(id="e2", action_type="skill_created", description="b", impact_score=0.5),
            EvolutionEntry(id="e3", action_type="code_proposed", description="c", impact_score=0.0),
        ]
        stats = self_dev.get_evolution_stats()
        assert stats["total_entries"] == 3
        assert stats["by_type"]["skill_created"] == 2
        assert stats["by_type"]["code_proposed"] == 1
        assert stats["net_impact"] == 1.0


# ── Persistence ────────────────────────────────────────────────


class TestPersistence:
    def test_save_and_load_log(self, memory_engine, mock_skills, tmp_path):
        evo_log = tmp_path / "evo_persist.json"
        with patch("backend.core.self_dev.EVOLUTION_LOG", evo_log):
            engine1 = SelfDevEngine(memory=memory_engine, skills=mock_skills)
            engine1._evolution_log.append(
                EvolutionEntry(id="e1", action_type="test", description="persisted")
            )
            engine1._save_log()

            # Create new engine, should load from file
            engine2 = SelfDevEngine(memory=memory_engine, skills=mock_skills)
            assert len(engine2._evolution_log) == 1
            assert engine2._evolution_log[0].id == "e1"
            assert engine2._evolution_log[0].description == "persisted"

    def test_load_corrupt_file(self, memory_engine, mock_skills, tmp_path):
        evo_log = tmp_path / "corrupt.json"
        evo_log.write_text("not valid json {{{")
        with patch("backend.core.self_dev.EVOLUTION_LOG", evo_log):
            engine = SelfDevEngine(memory=memory_engine, skills=mock_skills)
            # Should not crash, just have empty log
            assert engine._evolution_log == []
