"""Tests for the Agent Civilization registry."""

from __future__ import annotations

from backend.agents.civilization import (
    ALL_DIVISIONS,
    get_all_civilization_agents,
    get_division,
    get_division_stats,
    get_total_agent_count,
    STRATEGY_COUNCIL,
    RESEARCH_DIVISION,
    ENGINEERING_DIVISION,
    DATA_DIVISION,
    LEARNING_DIVISION,
    ECONOMIC_ENGINE,
    CONTENT_ENGINE,
    AUTOMATION_ENGINE,
    INFRASTRUCTURE_OPS,
    GOVERNANCE_SAFETY,
)
from backend.agents.registry import build_default_registry


class TestCivilizationDefinitions:
    def test_total_agent_count_at_least_150(self):
        assert get_total_agent_count() >= 150

    def test_ten_divisions(self):
        assert len(ALL_DIVISIONS) == 10

    def test_division_sizes(self):
        assert len(STRATEGY_COUNCIL) == 15
        assert len(RESEARCH_DIVISION) == 20
        assert len(ENGINEERING_DIVISION) == 30
        assert len(DATA_DIVISION) == 15
        assert len(LEARNING_DIVISION) == 20
        assert len(ECONOMIC_ENGINE) == 20
        assert len(CONTENT_ENGINE) == 10
        assert len(AUTOMATION_ENGINE) == 10
        assert len(INFRASTRUCTURE_OPS) == 10
        assert len(GOVERNANCE_SAFETY) == 10

    def test_all_agents_have_ids(self):
        for agent in get_all_civilization_agents():
            assert agent.id, f"Agent {agent.name} has no id"

    def test_no_duplicate_ids(self):
        agents = get_all_civilization_agents()
        ids = [a.id for a in agents]
        assert len(ids) == len(set(ids)), f"Duplicate IDs: {[i for i in ids if ids.count(i) > 1]}"

    def test_all_agents_have_capabilities(self):
        for agent in get_all_civilization_agents():
            assert len(agent.capabilities) > 0, f"Agent {agent.id} has no capabilities"

    def test_agents_have_expanded_capabilities(self):
        """Each agent should have 4-6 capabilities for full tool coverage."""
        for agent in get_all_civilization_agents():
            assert len(agent.capabilities) >= 4, (
                f"Agent {agent.id} has only {len(agent.capabilities)} capabilities, expected 4+"
            )

    def test_get_division(self):
        strategy = get_division("Strategy Council")
        assert len(strategy) == 15

    def test_get_nonexistent_division(self):
        assert get_division("Nonexistent") == []

    def test_division_stats(self):
        stats = get_division_stats()
        assert sum(stats.values()) >= 150


class TestRegistryIntegration:
    def test_registry_includes_civilization(self):
        registry = build_default_registry()
        # 12 core agents + 150+ civilization agents
        assert registry.agent_count() >= 162

    def test_core_agents_preserved(self):
        registry = build_default_registry()
        core = registry.list_core_agents()
        core_ids = {a.id for a in core}
        assert "astra" in core_ids
        assert "root" in core_ids
        assert "hermes" in core_ids
        assert "miro" in core_ids
        assert "swarm" in core_ids
        assert "openclaw" in core_ids
        assert "builder" in core_ids
        assert "researcher" in core_ids
        assert "coder" in core_ids
        assert "writer" in core_ids
        assert "analyst" in core_ids
        assert "guardian" in core_ids

    def test_divisions_registered(self):
        registry = build_default_registry()
        divisions = registry.list_divisions()
        assert len(divisions) == 10

    def test_list_division_agents(self):
        registry = build_default_registry()
        strategy = registry.list_division("Strategy Council")
        assert len(strategy) == 15

    def test_find_by_capability(self):
        registry = build_default_registry()
        architects = registry.find_by_capability("architecture")
        assert len(architects) >= 1
