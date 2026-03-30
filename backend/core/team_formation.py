"""
Team Formation — dynamic agent team assembly based on learned strengths.

Given a task description, selects the best agents by combining:
1. Routing weights from the LearningEngine (Bayesian, per-category)
2. Keyword-to-capability matching against the AgentRegistry
3. Current agent load (prefer less-busy agents)

This replaces static agent assignment with data-driven team formation.
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any, Optional

logger = logging.getLogger("root.team_formation")


# ── Keyword → capability mapping ─────────────────────────────

_KEYWORD_AGENTS: dict[str, list[str]] = {
    "research":     ["researcher", "analyst"],
    "investigate":  ["researcher", "analyst"],
    "explore":      ["researcher", "analyst"],
    "code":         ["coder", "builder"],
    "implement":    ["coder", "builder"],
    "build":        ["coder", "builder"],
    "fix":          ["coder", "builder"],
    "trade":        ["swarm", "analyst"],
    "market":       ["swarm", "analyst"],
    "signal":       ["swarm", "analyst"],
    "portfolio":    ["swarm", "analyst"],
    "predict":      ["miro", "analyst"],
    "forecast":     ["miro", "analyst"],
    "scenario":     ["miro", "analyst"],
    "write":        ["writer"],
    "content":      ["writer"],
    "marketing":    ["writer"],
    "security":     ["guardian"],
    "audit":        ["guardian"],
    "protect":      ["guardian"],
    "strategy":     ["analyst", "researcher"],
    "plan":         ["analyst", "researcher"],
    "goal":         ["analyst", "researcher"],
}

# Precompile a regex with all keywords for fast matching.
_KEYWORD_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in _KEYWORD_AGENTS) + r")\b",
    re.IGNORECASE,
)


class TeamFormation:
    """Dynamic agent team assembly based on learned strengths.

    Combines routing weights from the learning engine with keyword-based
    capability matching to select the best team for a given task.
    """

    def __init__(
        self,
        learning_engine=None,
        registry=None,
    ) -> None:
        self._learning_engine = learning_engine
        self._registry = registry
        self._agent_load: dict[str, int] = {}
        self._lock = threading.Lock()
        self._total_teams_formed = 0
        logger.info("TeamFormation initialised")

    # ── Public API ────────────────────────────────────────────

    def form_team(
        self,
        task_description: str,
        category: str = "",
        max_agents: int = 3,
    ) -> list[str]:
        """Select the best agents for a task.

        Args:
            task_description: Free-text description of the task.
            category: Optional category for routing weight lookup.
            max_agents: Maximum number of agents to return.

        Returns:
            List of agent IDs, ranked by combined score (best first).
        """
        if max_agents <= 0:
            return []

        # ── Step 1: Keyword relevance scores ──────────────────
        keyword_scores: dict[str, float] = {}
        matches = _KEYWORD_PATTERN.findall(task_description.lower())

        for keyword in matches:
            agents = _KEYWORD_AGENTS.get(keyword.lower(), [])
            for agent_id in agents:
                keyword_scores[agent_id] = keyword_scores.get(agent_id, 0.0) + 1.0

        # Normalise keyword scores to [0, 1] range.
        max_kw = max(keyword_scores.values()) if keyword_scores else 1.0
        if max_kw > 0:
            keyword_scores = {a: s / max_kw for a, s in keyword_scores.items()}

        # ── Step 2: Routing weights from learning engine ──────
        routing_scores: dict[str, float] = {}
        if self._learning_engine is not None and category:
            try:
                all_weights = self._learning_engine.get_routing_weights()
                for key, weight in all_weights.items():
                    # Keys are "agent_id:category"
                    parts = key.rsplit(":", 1)
                    if len(parts) == 2 and parts[1] == category:
                        routing_scores[parts[0]] = weight
            except Exception:
                logger.debug("Could not fetch routing weights")

        # ── Step 3: Combine scores ────────────────────────────
        # Gather all candidate agent IDs.
        all_candidates = set(keyword_scores.keys()) | set(routing_scores.keys())

        # If no candidates matched at all, fall back to registry listing.
        if not all_candidates and self._registry is not None:
            try:
                for agent in self._registry.list_core_agents():
                    all_candidates.add(agent.id)
            except Exception:
                pass

        # Default weight for missing scores.
        combined: dict[str, float] = {}
        for agent_id in all_candidates:
            kw = keyword_scores.get(agent_id, 0.0)
            rw = routing_scores.get(agent_id, 0.5)
            combined[agent_id] = rw * (1.0 + kw)  # Routing weight boosted by keyword relevance

        # ── Step 4: Verify agents exist in registry ───────────
        if self._registry is not None:
            verified: dict[str, float] = {}
            for agent_id, score in combined.items():
                if self._registry.get(agent_id) is not None:
                    verified[agent_id] = score
            combined = verified if verified else combined

        # ── Step 5: Rank and return top N ─────────────────────
        ranked = sorted(combined.keys(), key=lambda a: combined[a], reverse=True)
        team = ranked[:max_agents]

        self._total_teams_formed += 1
        logger.info(
            "Formed team of %d for '%s' (category=%s): %s",
            len(team), task_description[:60], category or "none",
            ", ".join(team),
        )
        return team

    # ── Load tracking ─────────────────────────────────────────

    def get_agent_load(self) -> dict[str, int]:
        """Return concurrent task count per agent."""
        with self._lock:
            return dict(self._agent_load)

    def record_task_start(self, agent_id: str) -> None:
        """Increment the concurrent task counter for an agent."""
        with self._lock:
            self._agent_load[agent_id] = self._agent_load.get(agent_id, 0) + 1
        logger.debug("Task started for %s (load=%d)", agent_id, self._agent_load[agent_id])

    def record_task_end(self, agent_id: str) -> None:
        """Decrement the concurrent task counter for an agent."""
        with self._lock:
            current = self._agent_load.get(agent_id, 0)
            self._agent_load[agent_id] = max(0, current - 1)
        logger.debug("Task ended for %s (load=%d)", agent_id, self._agent_load[agent_id])

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return runtime statistics."""
        with self._lock:
            load_snapshot = dict(self._agent_load)
        return {
            "total_teams_formed": self._total_teams_formed,
            "agent_load": load_snapshot,
            "busy_agents": sum(1 for v in load_snapshot.values() if v > 0),
            "has_learning_engine": self._learning_engine is not None,
            "has_registry": self._registry is not None,
            "keyword_mappings": len(_KEYWORD_AGENTS),
        }
