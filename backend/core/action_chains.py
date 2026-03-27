"""
Action Chaining / Reactive Pipeline — connects proactive behaviors so
scans trigger follow-up actions instead of being disconnected.

After any proactive action completes, the chain engine evaluates registered
chain rules and fires follow-up actions when conditions are met.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger("root.action_chains")

# Follow-up actions that trigger external side effects and need sandbox gating
_EXTERNAL_FOLLOW_UPS = frozenset({
    "auto_trade_cycle", "directive", "revenue_seeder",
    "self_rewrite", "notification", "business_discovery",
})


@dataclass(frozen=True)
class ActionChain:
    """A rule that links a trigger action to a follow-up action."""

    id: str
    trigger_action: str
    trigger_condition: Callable[[dict[str, Any]], bool]
    follow_up_action: str
    follow_up_args: dict[str, Any]
    description: str
    enabled: bool = True
    priority: int = 0
    cooldown_minutes: int = 5


@dataclass(frozen=True)
class ChainExecution:
    """Record of a chain execution."""

    id: str
    chain_id: str
    trigger_result: str
    follow_up_result: str
    triggered_at: str
    completed_at: str
    success: bool


class ActionChainEngine:
    """Evaluates chain rules after proactive actions and fires follow-ups."""

    def __init__(
        self,
        proactive_engine: Any = None,
        bus: Any = None,
        learning: Any = None,
    ) -> None:
        self._proactive_engine = proactive_engine
        self._bus = bus
        self._learning = learning
        self._sandbox_gate = None  # Set via main.py
        self._chains: dict[str, ActionChain] = {}
        self._executions: list[ChainExecution] = []
        self._last_fired: dict[str, str] = {}  # chain_id -> ISO timestamp

    def register_chain(self, chain: ActionChain) -> None:
        """Register a chain rule."""
        if not chain.id:
            raise ValueError("Chain must have an id")
        self._chains[chain.id] = chain
        logger.info("Registered chain: %s (%s)", chain.id, chain.description)

    async def evaluate_trigger(
        self, action_name: str, result: dict[str, Any]
    ) -> list[ChainExecution]:
        """Evaluate all chains for a completed action and fire matching follow-ups.

        Called after any proactive action completes. Returns executions created.
        """
        matching = [
            c for c in self._chains.values()
            if c.enabled and c.trigger_action == action_name
        ]
        # Sort by priority descending (higher priority first)
        matching.sort(key=lambda c: c.priority, reverse=True)

        executions: list[ChainExecution] = []
        for chain in matching:
            if not self._cooldown_ok(chain):
                logger.debug(
                    "Chain %s skipped — cooldown active", chain.id,
                )
                continue

            try:
                condition_met = chain.trigger_condition(result)
            except Exception as exc:
                logger.warning(
                    "Chain %s condition error: %s", chain.id, exc,
                )
                continue

            if not condition_met:
                continue

            logger.info(
                "Chain triggered: %s → %s",
                chain.trigger_action, chain.follow_up_action,
            )
            execution = await self._execute_follow_up(chain, result)
            executions.append(execution)

        return executions

    async def _execute_follow_up(
        self, chain: ActionChain, trigger_result: dict[str, Any],
    ) -> ChainExecution:
        """Run the follow-up action via proactive engine."""
        triggered_at = datetime.now(timezone.utc).isoformat()
        self._last_fired[chain.id] = triggered_at

        follow_up_result = ""
        success = False

        try:
            # Sandbox gate check for external follow-up actions
            if (
                self._sandbox_gate is not None
                and chain.follow_up_action in _EXTERNAL_FOLLOW_UPS
            ):
                decision = self._sandbox_gate.check(
                    system_id="proactive",
                    action=f"chain:{chain.follow_up_action}",
                    description=f"Chain follow-up: {chain.trigger_action} → {chain.follow_up_action}",
                    agent_id="action_chains",
                    risk_level="medium",
                )
                if not decision.was_executed:
                    logger.info("Sandbox blocked chain follow-up: %s", chain.follow_up_action)
                    return ChainExecution(
                        id=f"ce_{uuid.uuid4().hex[:12]}",
                        chain_id=chain.id,
                        trigger_result=f"{chain.trigger_action} → {chain.follow_up_action}",
                        follow_up_result="Sandboxed — external follow-up blocked",
                        triggered_at=triggered_at,
                        completed_at=triggered_at,
                        success=False,
                    )

            if self._proactive_engine:
                raw = await self._proactive_engine.trigger(chain.follow_up_action)
                follow_up_result = str(raw) if raw else "no result"
                success = True
            else:
                follow_up_result = "no proactive engine"

            if self._bus:
                msg = self._bus.create_message(
                    topic="system.chain",
                    sender="action_chain_engine",
                    payload={
                        "chain_id": chain.id,
                        "trigger": chain.trigger_action,
                        "follow_up": chain.follow_up_action,
                        "success": success,
                    },
                )
                await self._bus.publish(msg)

        except Exception as exc:
            follow_up_result = f"error: {exc}"
            logger.error("Chain %s follow-up failed: %s", chain.id, exc)

        completed_at = datetime.now(timezone.utc).isoformat()
        execution = ChainExecution(
            id=uuid.uuid4().hex[:12],
            chain_id=chain.id,
            trigger_result=str(trigger_result)[:500],
            follow_up_result=follow_up_result[:500],
            triggered_at=triggered_at,
            completed_at=completed_at,
            success=success,
        )
        self._executions.append(execution)
        return execution

    def _cooldown_ok(self, chain: ActionChain) -> bool:
        """Check whether cooldown has elapsed since last fire."""
        last = self._last_fired.get(chain.id)
        if not last:
            return True
        last_dt = datetime.fromisoformat(last)
        now = datetime.now(timezone.utc)
        elapsed = (now - last_dt).total_seconds() / 60
        return elapsed >= chain.cooldown_minutes

    def get_chains(self) -> list[dict[str, Any]]:
        """List all registered chains."""
        return [
            {
                "id": c.id,
                "trigger_action": c.trigger_action,
                "follow_up_action": c.follow_up_action,
                "description": c.description,
                "enabled": c.enabled,
                "priority": c.priority,
                "cooldown_minutes": c.cooldown_minutes,
            }
            for c in self._chains.values()
        ]

    def get_executions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Recent chain executions (most recent first)."""
        recent = self._executions[-limit:] if self._executions else []
        return [
            {
                "id": e.id,
                "chain_id": e.chain_id,
                "trigger_result": e.trigger_result[:200],
                "follow_up_result": e.follow_up_result[:200],
                "triggered_at": e.triggered_at,
                "completed_at": e.completed_at,
                "success": e.success,
            }
            for e in reversed(recent)
        ]

    def stats(self) -> dict[str, Any]:
        """Execution counts and success rates."""
        total = len(self._executions)
        successes = sum(1 for e in self._executions if e.success)
        return {
            "total_chains": len(self._chains),
            "enabled_chains": sum(1 for c in self._chains.values() if c.enabled),
            "total_executions": total,
            "successful_executions": successes,
            "failed_executions": total - successes,
            "success_rate": successes / max(total, 1),
        }


