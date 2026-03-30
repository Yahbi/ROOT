"""
Decision Feedback — Periodic analysis of outcomes that generates adjustment signals.

Closes the loop between action outcomes and future decision-making.
Analyzes the outcome registry to identify underperforming and high-performing
action types, ranks agents by effectiveness, and generates concrete
recommendations that are applied to the learning engine's routing weights.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger("root.decision_feedback")


class DecisionFeedback:
    """Analyzes accumulated outcomes and generates adjustment signals.

    Reads from OutcomeRegistry, produces actionable signals (which action types
    are working, which agents are effective, what to change), and applies those
    signals to the LearningEngine's routing weights.
    """

    # Thresholds for classification
    UNDERPERFORMING_THRESHOLD = 0.3
    HIGH_PERFORMING_THRESHOLD = 0.7
    MIN_SAMPLES = 3  # Minimum outcomes before judging an action type

    def __init__(
        self,
        outcome_registry: Any = None,
        learning_engine: Any = None,
    ) -> None:
        self._registry = outcome_registry
        self._learning_engine = learning_engine

    # ── Analysis ──────────────────────────────────────────────────

    async def analyze(self) -> dict:
        """Analyze recent outcomes and produce adjustment signals.

        Returns a dict with:
            underperforming_actions: action_types with avg quality < 0.3
            high_performing_actions: action_types with avg quality > 0.7
            agent_rankings: agents sorted by effectiveness (best first)
            recommendations: list of human-readable adjustment suggestions
        """
        signals: dict[str, Any] = {
            "underperforming_actions": [],
            "high_performing_actions": [],
            "agent_rankings": [],
            "recommendations": [],
        }

        if not self._registry:
            logger.warning("DecisionFeedback.analyze called without outcome_registry")
            return signals

        try:
            stats = self._registry.stats()
        except Exception as exc:
            logger.error("Failed to fetch outcome stats: %s", exc)
            return signals

        by_type = stats.get("by_action_type", {})

        # ── Classify action types by performance ──────────────────
        for action_type, type_stats in by_type.items():
            count = type_stats.get("count", 0)
            if count < self.MIN_SAMPLES:
                continue

            avg_q = type_stats.get("avg_quality", 0.0)

            if avg_q < self.UNDERPERFORMING_THRESHOLD:
                signals["underperforming_actions"].append({
                    "action_type": action_type,
                    "avg_quality": avg_q,
                    "count": count,
                    "success_rate": type_stats.get("success_rate", 0.0),
                })
            elif avg_q > self.HIGH_PERFORMING_THRESHOLD:
                signals["high_performing_actions"].append({
                    "action_type": action_type,
                    "avg_quality": avg_q,
                    "count": count,
                    "success_rate": type_stats.get("success_rate", 0.0),
                })

        # ── Agent rankings ────────────────────────────────────────
        agent_rankings = self._build_agent_rankings()
        signals["agent_rankings"] = agent_rankings

        # ── Generate recommendations ──────────────────────────────
        signals["recommendations"] = self._generate_recommendations(signals)

        logger.info(
            "Decision feedback: %d underperforming, %d high-performing, %d agents ranked, %d recommendations",
            len(signals["underperforming_actions"]),
            len(signals["high_performing_actions"]),
            len(signals["agent_rankings"]),
            len(signals["recommendations"]),
        )

        return signals

    def apply_signals(self, signals: dict) -> None:
        """Apply adjustment signals to the learning engine.

        For underperforming actions: reduce routing weights for associated agents.
        For high-performing actions: boost routing weights for associated agents.
        """
        if not self._learning_engine:
            logger.warning("DecisionFeedback.apply_signals called without learning_engine")
            return

        applied = 0

        # Boost high-performing action types
        for entry in signals.get("high_performing_actions", []):
            action_type = entry["action_type"]
            try:
                self._learning_engine.boost_routing_weight(
                    agent_id=action_type,
                    category="autonomous",
                    amount=0.03,
                )
                applied += 1
            except Exception as exc:
                logger.warning(
                    "Failed to boost weight for %s: %s", action_type, exc,
                )

        # Reduce underperforming action types
        for entry in signals.get("underperforming_actions", []):
            action_type = entry["action_type"]
            try:
                self._learning_engine.boost_routing_weight(
                    agent_id=action_type,
                    category="autonomous",
                    amount=-0.03,
                )
                applied += 1
            except Exception as exc:
                logger.warning(
                    "Failed to reduce weight for %s: %s", action_type, exc,
                )

        # Boost top-ranked agents, reduce bottom-ranked
        rankings = signals.get("agent_rankings", [])
        if len(rankings) >= 2:
            # Boost top 20%
            top_n = max(1, len(rankings) // 5)
            for agent_entry in rankings[:top_n]:
                agent_id = agent_entry.get("agent_id", "")
                if not agent_id:
                    continue
                try:
                    self._learning_engine.boost_routing_weight(
                        agent_id=agent_id,
                        category="general",
                        amount=0.02,
                    )
                    applied += 1
                except Exception as exc:
                    logger.debug("Failed to boost agent %s: %s", agent_id, exc)

            # Reduce bottom 20%
            for agent_entry in rankings[-top_n:]:
                agent_id = agent_entry.get("agent_id", "")
                if not agent_id:
                    continue
                try:
                    self._learning_engine.boost_routing_weight(
                        agent_id=agent_id,
                        category="general",
                        amount=-0.02,
                    )
                    applied += 1
                except Exception as exc:
                    logger.debug("Failed to reduce agent %s: %s", agent_id, exc)

        logger.info("Applied %d routing weight adjustments from feedback signals", applied)

    # ── Internal helpers ──────────────────────────────────────────

    def _build_agent_rankings(self) -> list[dict]:
        """Build a sorted list of agents by effectiveness from the outcome registry.

        Extracts agent_id from outcome context and aggregates their scores.
        Returns list sorted by avg_quality descending.
        """
        if not self._registry:
            return []

        try:
            # Get recent outcomes to extract agent-level data
            outcomes = self._registry.get_outcomes(limit=200)
        except Exception as exc:
            logger.warning("Failed to fetch outcomes for agent ranking: %s", exc)
            return []

        agent_scores: dict[str, list[float]] = {}
        for outcome in outcomes:
            ctx = outcome.get("context", {})
            agent_id = ctx.get("agent_id")
            if not agent_id:
                continue
            agent_scores.setdefault(agent_id, []).append(
                outcome.get("quality_score", 0.0)
            )

        # Build ranked list (min samples filter)
        rankings: list[dict] = []
        for agent_id, scores in agent_scores.items():
            if len(scores) < self.MIN_SAMPLES:
                continue
            avg_q = sum(scores) / len(scores)
            success_count = sum(1 for s in scores if s >= 0.4)
            rankings.append({
                "agent_id": agent_id,
                "avg_quality": round(avg_q, 3),
                "success_rate": round(success_count / len(scores), 3),
                "total_outcomes": len(scores),
            })

        rankings.sort(key=lambda r: r["avg_quality"], reverse=True)
        return rankings

    def _generate_recommendations(self, signals: dict) -> list[str]:
        """Generate human-readable adjustment recommendations from signals."""
        recs: list[str] = []

        # Underperforming actions
        for entry in signals.get("underperforming_actions", []):
            action_type = entry["action_type"]
            avg_q = entry["avg_quality"]
            count = entry["count"]
            recs.append(
                f"REDUCE '{action_type}' frequency — avg quality {avg_q:.2f} "
                f"across {count} outcomes is below threshold ({self.UNDERPERFORMING_THRESHOLD}). "
                f"Consider revising strategy or pausing this action type."
            )

        # High-performing actions
        for entry in signals.get("high_performing_actions", []):
            action_type = entry["action_type"]
            avg_q = entry["avg_quality"]
            count = entry["count"]
            recs.append(
                f"INCREASE '{action_type}' frequency — avg quality {avg_q:.2f} "
                f"across {count} outcomes exceeds threshold ({self.HIGH_PERFORMING_THRESHOLD}). "
                f"This action type is highly effective."
            )

        # Agent-level recommendations
        rankings = signals.get("agent_rankings", [])
        if rankings:
            best = rankings[0]
            recs.append(
                f"TOP AGENT: '{best['agent_id']}' — avg quality {best['avg_quality']:.2f}, "
                f"success rate {best['success_rate']:.0%} across {best['total_outcomes']} outcomes. "
                f"Route more tasks to this agent."
            )
            if len(rankings) >= 2:
                worst = rankings[-1]
                if worst["avg_quality"] < self.UNDERPERFORMING_THRESHOLD:
                    recs.append(
                        f"WEAK AGENT: '{worst['agent_id']}' — avg quality {worst['avg_quality']:.2f}, "
                        f"success rate {worst['success_rate']:.0%}. "
                        f"Reduce task assignments or investigate root cause."
                    )

        # Overall health
        if not signals.get("underperforming_actions") and not signals.get("high_performing_actions"):
            recs.append(
                "All action types performing within normal range. "
                "No immediate adjustments needed."
            )

        return recs
