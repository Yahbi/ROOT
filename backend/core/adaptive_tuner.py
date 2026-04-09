"""
Adaptive Tuner — background task that analyzes outcome data and
proposes parameter adjustments.

Runs on a 2-hour cycle by default.  For each action type it checks
outcome quality data from the LearningEngine, and nudges the
corresponding interval parameter:

- Underperforming (avg_quality < 0.3) => increase interval by 10% (run less often)
- Overperforming  (avg_quality > 0.7 and count > 5) => decrease interval by 5% (run more often)

MAX adjustment per cycle: 10% of current value.  Never exceeds bounds.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.adaptive")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Mapping from action types to tunable interval params ─────────

_ACTION_PARAM_MAP: dict[str, str] = {
    "market_scanner": "proactive_market_interval",
    "health_monitor": "proactive_health_interval",
    "goal_tracker": "proactive_goal_interval",
    "autonomous_loop": "autonomous_loop_interval",
    "directive": "directive_cycle_interval",
}

# Quality thresholds
_UNDERPERFORM_THRESHOLD = 0.3
_OVERPERFORM_THRESHOLD = 0.7
_OVERPERFORM_MIN_COUNT = 5

# Adjustment rates (fraction of current value)
_UNDERPERFORM_INCREASE = 0.10  # +10% interval (less frequent)
_OVERPERFORM_DECREASE = 0.05   # -5% interval (more frequent)


@dataclass(frozen=True)
class TuneAdjustment:
    """Immutable record of a single tuning adjustment."""

    param: str
    action_type: str
    old_value: float
    new_value: float
    avg_quality: float
    sample_count: int
    reason: str
    adjusted_at: str = field(default_factory=_now_iso)


class AdaptiveTuner:
    """Analyzes outcome data and proposes parameter adjustments.

    Dependencies:
        adaptive_config — AdaptiveConfig instance for reading/writing params
        learning_engine — LearningEngine for outcome quality data (via agent_outcomes)
    """

    def __init__(
        self,
        adaptive_config: Any = None,
        outcome_registry: Any = None,
        learning_engine: Any = None,
    ) -> None:
        self._config = adaptive_config
        self._outcome_registry = outcome_registry
        self._learning = learning_engine
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._total_cycles = 0
        self._total_adjustments = 0
        self._last_cycle_at: Optional[str] = None
        self._history: deque[TuneAdjustment] = deque(maxlen=500)

    # ── Main tuning cycle ─────────────────────────────────────

    async def tune(self) -> dict[str, Any]:
        """Run a single tuning cycle.

        1. Get action effectiveness from learning engine
        2. For each action type, check under/over-performance
        3. Adjust the corresponding interval parameter
        4. Return summary of adjustments made
        """
        adjustments: list[dict[str, Any]] = []

        if not self._config or not self._learning:
            logger.warning("AdaptiveTuner.tune() skipped — missing config or learning engine")
            return {"adjustments": [], "skipped": True, "reason": "missing dependencies"}

        try:
            effectiveness = self._get_action_effectiveness()
        except Exception as exc:
            logger.error("Failed to get action effectiveness: %s", exc)
            return {"adjustments": [], "error": str(exc)}

        for action_type, param_name in _ACTION_PARAM_MAP.items():
            data = effectiveness.get(action_type)
            if data is None:
                continue

            avg_quality = data.get("avg_quality", 0.5)
            count = data.get("count", 0)

            try:
                current = self._config.get(param_name)
            except (KeyError, RuntimeError):
                continue

            # Cap maximum delta at 10% of current value
            max_delta = current * 0.10

            adjustment = None

            if avg_quality < _UNDERPERFORM_THRESHOLD and count > 0:
                # Underperforming — increase interval (run less often)
                delta = min(current * _UNDERPERFORM_INCREASE, max_delta)
                reason = (
                    f"{action_type} underperforming (avg_quality={avg_quality:.3f}, "
                    f"n={count}): increasing interval by {delta:.1f}s"
                )
                new_value = self._config.adjust(param_name, delta, reason=reason)
                adjustment = TuneAdjustment(
                    param=param_name,
                    action_type=action_type,
                    old_value=current,
                    new_value=new_value,
                    avg_quality=avg_quality,
                    sample_count=count,
                    reason=reason,
                )

            elif avg_quality > _OVERPERFORM_THRESHOLD and count > _OVERPERFORM_MIN_COUNT:
                # Overperforming — decrease interval (run more often)
                delta = min(current * _OVERPERFORM_DECREASE, max_delta)
                reason = (
                    f"{action_type} overperforming (avg_quality={avg_quality:.3f}, "
                    f"n={count}): decreasing interval by {delta:.1f}s"
                )
                new_value = self._config.adjust(param_name, -delta, reason=reason)
                adjustment = TuneAdjustment(
                    param=param_name,
                    action_type=action_type,
                    old_value=current,
                    new_value=new_value,
                    avg_quality=avg_quality,
                    sample_count=count,
                    reason=reason,
                )

            if adjustment is not None:
                self._history.append(adjustment)
                self._total_adjustments += 1
                adjustments.append({
                    "param": adjustment.param,
                    "action_type": adjustment.action_type,
                    "old_value": adjustment.old_value,
                    "new_value": adjustment.new_value,
                    "avg_quality": adjustment.avg_quality,
                    "sample_count": adjustment.sample_count,
                    "reason": adjustment.reason,
                })
                logger.info("Tuned %s: %.1f -> %.1f (%s)", adjustment.param, adjustment.old_value, adjustment.new_value, adjustment.reason)

        self._total_cycles += 1
        self._last_cycle_at = _now_iso()

        if adjustments:
            logger.info("Tuning cycle complete: %d adjustment(s)", len(adjustments))
        else:
            logger.debug("Tuning cycle complete: no adjustments needed")

        return {
            "adjustments": adjustments,
            "cycle": self._total_cycles,
            "timestamp": self._last_cycle_at,
        }

    # ── Background loop ───────────────────────────────────────

    async def start_loop(self, interval: int = 7200) -> None:
        """Run ``tune()`` every *interval* seconds (default 2 hours)."""
        if self._running:
            logger.warning("AdaptiveTuner loop already running")
            return
        self._running = True
        self._task = asyncio.current_task()
        await self._loop(interval)

    async def _loop(self, interval: int) -> None:
        logger.info("AdaptiveTuner loop started (interval=%ds)", interval)
        while self._running:
            try:
                await self.tune()
            except Exception as exc:
                logger.error("Tuning cycle error: %s", exc)
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
        logger.info("AdaptiveTuner loop stopped")

    def stop(self) -> None:
        """Stop the background tuning loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            self._task = None
        logger.info("AdaptiveTuner stopped")

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Summary statistics for the adaptive tuner."""
        return {
            "total_cycles": self._total_cycles,
            "total_adjustments": self._total_adjustments,
            "last_cycle_at": self._last_cycle_at,
            "running": self._running,
            "recent_adjustments": [
                {
                    "param": a.param,
                    "old_value": a.old_value,
                    "new_value": a.new_value,
                    "reason": a.reason,
                    "adjusted_at": a.adjusted_at,
                }
                for a in self._history[-10:]
            ],
        }

    # ── Internal helpers ──────────────────────────────────────

    def _get_action_effectiveness(self) -> dict[str, dict[str, Any]]:
        """Pull per-action-type quality summaries from the learning engine.

        Uses the ``agent_outcomes`` table, grouping by ``task_category``
        (which maps to action types).  Falls back to the outcome_registry
        if provided and the learning engine has no data.
        """
        results: dict[str, dict[str, Any]] = {}

        # Primary source: learning engine's agent_outcomes
        if self._learning and hasattr(self._learning, "conn"):
            try:
                rows = self._learning.conn.execute(
                    """SELECT task_category,
                              COUNT(*) as count,
                              AVG(result_quality) as avg_quality
                       FROM agent_outcomes
                       WHERE created_at > datetime('now', '-48 hours')
                       GROUP BY task_category"""
                ).fetchall()
                for r in rows:
                    results[r["task_category"]] = {
                        "count": r["count"],
                        "avg_quality": round(r["avg_quality"] or 0.5, 4),
                    }
            except Exception as exc:
                logger.warning("Failed to query learning engine: %s", exc)

        # Secondary source: outcome_registry (if provided and has a get method)
        if self._outcome_registry and hasattr(self._outcome_registry, "get_effectiveness"):
            try:
                extra = self._outcome_registry.get_effectiveness()
                for action_type, data in extra.items():
                    if action_type not in results:
                        results[action_type] = data
            except Exception as exc:
                logger.debug("outcome_registry.get_effectiveness() failed: %s", exc)

        return results