# ── Default chain conditions ────────────────────────────────────


def _scan_markets_has_signals(result: dict[str, Any]) -> bool:
    """True when market scan finds tradeable signals."""
    text = str(result).lower()
    signal_count = result.get("signal_count", 0)
    return signal_count > 0 or "signal" in text


def _business_discovery_has_opportunities(result: dict[str, Any]) -> bool:
    """True when business discovery finds substantial opportunities."""
    return len(str(result)) > 200


def _miro_high_confidence(result: dict[str, Any]) -> bool:
    """True when MiRo prediction shows high-confidence opportunity."""
    confidence = result.get("confidence", 0)
    if confidence > 70:
        return True
    text = str(result).lower()
    return "high confidence" in text or "strong signal" in text


def _health_has_issues(result: dict[str, Any]) -> bool:
    """True when health check finds problems."""
    text = str(result).lower()
    return "unhealthy" in text or "error" in text


def _goals_stalled(result: dict[str, Any]) -> bool:
    """True when goal tracking finds stalled goals."""
    text = str(result).lower()
    return "stalled" in text or "blocked" in text


def _ecosystem_found_opportunity(result: dict[str, Any]) -> bool:
    """True when ecosystem scanner finds cross-project synergies."""
    text = str(result).lower()
    return "synergy" in text or "opportunity" in text or "connection" in text


def _experiment_completed(result: dict[str, Any]) -> bool:
    """True when an experiment finishes — feed results into revenue engine."""
    text = str(result).lower()
    return "completed" in text or "success" in text or "result" in text


def _learning_has_insights(result: dict[str, Any]) -> bool:
    """True when learning engine produces actionable routing insights."""
    text = str(result).lower()
    return "insight" in text or "improvement" in text or "weight" in text


def _goal_assessment_needs_recovery(result: dict[str, Any]) -> bool:
    """True when goal assessment finds goals needing auto-recovery."""
    text = str(result).lower()
    return text.count("stalled") > 0 or "inactive" in text


def _survival_economics_emergency(result: dict[str, Any]) -> bool:
    """True when survival economics detects revenue emergency."""
    text = str(result).lower()
    return "emergency" in text or "negative profit" in text or "below survival" in text


def _code_scanner_found_issues(result: dict[str, Any]) -> bool:
    """True when code scanner created improvement proposals."""
    text = str(result).lower()
    return "proposal" in text and "0 improvement" not in text


def _revenue_tracker_found_risk(result: dict[str, Any]) -> bool:
    """True when revenue tracker flags risks or growth opportunities."""
    text = str(result).lower()
    return "warning" in text or "alert" in text or "growth opportunity" in text


def _experiment_runner_scaled(result: dict[str, Any]) -> bool:
    """True when experiment runner scales a successful experiment."""
    text = str(result).lower()
    return "scaled" in text and "0 scaled" not in text


