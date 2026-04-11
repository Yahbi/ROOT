"""Extended tests for Experience Memory — 3-layer system edge cases and interactions."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.experience_memory import ExperienceMemory, ExperienceType, ShortTermEntry


@pytest.fixture
def exp_mem(tmp_path):
    with patch("backend.core.experience_memory.EXPERIENCE_DB", tmp_path / "experience.db"):
        engine = ExperienceMemory()
        engine.start()
        yield engine
        engine.stop()


# ── Short-Term TTL ────────────────────────────────────────────────────


class TestShortTermTTL:
    def test_entries_expire_after_ttl(self, exp_mem: ExperienceMemory):
        """Entries with ttl_seconds=0 should be immediately expired on next get."""
        exp_mem.store_short_term("Instant expiry entry", ttl_seconds=0)
        import time
        time.sleep(0.01)
        entries = exp_mem.get_short_term()
        # The entry should be expired and cleaned up
        assert len(entries) == 0

    def test_entries_survive_within_ttl(self, exp_mem: ExperienceMemory):
        exp_mem.store_short_term("Long-lived entry", ttl_seconds=3600)
        entries = exp_mem.get_short_term()
        assert len(entries) == 1

    def test_short_term_entry_fields(self, exp_mem: ExperienceMemory):
        entry = exp_mem.store_short_term("Content here", task_id="task_abc", ttl_seconds=60)
        assert isinstance(entry, ShortTermEntry)
        assert entry.id.startswith("stm_")
        assert entry.task_id == "task_abc"
        assert entry.ttl_seconds == 60
        assert entry.created_at

    def test_multiple_tasks_isolated(self, exp_mem: ExperienceMemory):
        exp_mem.store_short_term("Task X step 1", task_id="taskX")
        exp_mem.store_short_term("Task X step 2", task_id="taskX")
        exp_mem.store_short_term("Task Y step 1", task_id="taskY")

        x_entries = exp_mem.get_short_term(task_id="taskX")
        y_entries = exp_mem.get_short_term(task_id="taskY")
        all_entries = exp_mem.get_short_term()

        assert len(x_entries) == 2
        assert len(y_entries) == 1
        assert len(all_entries) == 3


# ── Experience Recording Edge Cases ───────────────────────────────────


class TestExperienceEdgeCases:
    def test_zero_confidence_is_valid(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_lesson(
            domain="test", title="uncertain lesson", description="nothing known",
            confidence=0.0,
        )
        assert exp.confidence == 0.0

    def test_full_confidence_is_valid(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_success(
            domain="test", title="certain win", description="definite success",
            confidence=1.0,
        )
        assert exp.confidence == 1.0

    def test_context_is_stored_and_retrieved(self, exp_mem: ExperienceMemory):
        ctx = {"client": "acme", "revenue": 5000, "duration_days": 30}
        exp_mem.record_success(
            domain="consulting", title="ACME project", description="Delivered on time",
            context=ctx,
        )
        results = exp_mem.get_successes(domain="consulting")
        assert len(results) == 1
        assert results[0].context["client"] == "acme"
        assert results[0].context["revenue"] == 5000

    def test_outcome_field_stored(self, exp_mem: ExperienceMemory):
        exp_mem.record_failure(
            domain="trading", title="bad trade", description="Loss",
            outcome="Lost $500 due to stop-loss not triggered",
        )
        failures = exp_mem.get_failures()
        assert len(failures) == 1
        assert "stop-loss" in failures[0].outcome

    def test_tags_empty_list_by_default(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_lesson(domain="test", title="no tags", description="lesson")
        assert exp.tags == []

    def test_multiple_tags_stored(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_strategy(
            domain="marketing", title="email drip",
            description="5-email sequence", tags=["email", "drip", "conversion"],
        )
        lessons = exp_mem.get_strategies()
        assert "email" in lessons[0].tags
        assert "conversion" in lessons[0].tags


# ── Experience Queries ─────────────────────────────────────────────────


class TestExperienceQueryFilters:
    def test_get_all_experiences(self, exp_mem: ExperienceMemory):
        exp_mem.record_success(domain="a", title="t1", description="d")
        exp_mem.record_failure(domain="b", title="t2", description="d")
        exp_mem.record_strategy(domain="c", title="t3", description="d")
        exp_mem.record_lesson(domain="d", title="t4", description="d")
        results = exp_mem.get_experiences()
        assert len(results) == 4

    def test_filter_by_type_success(self, exp_mem: ExperienceMemory):
        exp_mem.record_success(domain="x", title="win", description="good")
        exp_mem.record_failure(domain="x", title="fail", description="bad")
        successes = exp_mem.get_successes()
        assert all(e.experience_type == ExperienceType.SUCCESS for e in successes)
        assert len(successes) == 1

    def test_filter_by_type_failure(self, exp_mem: ExperienceMemory):
        exp_mem.record_success(domain="x", title="win", description="good")
        exp_mem.record_failure(domain="x", title="fail", description="bad")
        failures = exp_mem.get_failures()
        assert all(e.experience_type == ExperienceType.FAILURE for e in failures)

    def test_filter_by_domain_and_type(self, exp_mem: ExperienceMemory):
        exp_mem.record_success(domain="trading", title="trade win", description="d")
        exp_mem.record_success(domain="saas", title="saas win", description="d")
        results = exp_mem.get_successes(domain="trading")
        assert len(results) == 1
        assert results[0].domain == "trading"

    def test_search_case_insensitive(self, exp_mem: ExperienceMemory):
        exp_mem.record_lesson(domain="test", title="Momentum Strategy Works", description="d")
        results = exp_mem.search_experiences("momentum")
        assert len(results) == 1

    def test_search_by_description(self, exp_mem: ExperienceMemory):
        exp_mem.record_success(
            domain="test", title="generic title",
            description="unique_keyword_here in the description",
        )
        results = exp_mem.search_experiences("unique_keyword_here")
        assert len(results) >= 1

    def test_get_strategies(self, exp_mem: ExperienceMemory):
        exp_mem.record_strategy(domain="marketing", title="drip", description="email")
        exp_mem.record_strategy(domain="product", title="mvp", description="lean")
        strategies = exp_mem.get_strategies()
        assert len(strategies) == 2

    def test_get_lessons(self, exp_mem: ExperienceMemory):
        exp_mem.record_lesson(domain="infra", title="wal mode", description="use wal")
        lessons = exp_mem.get_lessons()
        assert len(lessons) == 1


# ── Apply Experience ───────────────────────────────────────────────────


class TestApplyExperience:
    def test_times_applied_increments_each_call(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_strategy(domain="test", title="t", description="d")
        exp_mem.apply_experience(exp.id)
        exp_mem.apply_experience(exp.id)
        exp_mem.apply_experience(exp.id)
        results = exp_mem.get_strategies()
        assert results[0].times_applied == 3

    def test_apply_nonexistent_does_not_raise(self, exp_mem: ExperienceMemory):
        # Should handle gracefully
        exp_mem.apply_experience("exp_doesnotexist0000")


# ── Confidence Strengthen / Weaken ────────────────────────────────────


class TestConfidenceAdjustment:
    def test_strengthen_capped_at_one(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_success(domain="test", title="t", description="d", confidence=0.9)
        exp_mem.strengthen(exp.id, boost=0.5)
        results = exp_mem.get_successes()
        assert results[0].confidence <= 1.0

    def test_weaken_floored_at_zero(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_failure(domain="test", title="t", description="d", confidence=0.1)
        exp_mem.weaken(exp.id, penalty=0.5)
        results = exp_mem.get_failures()
        assert results[0].confidence >= 0.0

    def test_strengthen_and_weaken_cycle(self, exp_mem: ExperienceMemory):
        exp = exp_mem.record_lesson(domain="test", title="t", description="d", confidence=0.5)
        exp_mem.strengthen(exp.id, boost=0.2)
        exp_mem.weaken(exp.id, penalty=0.1)
        results = exp_mem.get_lessons()
        assert results[0].confidence == pytest.approx(0.6, abs=0.02)


# ── Stats ──────────────────────────────────────────────────────────────


class TestExperienceStatsExtended:
    def test_stats_has_all_type_keys(self, exp_mem: ExperienceMemory):
        exp_mem.record_success(domain="t", title="t", description="d")
        exp_mem.record_failure(domain="t", title="t", description="d")
        exp_mem.record_strategy(domain="t", title="t", description="d")
        exp_mem.record_lesson(domain="t", title="t", description="d")
        stats = exp_mem.stats()
        assert "success" in stats["by_type"]
        assert "failure" in stats["by_type"]
        assert "strategy" in stats["by_type"]
        assert "lesson" in stats["by_type"]

    def test_stats_counts_short_term(self, exp_mem: ExperienceMemory):
        exp_mem.store_short_term("context 1")
        exp_mem.store_short_term("context 2")
        stats = exp_mem.stats()
        assert stats["short_term_entries"] == 2

    def test_stats_domain_breakdown(self, exp_mem: ExperienceMemory):
        exp_mem.record_success(domain="trading", title="t", description="d")
        exp_mem.record_success(domain="trading", title="t2", description="d")
        exp_mem.record_failure(domain="saas", title="f", description="d")
        stats = exp_mem.stats()
        assert stats["total_experiences"] == 3
