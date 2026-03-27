"""
Autonomy Actuator — the ACTION layer that closes ROOT's feedback loops.

ROOT's systems detect problems but rarely fix them. The Actuator bridges
observer systems to corrective actions:

1. Experiment success → auto-apply routing weight updates + deploy strategies
2. Stalled goal → auto-decompose into sub-goals + retry with different agents
3. Revenue emergency → auto-pause underperforming products + trigger cost-cutting
4. Learning insight → auto-create directives that change agent behavior
5. Task completion → auto-advance parent goal progress
6. Health issue → auto-remediate (restart, reassign, escalate)
7. Approval timeout → auto-escalate stale pending approvals
8. Agent underperformance → auto-demote routing weight + reassign tasks

This module subscribes to MessageBus topics and acts on events autonomously.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.actuator")


class AutonomyActuator:
    """Central autonomous action engine that turns observations into actions.

    Subscribes to system events via MessageBus and takes corrective actions
    without waiting for human intervention (respecting approval chain for
    HIGH/CRITICAL risk).
    """

    def __init__(
        self,
        bus: Any = None,
        learning: Any = None,
        goal_engine: Any = None,
        task_queue: Any = None,
        revenue_engine: Any = None,
        directive_engine: Any = None,
        approval_chain: Any = None,
        notification_engine: Any = None,
        experiment_lab: Any = None,
        memory: Any = None,
        collab: Any = None,
        llm: Any = None,
        state_store: Any = None,
    ) -> None:
        self._bus = bus
        self._learning = learning
        self._goal_engine = goal_engine
        self._task_queue = task_queue
        self._revenue = revenue_engine
        self._directive = directive_engine
        self._approval = approval_chain
        self._notifications = notification_engine
        self._experiment_lab = experiment_lab
        self._memory = memory
        self._collab = collab
        self._llm = llm
        self._state_store = state_store

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._actions_taken = 0
        self._failure_count: int = 0
        self._actions_log: list[dict[str, Any]] = []

    # ── Lifecycle ──────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the actuator — subscribe to bus events."""
        if self._running:
            return
        self._running = True

        # Subscribe to all relevant system events
        if self._bus:
            self._bus.subscribe("system.learning", "actuator_learning", self._on_learning_event)
            self._bus.subscribe("system.proactive", "actuator_proactive", self._on_proactive_event)
            self._bus.subscribe("system.directive", "actuator_directive", self._on_directive_event)
            self._bus.subscribe("system.approval", "actuator_approval", self._on_approval_event)
            self._bus.subscribe("system.chain", "actuator_chain", self._on_chain_event)
            self._bus.subscribe("task.*", "actuator_task", self._on_task_event)

        # Start background loops
        self._task = asyncio.create_task(self._background_loop())
        logger.info("AutonomyActuator started — listening for events")

    def stop(self) -> None:
        """Stop the actuator."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("AutonomyActuator stopped (%d actions taken)", self._actions_taken)

    # ── Event Handlers ─────────────────────────────────────────────

    async def _on_learning_event(self, message: Any) -> None:
        """React to learning engine events."""
        payload = getattr(message, "payload", {})
        event_type = payload.get("type", "")

        if event_type == "cycle_complete":
            kept = payload.get("results", {}).get("kept", 0)
            if kept > 0:
                await self._apply_experiment_wins(payload)

        elif event_type == "learning_cycle":
            findings = payload.get("findings", 0)
            if findings > 0:
                await self._learning_to_directives(payload)

    async def _on_proactive_event(self, message: Any) -> None:
        """React to proactive engine events."""
        payload = getattr(message, "payload", {})
        action = payload.get("action", "")
        result = payload.get("result", "")

        # Health issues → auto-remediate
        if action == "health_monitor" and ("unhealthy" in result.lower() or "error" in result.lower()):
            await self._auto_remediate_health(payload)

        # Goal assessment → auto-recover stalled
        if action == "goal_assessment" and "stalled" in result.lower():
            await self._auto_recover_stalled_goals()

        # Revenue tracker → auto-remediate emergency
        if action == "revenue_tracker" and ("warning" in result.lower() or "emergency" in result.lower()):
            await self._auto_remediate_revenue()

        # Survival economics → emergency action
        if action == "survival_economics" and "emergency" in result.lower():
            await self._auto_remediate_revenue()

    async def _on_directive_event(self, message: Any) -> None:
        """React to directive engine events — learn from outcomes."""
        payload = getattr(message, "payload", {})
        if payload.get("type") == "directive_completed":
            category = payload.get("category", "")
            result = payload.get("result", "")
            # Boost routing weights for agents that contributed to successful directives
            if self._learning and result:
                title = payload.get("title", "")
                self._log_action(
                    "directive_feedback",
                    f"Recording directive success for category={category}: {title[:80]}",
                )

    async def _on_approval_event(self, message: Any) -> None:
        """React to approval events — track pending for timeout."""
        # Timeout handling is done in the background loop
        pass

    async def _on_chain_event(self, message: Any) -> None:
        """React to chain execution events."""
        payload = getattr(message, "payload", {})
        if not payload.get("success", True):
            chain_id = payload.get("chain_id", "")
            logger.warning("Action chain %s failed — actuator may retry", chain_id)

    async def _on_task_event(self, message: Any) -> None:
        """React to task completion — advance parent goal progress."""
        payload = getattr(message, "payload", {})
        event = payload.get("event", "")

        if event == "task_complete":
            task_id = payload.get("task_id", "")
            await self._task_to_goal_progress(task_id)

    # ── Autonomous Actions ─────────────────────────────────────────

    async def _apply_experiment_wins(self, payload: dict) -> None:
        """When experiments succeed, apply their findings to routing weights."""
        if not self._learning:
            return

        self._log_action("apply_experiment_wins", "Auto-applying successful experiment results to routing")

        # Get recent successful experiments from the learning engine
        insights = self._learning.get_insights()
        best_area = insights.get("best_experiment_area", {})
        if best_area:
            area = best_area.get("area", "")
            success_rate = best_area.get("success_rate", 0)

            # If an experiment area consistently succeeds, boost agents in that area
            area_to_agents = {
                "knowledge": ["researcher"],
                "skills": ["builder", "coder"],
                "memory": ["researcher"],
                "agents": ["analyst"],
                "goals": ["analyst", "researcher"],
                "trading": ["swarm", "analyst"],
                "strategy": ["analyst", "miro"],
            }
            agents = area_to_agents.get(area, [])
            for agent_id in agents:
                if success_rate > 0.6:
                    new_weight = self._learning.boost_routing_weight(
                        agent_id, area, amount=0.03,
                    )
                    logger.info(
                        "Actuator: boosted %s weight for %s → %.3f (experiment success rate: %.1f%%)",
                        agent_id, area, new_weight, success_rate * 100,
                    )

        # Scale successful experiments in experiment lab
        if self._experiment_lab:
            try:
                completed = self._experiment_lab.get_completed(limit=5)
                for exp in completed:
                    if exp.status.value == "completed" and exp.confidence >= 0.7:
                        self._experiment_lab.scale_experiment(exp.id)
                        self._log_action(
                            "scale_experiment",
                            f"Auto-scaled experiment {exp.id}: {exp.title[:80]}",
                        )
            except Exception as exc:
                logger.warning("Actuator: experiment scaling failed: %s", exc)

    async def _auto_recover_stalled_goals(self) -> None:
        """Auto-decompose stalled goals into tasks and retry."""
        if not self._goal_engine:
            return

        assessment = await self._goal_engine.assess_all_goals()
        stalled = [u for u in assessment.get("updates", []) if u.get("status") == "stalled"]

        for stall in stalled[:3]:  # Max 3 recoveries per cycle
            goal_id = stall.get("goal_id", "")
            title = stall.get("title", "")
            days_inactive = stall.get("days_inactive", 0)

            if days_inactive < 7:
                continue  # Only act on goals stalled 7+ days

            self._log_action(
                "goal_auto_recovery",
                f"Auto-recovering stalled goal: {title[:80]} (inactive {days_inactive}d)",
            )

            # Decompose into fresh tasks
            try:
                task_ids = await self._goal_engine.decompose_goal(goal_id)
                if task_ids:
                    logger.info(
                        "Actuator: decomposed stalled goal %s into %d tasks",
                        goal_id, len(task_ids),
                    )

                    # Notify about recovery action
                    if self._notifications:
                        self._notifications.notify(
                            title=f"Goal auto-recovery: {title[:60]}",
                            message=f"Stalled {days_inactive}d — decomposed into {len(task_ids)} new tasks",
                            level="medium",
                            source="actuator",
                        )
            except Exception as exc:
                logger.error("Actuator: goal recovery failed for %s: %s", goal_id, exc)

            # If goal has been stalled 14+ days, try a different approach
            if days_inactive >= 14 and self._collab:
                try:
                    goal = self._goal_engine.get_goal(goal_id)
                    if goal:
                        result = await self._collab.delegate(
                            from_agent="actuator",
                            to_agent="analyst",
                            task=(
                                f"This goal has been stalled for {days_inactive} days: "
                                f"'{goal.title}' — {goal.description[:300]}. "
                                f"Propose 3 alternative approaches to unblock it. "
                                f"Consider different agents, tools, or strategies."
                            ),
                        )
                        if result.final_result and self._memory:
                            from backend.models.memory import MemoryEntry, MemoryType
                            self._memory.store(MemoryEntry(
                                content=f"[Actuator] Goal recovery plan for '{title}': {result.final_result[:500]}",
                                memory_type=MemoryType.LEARNING,
                                tags=["actuator", "goal_recovery", goal_id],
                                source="autonomy_actuator",
                                confidence=0.75,
                            ))
                except Exception as exc:
                    logger.error("Actuator: alternative recovery failed: %s", exc)

    async def _auto_remediate_revenue(self) -> None:
        """When revenue emergency detected, take corrective actions."""
        if not self._revenue:
            return

        snapshot = self._revenue.get_financial_snapshot()
        if not snapshot.emergency_mode:
            return

        self._log_action(
            "revenue_remediation",
            f"Emergency mode active — revenue ${snapshot.total_revenue:.0f} < cost ${snapshot.total_cost:.0f}",
        )

        # Action 1: Pause underperforming products (negative profit)
        products = self._revenue.get_products(limit=50)
        paused_count = 0
        for product in products:
            profit = product.monthly_revenue - product.monthly_cost
            if profit < -50 and product.status.value not in ("paused", "idea"):
                self._revenue.update_status(product.id, "paused")
                paused_count += 1
                logger.info(
                    "Actuator: paused unprofitable product %s (profit: $%.0f)",
                    product.name, profit,
                )

        # Action 2: Create cost-cutting directive
        if self._directive and self._directive._llm:
            from backend.core.directive_engine import Directive
            import uuid
            cost_directive = Directive(
                id=f"dir_{uuid.uuid4().hex[:12]}",
                title="EMERGENCY: Reduce operating costs and boost revenue",
                rationale=f"Revenue emergency — profit ${snapshot.profit:.0f}, {paused_count} products paused",
                priority=1,
                category="product",
                assigned_agents=("analyst", "researcher"),
                collab_pattern="pipeline",
                task_description=(
                    f"URGENT: Revenue is ${snapshot.total_revenue:.0f}/mo, costs are "
                    f"${snapshot.total_cost:.0f}/mo. {paused_count} underperforming products "
                    f"have been auto-paused. Analyze remaining products and propose: "
                    f"1) Which costs to cut immediately, 2) Which products to double down on, "
                    f"3) New quick-win revenue opportunities."
                ),
                source_signals=("emergency_mode", "actuator"),
            )
            self._directive._store_directive(cost_directive)
            logger.info("Actuator: created emergency cost-cutting directive %s", cost_directive.id)

        # Action 3: Create recovery goal
        if self._goal_engine:
            try:
                self._goal_engine.add_goal(
                    title="Revenue recovery — exit emergency mode",
                    description=(
                        f"Current state: revenue ${snapshot.total_revenue:.0f}/mo, "
                        f"cost ${snapshot.total_cost:.0f}/mo. "
                        f"Target: achieve positive profit within 30 days."
                    ),
                    priority=1,
                    source="autonomous",
                    category="trading",
                    metadata={"trigger": "revenue_emergency", "auto_created": True},
                )
            except Exception as exc:
                logger.warning("Actuator: recovery goal creation failed: %s", exc)

        # Notify
        if self._notifications:
            self._notifications.notify(
                title="REVENUE EMERGENCY — Auto-remediation active",
                message=(
                    f"Profit: ${snapshot.profit:.0f}/mo. "
                    f"Paused {paused_count} products. Created cost-cutting directive."
                ),
                level="critical",
                source="actuator",
            )

    async def _learning_to_directives(self, payload: dict) -> None:
        """When continuous learning produces findings, create directives."""
        if not self._directive or not self._learning:
            return

        insights = self._learning.get_insights()

        # If quality is declining, create improvement directive
        quality_trend = insights.get("quality_trend", {})
        if quality_trend.get("direction") == "declining":
            delta = quality_trend.get("delta", 0)
            self._log_action(
                "learning_to_directive",
                f"Quality declining ({delta:.3f}) — creating improvement directive",
            )
            import uuid
            from backend.core.directive_engine import Directive
            directive = Directive(
                id=f"dir_{uuid.uuid4().hex[:12]}",
                title="Improve interaction quality — declining trend detected",
                rationale=f"Quality trend: {quality_trend}",
                priority=3,
                category="learning",
                assigned_agents=("analyst", "researcher"),
                collab_pattern="pipeline",
                task_description=(
                    f"Interaction quality is declining (delta: {delta:.3f}). "
                    f"Analyze recent interactions, identify why quality dropped, "
                    f"and propose specific routing or agent improvements."
                ),
                source_signals=("quality_decline", "actuator"),
            )
            self._directive._store_directive(directive)

        # If misrouted interactions are high, create routing fix directive
        misrouted = insights.get("misrouted_count", 0)
        if misrouted > 5:
            self._log_action(
                "routing_fix_directive",
                f"High misroute count ({misrouted}) — creating routing improvement directive",
            )
            import uuid
            from backend.core.directive_engine import Directive
            worst = insights.get("worst_agent", {})
            directive = Directive(
                id=f"dir_{uuid.uuid4().hex[:12]}",
                title=f"Fix routing — {misrouted} misrouted interactions detected",
                rationale=f"Worst agent: {worst.get('id', 'unknown')} (quality: {worst.get('avg_quality', 0)})",
                priority=4,
                category="automation",
                assigned_agents=("analyst",),
                collab_pattern="delegate",
                task_description=(
                    f"{misrouted} interactions were routed as 'direct' but scored below 0.4 quality. "
                    f"Analyze which queries should have gone to specialist agents. "
                    f"Propose routing rule updates."
                ),
                source_signals=("misrouted_high", "actuator"),
            )
            self._directive._store_directive(directive)

        # Auto-demote underperforming agents
        worst = insights.get("worst_agent", {})
        best = insights.get("best_agent", {})
        if worst and best:
            worst_quality = worst.get("avg_quality", 0.5)
            if worst_quality < 0.3:
                agent_id = worst.get("id", "")
                if agent_id:
                    new_weight = self._learning.boost_routing_weight(
                        agent_id, "general", amount=-0.05,
                    )
                    self._log_action(
                        "demote_agent",
                        f"Auto-demoted {agent_id} routing weight → {new_weight:.3f} (quality: {worst_quality:.2f})",
                    )

    async def _task_to_goal_progress(self, task_id: str) -> None:
        """When a task completes, advance its parent goal's progress."""
        if not self._goal_engine or not self._task_queue:
            return

        try:
            task = self._task_queue.get_task(task_id)
            if not task:
                return

            metadata = getattr(task, "metadata", {})
            if isinstance(metadata, str):
                import json
                try:
                    metadata = json.loads(metadata)
                except (json.JSONDecodeError, TypeError):
                    metadata = {}

            goal_id = metadata.get("goal_id")
            if not goal_id:
                return

            # Record task completion on the goal
            self._goal_engine.record_task_completion(goal_id)

            # Check if goal should auto-complete
            goal = self._goal_engine.get_goal(goal_id)
            if goal and goal.tasks_generated > 0:
                completion_ratio = goal.tasks_completed / goal.tasks_generated
                if completion_ratio >= 1.0:
                    self._goal_engine.update_progress(goal_id, 1.0, "All tasks completed (actuator)")
                    self._log_action(
                        "goal_auto_complete",
                        f"Auto-completed goal: {goal.title[:80]}",
                    )
                else:
                    # Update progress proportionally
                    self._goal_engine.update_progress(
                        goal_id, completion_ratio,
                        f"Task completed ({goal.tasks_completed}/{goal.tasks_generated})",
                    )
        except Exception as exc:
            logger.debug("Actuator: task→goal progress failed: %s", exc)

    async def _auto_remediate_health(self, payload: dict) -> None:
        """When health issues detected, take corrective action."""
        result = payload.get("result", "")

        self._log_action("health_remediation", f"Health issue detected: {result[:120]}")

        # Create a high-priority task to investigate
        if self._task_queue:
            try:
                self._task_queue.enqueue(
                    goal=f"Investigate and fix health issue: {result[:200]}",
                    priority=2,
                    source="actuator",
                    metadata={"trigger": "health_alert", "auto_created": True},
                )
            except Exception as exc:
                logger.warning("Actuator: health task creation failed: %s", exc)

        # Notify
        if self._notifications:
            self._notifications.notify(
                title="Health issue detected — auto-investigating",
                message=result[:200],
                level="high",
                source="actuator",
            )

    async def _check_approval_timeouts(self) -> None:
        """Auto-escalate or auto-resolve stale pending approvals."""
        if not self._approval:
            return

        pending = self._approval.get_pending()
        now = datetime.now(timezone.utc)

        for req in pending:
            try:
                created = datetime.fromisoformat(req.created_at)
                age_minutes = (now - created).total_seconds() / 60

                # After 30 minutes: escalate via notification
                if 30 <= age_minutes < 60:
                    if self._notifications:
                        self._notifications.notify(
                            title=f"Approval pending 30min: {req.action}",
                            message=f"[{req.risk_level.value}] {req.description[:150]}",
                            level="high",
                            source="actuator",
                        )

                # After 60 minutes: notify urgently — never auto-approve HIGH or CRITICAL
                elif age_minutes >= 60:
                    if req.risk_level.value in ("high", "critical"):
                        # Critical: never auto-approve, but notify urgently
                        if self._notifications:
                            self._notifications.notify(
                                title=f"CRITICAL approval stale ({age_minutes:.0f}min): {req.action}",
                                message=f"Requires manual resolution: {req.description[:150]}",
                                level="critical",
                                source="actuator",
                            )
            except (ValueError, TypeError):
                continue

    async def _auto_demote_underperformers(self) -> None:
        """Periodically check agent performance and adjust routing weights."""
        if not self._learning:
            return

        weights = self._learning.get_routing_weights()
        if not weights:
            return

        # Find agents with very low weights and many failures
        for key, weight in weights.items():
            if weight < 0.25:
                parts = key.split(":", 1)
                if len(parts) == 2:
                    agent_id, category = parts
                    stats = self._learning.get_agent_stats(agent_id)
                    if stats.get("total", 0) >= 5 and stats.get("success_rate", 1.0) < 0.3:
                        self._log_action(
                            "agent_underperformer",
                            f"Agent {agent_id} severely underperforming in {category} "
                            f"(weight: {weight:.3f}, success: {stats.get('success_rate', 0):.1%})",
                        )

    # ── Background Loop ────────────────────────────────────────────

    async def _background_loop(self) -> None:
        """Periodic autonomous checks."""
        await asyncio.sleep(300)  # Let systems warm up

        while self._running:
            try:
                # Check approval timeouts every 5 minutes
                await self._check_approval_timeouts()

                # Check stalled goals every 30 minutes
                await self._auto_recover_stalled_goals()

                # Check revenue health every 30 minutes
                await self._auto_remediate_revenue()

                # Check agent performance every hour
                await self._auto_demote_underperformers()

                self._failure_count = 0
            except Exception as exc:
                self._failure_count = self._failure_count + 1
                logger.error("Actuator background loop error: %s", exc)
                if self._failure_count >= 5:
                    logger.critical(
                        "Autonomy actuator: %d consecutive failures — backing off 300s",
                        self._failure_count,
                    )
                    self._failure_count = 0
                    await asyncio.sleep(300)
                    continue

            await asyncio.sleep(300)  # Run checks every 5 minutes

    # ── Logging & Stats ────────────────────────────────────────────

    def _log_action(self, action_type: str, description: str) -> None:
        """Log an autonomous action taken."""
        self._actions_taken += 1
        entry = {
            "type": action_type,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        self._actions_log = [*self._actions_log[-199:], entry]
        logger.info("Actuator [%s]: %s", action_type, description)

    def get_actions_log(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get recent actuator actions."""
        return list(reversed(self._actions_log[-limit:]))

    def stats(self) -> dict[str, Any]:
        """Actuator statistics."""
        by_type: dict[str, int] = {}
        for entry in self._actions_log:
            t = entry["type"]
            by_type[t] = by_type.get(t, 0) + 1

        return {
            "running": self._running,
            "total_actions_taken": self._actions_taken,
            "recent_actions": len(self._actions_log),
            "by_type": by_type,
        }
