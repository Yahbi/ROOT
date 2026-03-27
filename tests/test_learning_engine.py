"""Tests for the Learning Engine — Bayesian routing weights and outcome tracking."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.learning_engine import LearningEngine


@pytest.fixture
def learning(tmp_path):
    """Provide a started LearningEngine with a temp database."""
    with patch("backend.core.learning_engine.LEARNING_DB", tmp_path / "learning.db"):
        engine = LearningEngine()
        engine.start()
        yield engine
        engine.stop()


class TestRecordInteraction:
    def test_record_and_stats(self, learning: LearningEngine):
        learning.record_interaction(
            user_message="test query",
            route="researcher",
            agents_used=["researcher"],
            response_length=100,
            agent_findings_count=2,
            tools_used_count=1,
            duration_seconds=0.5,
        )
        stats = learning.stats()
        assert stats["interactions_tracked"] >= 1

    def test_record_multiple(self, learning: LearningEngine):
        for i in range(5):
            learning.record_interaction(
                user_message=f"query {i}",
                route="coder",
                agents_used=["coder"],
                response_length=50 + i * 10,
                agent_findings_count=1,
                tools_used_count=0,
                duration_seconds=0.2,
            )
        stats = learning.stats()
        assert stats["interactions_tracked"] >= 5


class TestAgentOutcome:
    def test_record_success(self, learning: LearningEngine):
        learning.record_agent_outcome(
            agent_id="researcher",
            task_description="Search for AI trends",
            status="completed",
            result_quality=0.9,
            task_category="research",
        )
        stats = learning.stats()
        assert stats["agent_outcomes_tracked"] >= 1

    def test_record_failure(self, learning: LearningEngine):
        learning.record_agent_outcome(
            agent_id="coder",
            task_description="Generate buggy code",
            status="failed",
            result_quality=0.2,
            task_category="coding",
        )
        stats = learning.stats()
        assert stats["agent_outcomes_tracked"] >= 1


class TestRoutingWeights:
    def test_default_weight(self, learning: LearningEngine):
        weight = learning.get_agent_weight("unknown_agent", "general")
        assert weight == 0.5  # Default when no data

    def test_weight_after_success(self, learning: LearningEngine):
        learning.record_agent_outcome(
            agent_id="researcher",
            task_description="Research task",
            status="completed",
            result_quality=0.9,
            task_category="research",
        )
        weight = learning.get_agent_weight("researcher", "research")
        assert weight > 0.5  # Should be above default after success

    def test_weight_after_failure(self, learning: LearningEngine):
        learning.record_agent_outcome(
            agent_id="coder",
            task_description="Bad code",
            status="failed",
            result_quality=0.1,
            task_category="coding",
        )
        weight = learning.get_agent_weight("coder", "coding")
        assert weight < 0.5  # Should be below default after failure

    def test_get_routing_weights_dict(self, learning: LearningEngine):
        learning.record_agent_outcome(
            agent_id="researcher", task_description="t1",
            status="completed", result_quality=0.8, task_category="research",
        )
        learning.record_agent_outcome(
            agent_id="coder", task_description="t2",
            status="completed", result_quality=0.7, task_category="coding",
        )
        weights = learning.get_routing_weights()
        assert "researcher:research" in weights
        assert "coder:coding" in weights

    def test_get_best_agent_for(self, learning: LearningEngine):
        # Record good outcomes for researcher on research tasks
        for _ in range(5):
            learning.record_agent_outcome(
                agent_id="researcher", task_description="research task",
                status="completed", result_quality=0.9, task_category="research",
            )
        # Record poor outcomes for coder on research tasks
        for _ in range(5):
            learning.record_agent_outcome(
                agent_id="coder", task_description="research task",
                status="failed", result_quality=0.2, task_category="research",
            )
        best = learning.get_best_agent_for("research")
        assert best == "researcher"


class TestBoostRoutingWeight:
    def test_boost_new_agent(self, learning: LearningEngine):
        new_weight = learning.boost_routing_weight("analyst", "market", amount=0.1)
        assert new_weight == pytest.approx(0.6, abs=0.01)

    def test_boost_existing_agent(self, learning: LearningEngine):
        learning.record_agent_outcome(
            agent_id="researcher", task_description="t",
            status="completed", result_quality=0.8, task_category="research",
        )
        before = learning.get_agent_weight("researcher", "research")
        after = learning.boost_routing_weight("researcher", "research", amount=0.05)
        assert after == pytest.approx(before + 0.05, abs=0.01)

    def test_boost_clamped(self, learning: LearningEngine):
        # Boost beyond 1.0 should clamp to 0.99
        learning.boost_routing_weight("agent", "cat", amount=0.6)
        result = learning.boost_routing_weight("agent", "cat", amount=0.6)
        assert result <= 0.99

    def test_negative_boost(self, learning: LearningEngine):
        learning.boost_routing_weight("agent", "cat", amount=0.3)
        result = learning.boost_routing_weight("agent", "cat", amount=-0.5)
        assert result >= 0.01


class TestInsights:
    def test_get_insights_empty(self, learning: LearningEngine):
        insights = learning.get_insights()
        assert isinstance(insights, dict)

    def test_insights_with_data(self, learning: LearningEngine):
        for i in range(10):
            learning.record_interaction(
                user_message=f"search query {i}",
                route="researcher",
                agents_used=["researcher"],
                response_length=100,
                agent_findings_count=1,
                tools_used_count=0,
                duration_seconds=0.1,
            )
        insights = learning.get_insights()
        assert isinstance(insights, dict)
