"""Tests for the Trigger Engine — rule management and firing."""

from __future__ import annotations

from dataclasses import replace

import pytest

from backend.core.trigger_engine import TriggerEngine, TriggerRule


@pytest.fixture
def trigger_engine():
    engine = TriggerEngine()
    # Clear defaults for testing
    engine._rules.clear()
    return engine


class TestRuleManagement:
    def test_add_rule(self, trigger_engine):
        rule = TriggerRule(
            id="test_rule",
            name="Test Rule",
            trigger_type="webhook",
            config={},
            action_type="enqueue",
            action_config={"goal": "Process webhook event data"},
        )
        trigger_engine.add_rule(rule)
        rules = trigger_engine.get_rules()
        assert len(rules) == 1
        assert rules[0]["name"] == "Test Rule"

    def test_remove_rule(self, trigger_engine):
        rule = TriggerRule(
            id="removable",
            name="Removable Rule",
            trigger_type="condition",
            config={},
            action_type="enqueue",
            action_config={},
        )
        trigger_engine.add_rule(rule)
        assert trigger_engine.remove_rule("removable") is True
        assert trigger_engine.remove_rule("nonexistent") is False

    def test_enable_disable(self, trigger_engine):
        rule = TriggerRule(
            id="toggleable",
            name="Toggleable Rule",
            trigger_type="schedule",
            config={},
            action_type="enqueue",
            action_config={},
        )
        trigger_engine.add_rule(rule)
        assert trigger_engine.disable_rule("toggleable") is True
        rules = trigger_engine.get_rules()
        assert rules[0]["enabled"] is False

        assert trigger_engine.enable_rule("toggleable") is True
        rules = trigger_engine.get_rules()
        assert rules[0]["enabled"] is True


class TestTriggerStats:
    def test_stats(self, trigger_engine):
        trigger_engine.add_rule(TriggerRule(
            id="r1", name="Rule 1", trigger_type="webhook",
            config={}, action_type="enqueue", action_config={},
        ))
        trigger_engine.add_rule(TriggerRule(
            id="r2", name="Rule 2", trigger_type="schedule",
            config={}, action_type="enqueue", action_config={},
        ))
        stats = trigger_engine.stats()
        assert stats["total_rules"] == 2
        assert stats["enabled"] == 2
        assert stats["by_type"]["webhook"] == 1
        assert stats["by_type"]["schedule"] == 1


class TestDefaultRules:
    def test_defaults_registered(self):
        engine = TriggerEngine()
        rules = engine.get_rules()
        # Should have morning briefing and evening summary at minimum
        names = [r["name"] for r in rules]
        assert "Morning Briefing" in names
        assert "Evening Summary" in names
