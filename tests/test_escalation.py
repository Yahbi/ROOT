"""Tests for the Escalation Engine — confidence-gated decisions."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.escalation_engine import EscalationEngine, ESCALATION_DB


@pytest.fixture
def escalation(tmp_path):
    db_path = tmp_path / "test_escalation.db"
    with patch("backend.core.escalation_engine.ESCALATION_DB", db_path):
        engine = EscalationEngine()
        engine.start()
        yield engine
        engine.stop()


class TestEscalationDecisions:
    def test_insufficient_history_escalates(self, escalation):
        decision = escalation.should_auto_execute("new_action_type")
        assert decision.should_auto_execute is False
        assert "Insufficient history" in decision.reason

    def test_high_confidence_auto_executes(self, escalation):
        # Build up history with positive outcomes
        for _ in range(10):
            record_id = escalation.record_decision(
                "proven_action", "Test action description", auto_executed=True,
            )
            escalation.record_outcome(record_id, positive=True)

        decision = escalation.should_auto_execute("proven_action")
        assert decision.should_auto_execute is True

    def test_high_risk_needs_more_confidence(self, escalation):
        # Build moderate history
        for _ in range(6):
            record_id = escalation.record_decision(
                "risky_action", "Test risky action here", auto_executed=True,
            )
            escalation.record_outcome(record_id, positive=True)

        # Low risk should auto-execute
        low_decision = escalation.should_auto_execute("risky_action", risk_level="low")
        # Critical risk should be more cautious
        crit_decision = escalation.should_auto_execute("risky_action", risk_level="critical")

        # Critical should be less likely to auto-execute
        assert crit_decision.confidence <= low_decision.confidence or not crit_decision.should_auto_execute


class TestOverrides:
    def test_override_lowers_confidence(self, escalation):
        # Build initial confidence
        for _ in range(6):
            record_id = escalation.record_decision(
                "override_test", "Test override action", auto_executed=True,
            )
            escalation.record_outcome(record_id, positive=True)

        conf_before = escalation._confidence_cache.get("override_test", 0.5)

        # Record override
        record_id = escalation.record_decision(
            "override_test", "Bad action by system", auto_executed=True,
        )
        escalation.record_override(record_id, "user corrected this decision")

        conf_after = escalation._confidence_cache.get("override_test", 0.5)
        assert conf_after <= conf_before


class TestEscalationStats:
    def test_stats(self, escalation):
        escalation.record_decision("test_action", "Testing stats", auto_executed=True)
        escalation.record_decision("test_action", "Testing stats two", auto_executed=False)
        stats = escalation.stats()
        assert stats["total_decisions"] == 2
        assert stats["auto_executed"] == 1

    def test_recent_decisions(self, escalation):
        escalation.record_decision("action_a", "First decision made", auto_executed=True)
        escalation.record_decision("action_b", "Second decision made", auto_executed=False)
        recent = escalation.get_recent_decisions(10)
        assert len(recent) == 2