def build_default_chains(
    proactive_engine: Any = None,
    bus: Any = None,
    learning: Any = None,
) -> ActionChainEngine:
    """Build an ActionChainEngine with pre-registered default chains."""
    engine = ActionChainEngine(
        proactive_engine=proactive_engine,
        bus=bus,
        learning=learning,
    )

    defaults = [
        ActionChain(
            id="scan_markets_to_trade",
            trigger_action="market_scanner",
            trigger_condition=_scan_markets_has_signals,
            follow_up_action="auto_trade_cycle",
            follow_up_args={},
            description="When market scan finds signals, trigger auto trade cycle",
            priority=10,
            cooldown_minutes=30,
        ),
        ActionChain(
            id="business_to_directive",
            trigger_action="business_discovery",
            trigger_condition=_business_discovery_has_opportunities,
            follow_up_action="directive",
            follow_up_args={},
            description="When business discovery finds opportunities, create directive",
            priority=5,
            cooldown_minutes=60,
        ),
        ActionChain(
            id="miro_to_scan",
            trigger_action="miro_prediction",
            trigger_condition=_miro_high_confidence,
            follow_up_action="market_scanner",
            follow_up_args={},
            description="When MiRo predicts high-confidence opportunity, trigger market scan",
            priority=8,
            cooldown_minutes=15,
        ),
        ActionChain(
            id="health_to_notification",
            trigger_action="health_monitor",
            trigger_condition=_health_has_issues,
            follow_up_action="notification",
            follow_up_args={},
            description="When health check finds issues, trigger notification",
            priority=15,
            cooldown_minutes=5,
        ),
        ActionChain(
            id="goals_to_assess",
            trigger_action="goal_tracker",
            trigger_condition=_goals_stalled,
            follow_up_action="goal_assessment",
            follow_up_args={},
            description="When goal tracking finds stalled goals, trigger assessment",
            priority=5,
            cooldown_minutes=30,
        ),
        ActionChain(
            id="ecosystem_to_directive",
            trigger_action="ecosystem_scanner",
            trigger_condition=_ecosystem_found_opportunity,
            follow_up_action="directive",
            follow_up_args={},
            description="When ecosystem scan finds cross-project synergies, create directive",
            priority=7,
            cooldown_minutes=60,
        ),
        ActionChain(
            id="experiment_to_revenue",
            trigger_action="experiment_proposer",
            trigger_condition=_experiment_completed,
            follow_up_action="revenue_seeder",
            follow_up_args={},
            description="When experiments complete successfully, feed into revenue engine",
            priority=6,
            cooldown_minutes=120,
        ),
        ActionChain(
            id="learning_to_improvement",
            trigger_action="skill_discovery",
            trigger_condition=_learning_has_insights,
            follow_up_action="experiment_proposer",
            follow_up_args={},
            description="When skill discovery finds insights, trigger experiment proposals",
            priority=4,
            cooldown_minutes=60,
        ),
        ActionChain(
            id="code_scanner_to_rewrite",
            trigger_action="code_scanner",
            trigger_condition=_code_scanner_found_issues,
            follow_up_action="self_rewrite",
            follow_up_args={},
            description="When code scanner finds improvements, trigger self-rewrite review",
            priority=3,
            cooldown_minutes=120,
        ),
        ActionChain(
            id="revenue_tracker_to_directive",
            trigger_action="revenue_tracker",
            trigger_condition=_revenue_tracker_found_risk,
            follow_up_action="directive",
            follow_up_args={},
            description="When revenue tracker flags risks, generate strategic directive",
            priority=9,
            cooldown_minutes=60,
        ),
        ActionChain(
            id="experiment_runner_to_discovery",
            trigger_action="experiment_runner",
            trigger_condition=_experiment_runner_scaled,
            follow_up_action="business_discovery",
            follow_up_args={},
            description="When experiments scale successfully, trigger business discovery for expansion",
            priority=6,
            cooldown_minutes=120,
        ),
        # ── Actuator chains: close feedback loops ──
        ActionChain(
            id="goal_stalled_to_recovery",
            trigger_action="goal_assessment",
            trigger_condition=_goal_assessment_needs_recovery,
            follow_up_action="goal_assessment",
            follow_up_args={},
            description="When goals are stalled, trigger auto-recovery decomposition",
            priority=12,
            cooldown_minutes=60,
        ),
        ActionChain(
            id="survival_to_revenue_remediation",
            trigger_action="survival_economics",
            trigger_condition=_survival_economics_emergency,
            follow_up_action="revenue_tracker",
            follow_up_args={},
            description="When survival economics detects emergency, trigger revenue tracking for remediation",
            priority=15,
            cooldown_minutes=30,
        ),
        ActionChain(
            id="health_to_goal_assessment",
            trigger_action="health_monitor",
            trigger_condition=_health_has_issues,
            follow_up_action="goal_assessment",
            follow_up_args={},
            description="When health issues found, assess goals that may be blocked by the issue",
            priority=8,
            cooldown_minutes=15,
        ),
    ]

    for chain in defaults:
        engine.register_chain(chain)

    logger.info("Built %d default action chains", len(defaults))
    return engine
