"""
Agent Civilization — 160 specialized agents across 10 divisions.

Thin wrapper that re-exports from backend.agents.divisions.
All agent definitions live in per-division files under divisions/.
"""

from __future__ import annotations

from backend.models.agent import AgentProfile

from backend.agents.divisions import (
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
    ALL_DIVISIONS,
)


def get_all_civilization_agents() -> list[AgentProfile]:
    """Return all 160 civilization agents."""
    agents: list[AgentProfile] = []
    for division in ALL_DIVISIONS.values():
        agents.extend(division)
    return agents


def get_division(name: str) -> list[AgentProfile]:
    """Get agents for a specific division."""
    return ALL_DIVISIONS.get(name, [])


def get_division_stats() -> dict[str, int]:
    """Get agent count per division."""
    return {name: len(agents) for name, agents in ALL_DIVISIONS.items()}


def get_total_agent_count() -> int:
    """Total number of civilization agents."""
    return sum(len(agents) for agents in ALL_DIVISIONS.values())


__all__ = [
    "STRATEGY_COUNCIL", "RESEARCH_DIVISION", "ENGINEERING_DIVISION",
    "DATA_DIVISION", "LEARNING_DIVISION", "ECONOMIC_ENGINE",
    "CONTENT_ENGINE", "AUTOMATION_ENGINE", "INFRASTRUCTURE_OPS",
    "GOVERNANCE_SAFETY", "ALL_DIVISIONS",
    "get_all_civilization_agents", "get_division",
    "get_division_stats", "get_total_agent_count",
]
