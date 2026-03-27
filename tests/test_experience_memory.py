"""Tests for the Experience Memory — 3-layer memory system."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.experience_memory import ExperienceMemory, ExperienceType


@pytest.fixture
def exp_mem(tmp_path):
    with patch("backend.core.experience_memory.EXPERIENCE_DB", tmp_path / "experience.db"):
        engine = ExperienceMemory()
        engine.start()
        yield engine
        engine.stop()


class TestShortTermMemory:
    def test_store_and_retrieve(self, exp_mem: ExperienceMemory):
        entry = exp_mem.store_short_term("active task context")
        assert entry.id.startswith("stm_")
        entries = exp_mem.get_short_term()
        assert len(entries) == 1
        assert entries[0].content == "active task context"

    def test_filter_by_task(self, exp_mem: ExperienceMemory):
        exp_mem.store_short_term("task A context", task_id="task_001")
        exp_mem.store_short_term("task B context", task_id="task_002")
        entries = exp_mem.get_short_term(task_id="task_001")
        assert len(entries) == 1
        assert entries[0].task_id == "task_001"

    def test_clear_all(self, exp_mem: ExperienceMemory):
        exp_mem.store_short_term("a")
        exp_mem.store_short_term("b")
        cleared = exp_mem.clear_short_term()
        assert cleared == 2
        assert len(exp_mem.get_short_term()) == 0

    def test_clear_by_task(self, exp_mem: ExperienceMemory):
        exp_mem.store_short_term("a", task_id="t1")
        exp_mem.store_short_term("b", task_id="t2")
        cleared = exp_mem.clear_short_term(task_id="t1")
        assert cleared == 1
        assert len(exp_mem.get_short_term()) == 1

    def test_limit_enforced(self, exp_mem: ExperienceMemory):
        exp_mem.MAX_SHORT_TERM = 5
        for i in range(10):
            exp_mem.store_short_term(f"entry {i}")
        assert len(exp_mem.get_short_term()) <= 5


class TestExperienceRecording:
    def test_record_success(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_success(
            domain="trading", title="Momentum strategy worked",
            description="50% return in 3 months",
        )
        assert exp.id.startswith("exp_")
        assert exp.experience_type == ExperienceType.SUCCESS
        assert exp.domain == "trading"

    def test_record_failure(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_failure(
            domain="saas", title="Landing page failed",
            description="0 signups after 1000 visitors",
        )
        assert exp.experience_type == ExperienceType.FAILURE

    def test_record_strategy(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_strategy(
            domain="marketing", title="Email drip sequence",
            description="5-email sequence with 40% open rate",
        )
        assert exp.experience_type == ExperienceType.STRATEGY

    def test_record_lesson(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_lesson(
            domain="infrastructure", title="Always use WAL mode",
            description="SQLite WAL prevents lock contention",
        )
        assert exp.experience_type == ExperienceType.LESSON

    def test_invalid_type_raises(self, exp_mem: ExperienceMemory):
        with pytest.raises(ValueError):
            exp_mem.record_experience(
                experience_type="invalid", domain="test",
                title="test", description="test",
            )

    def test_invalid_confidence_raises(self, exp_mem: ExperienceMemory):
        with pytest.raises(ValueError, match="Confidence"):
            exp_mem.record_experience(
                experience_type="success", domain="test",
                title="test", description="test", confidence=1.5,
            )

    def test_with_tags_and_context(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_success(
            domain="automation", title="CRM bot",
            description="Automated CRM data entry",
            context={"client": "acme", "revenue": 500},
            tags=["automation", "crm"],
        )
        exps = exp_mem.get_experiences(domain="automation")
        assert len(exps) == 1
        assert exps[0].tags == ["automation", "crm"]


class TestExperienceQueries:
    def test_filter_by_domain(self, exp_mem: ExperienceMemory):
        exp_mem.record_success(domain="trading", title="t1", description="d1")
        exp_mem.record_success(domain="saas", title="t2", description="d2")
        results = exp_mem.get_successes(domain="trading")
        assert len(results) == 1

    def test_filter_by_type(self, exp_mem: ExperienceMemory):
        exp_mem.record_success(domain="test", title="s1", description="d1")
        exp_mem.record_failure(domain="test", title="f1", description="d2")
        assert len(exp_mem.get_successes()) == 1
        assert len(exp_mem.get_failures()) == 1

    def test_search_keyword(self, exp_mem: ExperienceMemory):
        exp_mem.record_success(domain="test", title="momentum strategy", description="great")
        exp_mem.record_failure(domain="test", title="mean reversion", description="bad")
        results = exp_mem.search_experiences("momentum")
        assert len(results) == 1
        assert "momentum" in results[0].title

    def test_apply_experience(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_strategy(domain="test", title="t", description="d")
        exp_mem.apply_experience(exp.id)
        updated = exp_mem.get_strategies()
        assert updated[0].times_applied == 1

    def test_strengthen_and_weaken(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_lesson(domain="test", title="t", description="d", confidence=0.5)
        exp_mem.strengthen(exp.id, boost=0.2)
        results = exp_mem.get_lessons()
        assert results[0].confidence == pytest.approx(0.7, abs=0.01)

        exp_mem.weaken(exp.id, penalty=0.3)
        results = exp_mem.get_lessons()
        assert results[0].confidence == pytest.approx(0.4, abs=0.01)


class TestExperienceStats:
    def test_empty_stats(self, exp_mem: ExperienceMemory):
        stats = exp_mem.stats()
        assert stats["total_experiences"] == 0
        assert stats["short_term_entries"] == 0

    def test_stats_with_data(self, exp_mem: ExperienceMemory):
        exp_mem.record_success(domain="test", title="t1", description="d")
        exp_mem.record_failure(domain="test", title="t2", description="d")
        exp_mem.store_short_term("context")
        stats = exp_mem.stats()
        assert stats["total_experiences"] == 2
        assert stats["short_term_entries"] == 1
        assert "success" in stats["by_type"]
        assert "failure" in stats["by_type"]
