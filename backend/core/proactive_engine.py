"""
Proactive Engine — autonomous background actions for ROOT.

From HERMES proactive behavior + YOHAN-Command-Center proactive.js:
ROOT doesn't just respond — it anticipates, monitors, and acts on its own.

Proactive behaviors:
1. Morning briefing — summarize overnight activity, market conditions, pending tasks
2. Opportunity scanning — continuously look for opportunities aligned with Yohan's goals
3. Health monitoring — check all agent/service health, alert on issues
4. Knowledge gaps — identify and fill knowledge gaps autonomously
5. Skill evolution — create new skills from successful patterns
6. Memory consolidation — prune, strengthen, and organize knowledge
7. Goal tracking — monitor progress toward Yohan's stated goals
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from backend.config import PROACTIVE_INTERVALS
from backend.core.approval_chain import ApprovalStatus
from backend.core.proactive_actions import (
    assess_goals,
    auto_trade_cycle,
    business_discovery,
    check_health,
    consolidate_knowledge,
    data_intelligence,
    discover_skills,
    drain_task_queue,
    evolve_agents,
    experiment_proposer,
    miro_continuous_assess,
    miro_predict,
    miro_world_intelligence,
    miro_daily_briefing,
    scan_github,
    scan_markets,
    scan_opportunities,
    correlate_projects,
    run_experiments,
    scan_code_improvements,
    scan_project_ecosystem,
    seed_revenue_products,
    self_rewrite,
    survival_economics,
    track_goals,
    track_revenue_health,
    check_approval_timeouts,
    auto_recover_goals,
    auto_remediate_revenue,
    validate_strategies,
    deploy_promoted_strategies,
    scalp_trade_cycle,
    scan_polymarkets,
    polymarket_trade_cycle,
    monitor_polymarket_positions,
)

logger = logging.getLogger("root.proactive")


class ProactiveAction:
    """Represents a proactive action ROOT can take."""

    def __init__(
        self,
        name: str,
        description: str,
        interval_seconds: int,
        handler,
        enabled: bool = True,
        risk_level: str = "low",
    ) -> None:
        self.name = name
        self.description = description
        self.interval_seconds = interval_seconds
        self.handler = handler
        self.enabled = enabled
        self.risk_level = risk_level
        self.last_run: Optional[str] = None
        self.run_count = 0
        self.error_count = 0
        self.last_result: Optional[str] = None


class ProactiveEngine:
    """Manages autonomous background behaviors for ROOT.

    Each behavior runs on its own interval, checks conditions,
    and takes action through the collaboration system or directly.
    """

    def __init__(
        self,
        memory=None,
        skills=None,
        self_dev=None,
        registry=None,
        orchestrator=None,
        collab=None,
        bus=None,
        approval=None,
        llm=None,
        task_queue=None,
        task_executor=None,
        hedge_fund=None,
        escalation=None,
        goal_engine=None,
        state_store=None,
        experiment_lab=None,
        revenue_engine=None,
        ecosystem=None,
        self_writing_code=None,
        strategy_validator=None,
        notification_engine=None,
    ) -> None:
        self._memory = memory
        self._skills = skills
        self._self_dev = self_dev
        self._registry = registry
        self._orchestrator = orchestrator
        self._collab = collab
        self._bus = bus
        self._approval = approval
        self._llm = llm
        self._task_queue = task_queue
        self._task_executor = task_executor
        self._hedge_fund = hedge_fund
        self._escalation = escalation
        self._goal_engine = goal_engine
        self._state_store = state_store
        self._experiment_lab = experiment_lab
        self._revenue_engine = revenue_engine
        self._ecosystem = ecosystem
        self._self_writing_code = self_writing_code
        self._strategy_validator = strategy_validator
        self._notifications = notification_engine
        self._market_data = None  # Set via set_market_data()
        self._planning_engine = None  # Set via set_planning_engine()
        self._experience_memory = None  # Set via set_experience_memory()
        self._polymarket_bot = None  # Set via set_polymarket_bot()
        self._outcome_registry = None  # Set via main.py — closed-loop learning

        self._actions: dict[str, ProactiveAction] = {}
        self._actions_lock = asyncio.Lock()
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._sandbox_gate = None  # Set via main.py
        self._chain_engine = None  # Set via set_chain_engine()
        # Limit concurrent background actions to avoid starving Ollama for user chat
        self._llm_semaphore = asyncio.Semaphore(1)
        # When user chat is active, background actions wait
        self._chat_active = asyncio.Event()
        self._chat_active.set()  # Not chatting → background can proceed

        self._register_default_actions()

    def set_market_data(self, market_data) -> None:
        """Late-bind MarketDataService for technical analysis in proactive actions."""
        self._market_data = market_data

    def set_planning_engine(self, planning_engine) -> None:
        """Late-bind PlanningEngine for structured experiment/task design."""
        self._planning_engine = planning_engine

    def set_experience_memory(self, exp_mem) -> None:
        """Late-bind experience memory for cross-project correlation."""
        self._experience_memory = exp_mem

    def set_polymarket_bot(self, bot) -> None:
        """Late-bind Polymarket trading bot."""
        self._polymarket_bot = bot

    def chat_started(self) -> None:
        """Signal that user chat is active — background actions should wait."""
        self._chat_active.clear()

    def chat_finished(self) -> None:
        """Signal that user chat is done — background actions can resume."""
        self._chat_active.set()

    def set_chain_engine(self, chain_engine) -> None:
        """Attach an ActionChainEngine for reactive chaining."""
        self._chain_engine = chain_engine

    def _register_default_actions(self) -> None:
        """Register ROOT's built-in proactive behaviors."""
        defaults = [
            ProactiveAction(
                name="health_monitor",
                description="Check all agent and service health, alert on issues",
                interval_seconds=PROACTIVE_INTERVALS.get("health_monitor", 300),
                handler=lambda: check_health(
                    registry=self._registry, bus=self._bus,
                ),
                risk_level="low",
            ),
            ProactiveAction(
                name="knowledge_consolidation",
                description="Prune weak memories, strengthen used ones, find patterns",
                interval_seconds=PROACTIVE_INTERVALS.get("knowledge_consolidation", 7200),
                handler=lambda: consolidate_knowledge(memory=self._memory),
                risk_level="low",
            ),
            ProactiveAction(
                name="goal_tracker",
                description="Review progress toward Yohan's goals and flag blockers",
                interval_seconds=PROACTIVE_INTERVALS.get("goal_tracker", 3600),
                handler=lambda: track_goals(
                    memory=self._memory, llm=self._llm,
                ),
                risk_level="low",
            ),
            ProactiveAction(
                name="opportunity_scanner",
                description="Look for opportunities aligned with Yohan's interests",
                interval_seconds=PROACTIVE_INTERVALS.get("opportunity_scanner", 14400),
                handler=lambda: scan_opportunities(
                    collab=self._collab, llm=self._llm,
                ),
                risk_level="medium",
            ),
            ProactiveAction(
                name="agent_evolution",
                description="Assess agent performance and propose improvements",
                interval_seconds=PROACTIVE_INTERVALS.get("agent_evolution", 7200),
                handler=lambda: evolve_agents(self_dev=self._self_dev),
                risk_level="low",
            ),
            ProactiveAction(
                name="skill_discovery",
                description="Create new skills from successful patterns",
                interval_seconds=PROACTIVE_INTERVALS.get("skill_discovery", 3600),
                handler=lambda: discover_skills(
                    self_dev=self._self_dev, memory=self._memory,
                ),
                risk_level="medium",
            ),
            # ── Market Intelligence (Trading Swarm) ──
            ProactiveAction(
                name="market_scanner",
                description="Scan markets via Trading Swarm + technical analysis + hedge fund intelligence",
                interval_seconds=PROACTIVE_INTERVALS.get("market_scanner", 1800),
                handler=lambda: scan_markets(
                    collab=self._collab, llm=self._llm, memory=self._memory,
                    hedge_fund=self._hedge_fund, market_data=self._market_data,
                ),
                risk_level="low",
            ),
            # ── GitHub & Open Source Intelligence ──
            ProactiveAction(
                name="github_scanner",
                description="Scan GitHub for trending repos, AI breakthroughs, useful tools",
                interval_seconds=PROACTIVE_INTERVALS.get("github_scanner", 14400),
                handler=lambda: scan_github(
                    collab=self._collab, llm=self._llm, memory=self._memory,
                ),
                risk_level="low",
            ),
            # ── Self-Rewrite (ROOT enhances itself) ──
            ProactiveAction(
                name="self_rewrite",
                description="ROOT analyzes its own code and proposes enhancements via Coder agent",
                interval_seconds=PROACTIVE_INTERVALS.get("self_rewrite", 21600),
                handler=lambda: self_rewrite(
                    collab=self._collab, llm=self._llm, self_dev=self._self_dev,
                ),
                risk_level="medium",
            ),
            # ── MiRo Prediction (future decision projection) ──
            ProactiveAction(
                name="miro_prediction",
                description="Use MiRo swarm intelligence to project future decisions and patterns",
                interval_seconds=PROACTIVE_INTERVALS.get("miro_prediction", 7200),
                handler=lambda: miro_predict(
                    collab=self._collab, llm=self._llm, memory=self._memory,
                    notification_engine=self._notifications,
                ),
                risk_level="low",
            ),
            # ── OpenClaw Data Intelligence ──
            ProactiveAction(
                name="data_intelligence",
                description="Run OpenClaw gap analysis and discovery for new public data sources",
                interval_seconds=PROACTIVE_INTERVALS.get("data_intelligence", 14400),
                handler=lambda: data_intelligence(collab=self._collab),
                risk_level="medium",
            ),
            # ── Task Queue Drainer (bridges persistent queue → executor) ──
            ProactiveAction(
                name="task_queue_drainer",
                description="Process pending tasks from persistent queue through task executor",
                interval_seconds=PROACTIVE_INTERVALS.get("task_queue_drainer", 120),
                handler=lambda: drain_task_queue(
                    task_queue=self._task_queue, task_executor=self._task_executor,
                ),
                risk_level="low",
            ),
            # ── Autonomous Trading Cycle ──
            ProactiveAction(
                name="auto_trade_cycle",
                description="Run hedge fund scan→analyze→trade cycle with escalation approval",
                interval_seconds=PROACTIVE_INTERVALS.get("auto_trade_cycle", 3600),
                handler=lambda: auto_trade_cycle(
                    hedge_fund=self._hedge_fund, escalation=self._escalation,
                ),
                risk_level="critical",
            ),
            # ── Goal Assessment (stalled goal detection) ──
            ProactiveAction(
                name="goal_assessment",
                description="Assess active goals, detect stalled progress, propose fixes",
                interval_seconds=PROACTIVE_INTERVALS.get("goal_assessment", 3600),
                handler=lambda: assess_goals(goal_engine=self._goal_engine),
                risk_level="low",
            ),
            # ── Survival Economics (revenue awareness) ──
            ProactiveAction(
                name="survival_economics",
                description="Assess economic health, scan for revenue opportunities, ensure system sustainability",
                interval_seconds=PROACTIVE_INTERVALS.get("survival_economics", 7200),
                handler=lambda: survival_economics(
                    hedge_fund=self._hedge_fund, goal_engine=self._goal_engine,
                    task_queue=self._task_queue, memory=self._memory,
                ),
                risk_level="low",
            ),
            # ── MiRo Continuous Potentiality (constant assessment) ──
            ProactiveAction(
                name="miro_continuous",
                description="MiRo continuously assesses market potentiality and shares insights to agent network",
                interval_seconds=PROACTIVE_INTERVALS.get("miro_continuous", 3600),
                handler=lambda: miro_continuous_assess(
                    collab=self._collab, memory=self._memory,
                    notification_engine=self._notifications,
                ),
                risk_level="low",
            ),
            # ── MiRo World Intelligence (6-domain autonomous analysis) ──
            ProactiveAction(
                name="miro_world_intelligence",
                description="MiRo scans world domains (markets, geopolitics, AI, crypto, weather, macro) on rotation",
                interval_seconds=PROACTIVE_INTERVALS.get("miro_world_intelligence", 14400),
                handler=lambda: miro_world_intelligence(
                    collab=self._collab, memory=self._memory,
                    notification_engine=self._notifications,
                    run_count=self._actions.get("miro_world_intelligence", ProactiveAction(
                        name="_", description="_", interval_seconds=0, handler=lambda: None,
                    )).run_count,
                ),
                risk_level="low",
            ),
            # ── MiRo Daily Briefing (comprehensive daily push) ──
            ProactiveAction(
                name="miro_daily_briefing",
                description="MiRo synthesizes a comprehensive daily briefing across all world domains",
                interval_seconds=PROACTIVE_INTERVALS.get("miro_daily_briefing", 86400),
                handler=lambda: miro_daily_briefing(
                    collab=self._collab, llm=self._llm, memory=self._memory,
                    notification_engine=self._notifications,
                ),
                risk_level="low",
            ),
            # ── Business Discovery (opportunity scanning) ──
            ProactiveAction(
                name="business_discovery",
                description="Scan for micro-SaaS, automation, and product opportunities using researcher + analyst",
                interval_seconds=PROACTIVE_INTERVALS.get("business_discovery", 14400),
                handler=lambda: business_discovery(
                    collab=self._collab, memory=self._memory,
                ),
                risk_level="low",
            ),
            # ── Experiment Auto-Proposer (generates testable hypotheses) ──
            ProactiveAction(
                name="experiment_proposer",
                description="Auto-propose experiments from market scans, business discoveries, and agent insights (planning-enhanced)",
                interval_seconds=PROACTIVE_INTERVALS.get("experiment_proposer", 7200),
                handler=lambda: experiment_proposer(
                    experiment_lab=self._experiment_lab,
                    collab=self._collab, llm=self._llm,
                    memory=self._memory,
                    planning_engine=self._planning_engine,
                ),
                risk_level="low",
            ),
            # ── Revenue Seeder (ensures products exist from real projects) ──
            ProactiveAction(
                name="revenue_seeder",
                description="Seed revenue engine with real products from Yohan's project ecosystem",
                interval_seconds=PROACTIVE_INTERVALS.get("revenue_seeder", 86400),
                handler=lambda: seed_revenue_products(
                    revenue_engine=self._revenue_engine,
                    ecosystem=self._ecosystem,
                ),
                risk_level="low",
            ),
            # ── Project Ecosystem Scanner (cross-project awareness) ──
            ProactiveAction(
                name="ecosystem_scanner",
                description="Scan project ecosystem and store cross-project awareness into memory",
                interval_seconds=PROACTIVE_INTERVALS.get("ecosystem_scanner", 3600),
                handler=lambda: scan_project_ecosystem(
                    ecosystem=self._ecosystem, memory=self._memory,
                ),
                risk_level="low",
            ),
            # ── Autonomous Experiment Runner (start → evaluate → learn) ──
            ProactiveAction(
                name="experiment_runner",
                description="Start proposed experiments, evaluate running ones, scale successes",
                interval_seconds=PROACTIVE_INTERVALS.get("experiment_runner", 3600),
                handler=lambda: run_experiments(
                    experiment_lab=self._experiment_lab,
                    llm=self._llm, memory=self._memory,
                    collab=self._collab,
                ),
                risk_level="medium",
            ),
            # ── Self-Writing Code Scanner ──
            ProactiveAction(
                name="code_scanner",
                description="Scan for code inefficiencies and propose self-improvement changes",
                interval_seconds=PROACTIVE_INTERVALS.get("code_scanner", 7200),
                handler=lambda: scan_code_improvements(
                    self_writing_code=self._self_writing_code,
                    llm=self._llm, memory=self._memory,
                ),
                risk_level="low",
            ),
            # ── Revenue Health Tracker ──
            ProactiveAction(
                name="revenue_tracker",
                description="Monitor project revenue health, flag risks, identify growth",
                interval_seconds=PROACTIVE_INTERVALS.get("revenue_tracker", 3600),
                handler=lambda: track_revenue_health(
                    revenue_engine=self._revenue_engine,
                    ecosystem=self._ecosystem, memory=self._memory,
                ),
                risk_level="low",
            ),
            # ── Cross-Project Correlation (find synergies) ──
            ProactiveAction(
                name="project_correlator",
                description="Correlate across projects to find synergies and untapped opportunities",
                interval_seconds=PROACTIVE_INTERVALS.get("project_correlator", 14400),
                handler=lambda: correlate_projects(
                    ecosystem=self._ecosystem, llm=self._llm,
                    memory=self._memory,
                    experience_memory=self._experience_memory,
                ),
                risk_level="low",
            ),
            # ── Actuator: Approval Timeout Escalation ──
            ProactiveAction(
                name="approval_timeout",
                description="Expire stale approvals — HIGH auto-approved after 60min, CRITICAL expired",
                interval_seconds=PROACTIVE_INTERVALS.get("approval_timeout", 300),
                handler=lambda: check_approval_timeouts(
                    approval_chain=self._approval,
                ),
                risk_level="low",
            ),
            # ── Actuator: Stalled Goal Auto-Recovery ──
            ProactiveAction(
                name="goal_auto_recovery",
                description="Auto-recover stalled goals by decomposing into tasks (7d/14d/30d tiers)",
                interval_seconds=PROACTIVE_INTERVALS.get("goal_auto_recovery", 3600),
                handler=lambda: auto_recover_goals(
                    goal_engine=self._goal_engine,
                ),
                risk_level="medium",
            ),
            # ── Actuator: Revenue Emergency Remediation ──
            ProactiveAction(
                name="revenue_remediation",
                description="Auto-pause unprofitable products, flag top earners and near-profitable for optimization",
                interval_seconds=PROACTIVE_INTERVALS.get("revenue_remediation", 3600),
                handler=lambda: auto_remediate_revenue(
                    revenue_engine=self._revenue_engine,
                ),
                risk_level="medium",
            ),
            # ── Strategy Validator (autonomous backtest → promote pipeline) ──
            ProactiveAction(
                name="strategy_validator",
                description="Autonomously discover, backtest, and rank trading strategies — promote winners to live",
                interval_seconds=PROACTIVE_INTERVALS.get("strategy_validator", 14400),
                handler=lambda: validate_strategies(
                    strategy_validator=self._strategy_validator,
                ),
                risk_level="medium",
            ),
            # ── Deploy Promoted Strategies (validator → hedge fund bridge) ──
            ProactiveAction(
                name="deploy_promoted",
                description="Convert promoted strategies into live trading signals for hedge fund execution",
                interval_seconds=PROACTIVE_INTERVALS.get("deploy_promoted", 3600),
                handler=lambda: deploy_promoted_strategies(
                    strategy_validator=self._strategy_validator,
                    hedge_fund=self._hedge_fund,
                    escalation=self._escalation,
                    notification_engine=self._notifications,
                ),
                risk_level="critical",
            ),
            # ── Scalp Trade Cycle (fast leveraged ETF scalping) ──
            ProactiveAction(
                name="scalp_trade_cycle",
                description="Fast 90s scalp cycle on leveraged ETFs (TQQQ, SQQQ, SOXL, SOXS) using EMA/RSI strategies",
                interval_seconds=PROACTIVE_INTERVALS.get("scalp_trade_cycle", 90),
                handler=lambda: scalp_trade_cycle(
                    hedge_fund=self._hedge_fund,
                    escalation=self._escalation,
                    notification_engine=self._notifications,
                ),
                risk_level="critical",
            ),
            # ── Polymarket: Market Scanner ──
            ProactiveAction(
                name="polymarket_scanner",
                description="Scan Polymarket prediction markets and store price snapshots",
                interval_seconds=PROACTIVE_INTERVALS.get("polymarket_scanner", 600),
                handler=lambda: scan_polymarkets(
                    polymarket_bot=self._polymarket_bot,
                ),
                risk_level="low",
            ),
            # ── Polymarket: Trading Cycle ──
            ProactiveAction(
                name="polymarket_trade_cycle",
                description="Run Polymarket scalping + edge hunting trading cycle",
                interval_seconds=PROACTIVE_INTERVALS.get("polymarket_trade_cycle", 1800),
                handler=lambda: polymarket_trade_cycle(
                    polymarket_bot=self._polymarket_bot,
                    escalation=self._escalation,
                ),
                risk_level="critical",
            ),
            # ── Polymarket: Position Monitor ──
            ProactiveAction(
                name="polymarket_monitor",
                description="Check open Polymarket positions for profit targets and stop losses",
                interval_seconds=PROACTIVE_INTERVALS.get("polymarket_monitor", 300),
                handler=lambda: monitor_polymarket_positions(
                    polymarket_bot=self._polymarket_bot,
                ),
                risk_level="low",
            ),
        ]

        for action in defaults:
            self._actions[action.name] = action

    async def start(self) -> None:
        """Start all proactive behavior loops."""
        async with self._actions_lock:
            if self._running:
                return
            self._running = True
            if self._state_store:
                saved = self._state_store.load_proactive_state()
                for name, state in saved.items():
                    action = self._actions.get(name)
                    if action:
                        action.run_count = state["run_count"]
                        action.error_count = state["error_count"]
                        action.last_run = state["last_run"]
                        action.last_result = state["last_result"]
                if saved:
                    logger.info("Proactive engine: restored state for %d actions", len(saved))

            logger.info("Proactive engine starting with %d behaviors", len(self._actions))

            actions_snapshot = list(self._actions.values())

        for action in actions_snapshot:
            if action.enabled:
                task = asyncio.create_task(self._run_loop(action))
                self._tasks.append(task)

    def stop(self) -> None:
        """Stop all proactive loops."""
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("Proactive engine stopped")

    async def trigger(self, action_name: str) -> Optional[str]:
        """Manually trigger a proactive action."""
        async with self._actions_lock:
            action = self._actions.get(action_name)
        if not action:
            return None
        return await self._execute_action(action)

    async def get_actions(self) -> list[dict[str, Any]]:
        """List all proactive actions with their status."""
        async with self._actions_lock:
            actions_snapshot = list(self._actions.values())
        return [
            {
                "name": a.name,
                "description": a.description,
                "enabled": a.enabled,
                "interval_seconds": a.interval_seconds,
                "risk_level": a.risk_level,
                "last_run": a.last_run,
                "run_count": a.run_count,
                "error_count": a.error_count,
                "last_result": (a.last_result or "")[:200],
            }
            for a in actions_snapshot
        ]

    async def enable(self, action_name: str) -> bool:
        async with self._actions_lock:
            action = self._actions.get(action_name)
            if not action:
                return False
            self._actions[action_name] = ProactiveAction(
                name=action.name,
                description=action.description,
                interval_seconds=action.interval_seconds,
                handler=action.handler,
                enabled=True,
                risk_level=action.risk_level,
            )
            return True

    async def disable(self, action_name: str) -> bool:
        async with self._actions_lock:
            action = self._actions.get(action_name)
            if not action:
                return False
            self._actions[action_name] = ProactiveAction(
                name=action.name,
                description=action.description,
                interval_seconds=action.interval_seconds,
                handler=action.handler,
                enabled=False,
                risk_level=action.risk_level,
            )
            return True

    async def stats(self) -> dict[str, Any]:
        async with self._actions_lock:
            actions_snapshot = list(self._actions.values())
        total_runs = sum(a.run_count for a in actions_snapshot)
        total_errors = sum(a.error_count for a in actions_snapshot)
        return {
            "running": self._running,
            "total_actions": len(actions_snapshot),
            "enabled": sum(1 for a in actions_snapshot if a.enabled),
            "total_runs": total_runs,
            "total_errors": total_errors,
            "success_rate": (total_runs - total_errors) / max(total_runs, 1),
        }

    # ── Loop runner ───────────────────────────────────────────────

    async def _run_loop(self, action: ProactiveAction) -> None:
        """Run a proactive action on its interval."""
        action_name = action.name
        # Stagger start over 5 minutes to avoid thundering herd on Ollama
        await asyncio.sleep(abs(hash(action_name)) % 300 + 30)

        while self._running:
            # Re-fetch the current action object under the lock (enable/disable replaces it)
            async with self._actions_lock:
                current_action = self._actions.get(action_name)
            if current_action is None:
                break
            if not current_action.enabled:
                break
            # Wait if user chat is in progress — user gets LLM priority
            await self._chat_active.wait()
            try:
                # Acquire semaphore so only 1 background action uses LLM at a time
                async with self._llm_semaphore:
                    await self._execute_action(current_action)
            except Exception as exc:
                current_action.error_count += 1
                logger.error("Proactive action '%s' failed: %s", action_name, exc)
            await asyncio.sleep(current_action.interval_seconds)

    # Actions that are purely internal — always run, never gated
    _INTERNAL_ACTIONS: frozenset[str] = frozenset({
        "health_monitor", "knowledge_consolidation", "goal_tracker",
        "agent_evolution", "skill_discovery", "goal_assessment",
        "task_queue_drainer", "miro_prediction", "miro_continuous",
        "miro_world_intelligence", "miro_daily_briefing",
        "business_discovery", "experiment_proposer", "revenue_seeder",
        "ecosystem_scanner", "experiment_runner", "code_scanner",
        "revenue_tracker", "project_correlator", "approval_timeout",
        "goal_auto_recovery", "revenue_remediation", "strategy_validator",
        "polymarket_monitor", "survival_economics", "polymarket_scanner",
    })

    async def _execute_action(self, action: ProactiveAction) -> str:
        """Execute a single proactive action, routing through approval chain."""
        # ── Sandbox gate check for external actions ─────────────
        if (
            self._sandbox_gate is not None
            and action.name not in self._INTERNAL_ACTIONS
        ):
            decision = self._sandbox_gate.check(
                system_id="proactive",
                action=f"proactive:{action.name}",
                description=action.description,
                agent_id="proactive_engine",
                risk_level=action.risk_level,
            )
            if not decision.was_executed:
                logger.info("Proactive '%s' sandboxed — skipping execution", action.name)
                return f"sandboxed: {action.description}"

        # Route medium+ risk actions through approval chain
        if self._approval and action.risk_level != "low":
            approval_result = await self._approval.request_approval(
                agent_id="proactive_engine",
                action=action.name,
                description=f"Proactive: {action.description}",
            )
            if hasattr(approval_result, 'status') and approval_result.status == ApprovalStatus.REJECTED:
                logger.info("Proactive '%s' rejected by approval chain", action.name)
                return "rejected by approval chain"

        logger.info("Proactive: running '%s'", action.name)
        try:
            result = await action.handler()
            action.run_count += 1
            action.last_run = datetime.now(timezone.utc).isoformat()
            action.last_result = str(result)[:500] if result else "completed"

            # Publish to bus
            if self._bus and result:
                msg = self._bus.create_message(
                    topic="system.proactive",
                    sender="proactive_engine",
                    payload={
                        "action": action.name,
                        "result": str(result)[:1000],
                    },
                )
                await self._bus.publish(msg)

            # Persist state to SQLite
            if self._state_store:
                self._state_store.save_proactive_state(
                    action.name, action.run_count, action.error_count,
                    action.last_run, action.last_result,
                )

            # Record experience from proactive action for long-term learning
            if self._experience_memory and result:
                try:
                    self._experience_memory.record_experience(
                        experience_type="success",
                        domain=f"proactive:{action.name}",
                        title=f"Proactive action: {action.name}",
                        description=str(result)[:300],
                        context={"action": action.name, "run_count": action.run_count},
                    )
                except Exception as exp_exc:
                    logger.warning("Experience recording failed for '%s': %s", action.name, exp_exc)

            # Record outcome for closed-loop learning
            if hasattr(self, '_outcome_registry') and self._outcome_registry and result:
                try:
                    self._outcome_registry.record(
                        action_type="proactive",
                        action_id=action.name,
                        intent=action.description,
                        result=str(result)[:500],
                        quality_score=0.8 if result and len(str(result)) > 100 else 0.5,
                        context={"action": action.name, "run_count": action.run_count},
                    )
                except Exception:
                    pass

            # Evaluate action chains (reactive follow-ups)
            if self._chain_engine:
                try:
                    chain_result = {"result": action.last_result}
                    await self._chain_engine.evaluate_trigger(
                        action.name, chain_result,
                    )
                except Exception as chain_exc:
                    logger.warning(
                        "Chain evaluation failed for '%s': %s",
                        action.name, chain_exc,
                    )

            return action.last_result
        except Exception as exc:
            action.error_count += 1
            # Record failed outcome for closed-loop learning
            if hasattr(self, '_outcome_registry') and self._outcome_registry:
                try:
                    self._outcome_registry.record(
                        action_type="proactive",
                        action_id=action.name,
                        intent=action.description,
                        result=str(exc)[:500],
                        quality_score=0.1,
                        context={"action": action.name, "error_count": action.error_count},
                    )
                except Exception:
                    pass
            if self._state_store:
                self._state_store.save_proactive_state(
                    action.name, action.run_count, action.error_count,
                    action.last_run, action.last_result,
                )
            raise
