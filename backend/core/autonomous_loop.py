"""
Autonomous Loop — self-improving intelligence cycle.

From autoresearch-master pattern + HERMES learning loop:
ROOT continuously improves itself through autonomous experimentation.

The loop:
1. ASSESS   — What are ROOT's current gaps and weaknesses?
2. PROPOSE  — What experiments could close those gaps?
3. EXECUTE  — Run the experiment (bounded, safe)
4. EVALUATE — Did it improve things? (metrics-based)
5. KEEP/DISCARD — Apply improvements or roll back
6. LEARN    — Store what worked for future reference

Runs as a background task, respecting approval chain for risky changes.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.autonomous")


@dataclass(frozen=True)
class Experiment:
    """Immutable experiment definition and results."""
    id: str
    area: str  # "knowledge", "skills", "agents", "memory", "tools", "trading", "strategy"
    hypothesis: str
    approach: str
    status: str = "proposed"  # proposed → running → completed → kept/discarded
    baseline_metric: Optional[float] = None
    result_metric: Optional[float] = None
    outcome: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None


class AutonomousLoop:
    """Self-improving loop that runs in the background.

    Uses collaboration to delegate experiments to specialist agents
    and the approval chain for risky changes.
    """

    MAX_EXPERIMENTS_PER_CYCLE = 3
    CYCLE_INTERVAL = 1800  # 30 minutes

    def __init__(
        self,
        memory=None,
        skills=None,
        self_dev=None,
        collab=None,
        bus=None,
        approval=None,
        llm=None,
        learning=None,
        goal_engine=None,
        task_queue=None,
        state_store=None,
        ecosystem=None,
        prediction_ledger=None,
        experience_memory=None,
    ) -> None:
        self._memory = memory
        self._skills = skills
        self._self_dev = self_dev
        self._collab = collab
        self._bus = bus
        self._approval = approval
        self._llm = llm
        self._learning = learning  # LearningEngine for outcome tracking
        self._goal_engine = goal_engine
        self._task_queue = task_queue
        self._state_store = state_store
        self._ecosystem = ecosystem
        self._prediction_ledger = prediction_ledger
        self._experience_memory = experience_memory

        self._experiments: list[Experiment] = []
        self._cycle_count = 0
        self._running = False
        self._failure_count: int = 0
        self._task: Optional[asyncio.Task] = None

    async def start(self, interval: Optional[int] = None) -> None:
        """Start the autonomous improvement loop."""
        if self._running:
            return
        self._running = True

        # Restore state from previous runs
        if self._state_store:
            self._cycle_count = int(self._state_store.get_meta("autonomous_cycle_count", "0"))
            saved_exps = self._state_store.load_experiments(limit=50)
            for exp_data in saved_exps:
                exp = Experiment(
                    id=exp_data.get("id", ""),
                    area=exp_data.get("area", "unknown"),
                    hypothesis=exp_data.get("hypothesis", ""),
                    approach=exp_data.get("baseline", "restored"),
                    status=exp_data.get("status", "proposed"),
                    outcome=exp_data.get("result"),
                    created_at=exp_data.get("created_at", ""),
                    completed_at=exp_data.get("completed_at"),
                )
                self._experiments.append(exp)
            if saved_exps:
                logger.info("Autonomous loop: restored %d experiments, cycle=%d",
                            len(saved_exps), self._cycle_count)

        actual_interval = interval or self.CYCLE_INTERVAL
        self._task = asyncio.create_task(self._loop(actual_interval))
        logger.info("Autonomous loop started (interval=%ds)", actual_interval)

    def stop(self) -> None:
        """Stop the loop."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Autonomous loop stopped")

    async def run_cycle(self) -> dict[str, Any]:
        """Run a single improvement cycle."""
        self._cycle_count += 1
        cycle_id = f"cycle_{self._cycle_count}"
        logger.info("Autonomous cycle %s starting", cycle_id)

        results: dict[str, Any] = {
            "cycle": self._cycle_count,
            "experiments_proposed": 0,
            "experiments_run": 0,
            "kept": 0,
            "discarded": 0,
        }

        # Step 1: ASSESS current state
        assessment = await self._assess()

        # Step 2: PROPOSE experiments based on gaps
        experiments = await self._propose(assessment)
        results["experiments_proposed"] = len(experiments)

        # Step 3-5: EXECUTE, EVALUATE, KEEP/DISCARD
        for exp in experiments[:self.MAX_EXPERIMENTS_PER_CYCLE]:
            outcome = await self._run_experiment(exp)
            results["experiments_run"] += 1

            if outcome and outcome.status == "kept":
                results["kept"] += 1
            else:
                results["discarded"] += 1

        # Step 6: LEARN from this cycle
        await self._learn(results)

        # Notify via bus
        if self._bus:
            msg = self._bus.create_message(
                topic="system.learning",
                sender="autonomous_loop",
                payload={
                    "type": "cycle_complete",
                    "cycle": self._cycle_count,
                    "results": results,
                },
            )
            await self._bus.publish(msg)

        # Persist cycle count
        if self._state_store:
            self._state_store.set_meta("autonomous_cycle_count", str(self._cycle_count))

        logger.info(
            "Autonomous cycle %s complete: %d proposed, %d run, %d kept",
            cycle_id, results["experiments_proposed"],
            results["experiments_run"], results["kept"],
        )
        return results

    # ── Core cycle steps ──────────────────────────────────────────

    async def _assess(self) -> dict[str, Any]:
        """Assess ROOT's current state and identify improvement areas."""
        assessment: dict[str, Any] = {}

        if self._self_dev:
            dev_assessment = self._self_dev.assess()
            assessment["maturity"] = dev_assessment.get("maturity_level")
            assessment["maturity_score"] = dev_assessment.get("maturity_score")
            assessment["gaps"] = dev_assessment.get("capability_gaps", [])
            assessment["evolution_count"] = dev_assessment.get("evolution_count", 0)

        if self._memory:
            mem_count = self._memory.count()
            assessment["memory_count"] = mem_count

        if self._skills:
            skill_info = self._skills.list_all()
            assessment["skill_count"] = len(skill_info)

        # Assess active goals
        if self._goal_engine:
            goal_stats = self._goal_engine.stats()
            assessment["active_goals"] = goal_stats.get("by_status", {}).get("active", 0)
            assessment["avg_goal_progress"] = goal_stats.get("avg_active_progress", 0)

            # Detect stalled goals
            goal_assessment = await self._goal_engine.assess_all_goals()
            stalled = [u for u in goal_assessment.get("updates", []) if u.get("status") == "stalled"]
            assessment["stalled_goals"] = stalled

        # Check task queue backlog
        if self._task_queue:
            queue_stats = self._task_queue.stats()
            assessment["pending_tasks"] = queue_stats.get("by_status", {}).get("pending", 0)

        # Ecosystem health — cross-project awareness
        if self._ecosystem:
            try:
                eco_summary = self._ecosystem.get_ecosystem_summary()
                assessment["ecosystem_projects"] = eco_summary.get("total_projects", 0)
                assessment["ecosystem_revenue_streams"] = list(
                    eco_summary.get("by_revenue_stream", {}).keys()
                )
                assessment["active_ports"] = eco_summary.get("active_ports", {})
            except Exception as exc:
                logger.warning("Failed to fetch ecosystem summary: %s", exc)

        # Prediction accuracy — calibration feedback
        if self._prediction_ledger:
            try:
                pred_stats = self._prediction_ledger.stats()
                assessment["prediction_accuracy"] = pred_stats.get("hit_rate", 0)
                assessment["predictions_pending"] = pred_stats.get("pending", 0)
                assessment["predictions_total"] = pred_stats.get("total", 0)
            except Exception as exc:
                logger.warning("Failed to fetch prediction stats: %s", exc)

        # Experience wisdom — what have we learned from past experiments
        if self._experience_memory:
            try:
                exp_stats = self._experience_memory.stats()
                if isinstance(exp_stats, list):
                    assessment["experience_count"] = sum(
                        row.get("cnt", 0) if isinstance(row, dict) else 0
                        for row in exp_stats
                    )
                    assessment["experience_types"] = {
                        row.get("experience_type", "unknown"): row.get("cnt", 0)
                        for row in exp_stats
                        if isinstance(row, dict)
                    }
            except Exception as exc:
                logger.warning("Failed to fetch experience memory stats: %s", exc)

        return assessment

    async def _propose_dynamic(self, assessment: dict) -> list[Experiment]:
        """Use LLM to propose experiments based on current system state."""
        prompt = (
            "Based on ROOT's current state, propose 2-3 experiments that would "
            "improve the system. For each: area (knowledge/skills/memory/agents/"
            "goals/trading/strategy), hypothesis, approach. Return JSON array.\n\n"
            f"System assessment:\n{json.dumps(assessment, default=str)[:2000]}"
        )
        try:
            response = await self._llm.complete(
                system="You are ROOT's self-improvement engine. Return only a JSON array.",
                messages=[{"role": "user", "content": prompt}],
                model_tier="default",
                max_tokens=800,
                method="proactive",
            )
            raw = response.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            try:
                items = json.loads(raw)
            except (json.JSONDecodeError, ValueError) as parse_err:
                logger.warning("LLM proposal JSON parse failed: %s. Response: %s", parse_err, raw[:200])
                return []
            if isinstance(items, dict):
                items = items.get("experiments", items.get("directives", []))
            valid_areas = {"knowledge", "skills", "memory", "agents", "goals", "trading", "strategy"}
            experiments: list[Experiment] = []
            for item in items[:3]:
                area = str(item.get("area", "knowledge"))
                if area not in valid_areas:
                    area = "knowledge"
                experiments.append(Experiment(
                    id=f"exp_{uuid.uuid4().hex[:8]}",
                    area=area,
                    hypothesis=str(item.get("hypothesis", ""))[:300],
                    approach=str(item.get("approach", ""))[:300],
                ))
            if experiments:
                logger.info("LLM proposed %d dynamic experiments", len(experiments))
                return experiments
        except Exception as exc:
            logger.warning("Dynamic proposal failed, falling back to templates: %s", exc)
        return []

    async def _propose(self, assessment: dict) -> list[Experiment]:
        """Propose experiments to close identified gaps, weighted by past success."""
        # Try LLM-based dynamic proposals first
        if self._llm:
            dynamic = await self._propose_dynamic(assessment)
            if dynamic:
                return dynamic

        experiments: list[Experiment] = []
        gaps = assessment.get("gaps", [])

        # Candidate experiments with their areas
        candidates: list[tuple[Experiment, float]] = []

        # Knowledge expansion
        candidates.append((
            Experiment(
                id=f"exp_{uuid.uuid4().hex[:8]}",
                area="knowledge",
                hypothesis="Expanding knowledge base improves task routing accuracy",
                approach="Use researcher to find new patterns and store learnings",
            ),
            self._get_area_weight("knowledge"),
        ))

        # Gap-based experiments
        for gap in gaps[:3]:
            candidates.append((
                Experiment(
                    id=f"exp_{uuid.uuid4().hex[:8]}",
                    area="skills",
                    hypothesis=f"Creating a skill for '{gap}' closes the capability gap",
                    approach=f"Analyze existing patterns and create a reusable skill for {gap}",
                ),
                self._get_area_weight("skills"),
            ))

        # Memory optimization
        if assessment.get("memory_count", 0) > 200:
            candidates.append((
                Experiment(
                    id=f"exp_{uuid.uuid4().hex[:8]}",
                    area="memory",
                    hypothesis="Pruning low-confidence memories improves recall quality",
                    approach="Identify memories below 0.3 confidence and evaluate for removal",
                ),
                self._get_area_weight("memory"),
            ))

        # Agent performance optimization (new: learn from routing data)
        if self._learning:
            insights = self._learning.get_insights()
            if insights.get("misrouted_count", 0) > 3:
                candidates.append((
                    Experiment(
                        id=f"exp_{uuid.uuid4().hex[:8]}",
                        area="agents",
                        hypothesis="Improving agent routing reduces misrouted interactions",
                        approach="Analyze routing failures and adjust agent descriptions",
                    ),
                    self._get_area_weight("agents"),
                ))

        # Stalled goal recovery
        stalled = assessment.get("stalled_goals", [])
        for stall in stalled[:2]:
            candidates.append((
                Experiment(
                    id=f"exp_{uuid.uuid4().hex[:8]}",
                    area="goals",
                    hypothesis=f"Decomposing stalled goal '{stall.get('title', '')[:80]}' into tasks will unblock it",
                    approach=f"Auto-decompose goal {stall.get('goal_id')} into actionable tasks",
                ),
                self._get_area_weight("goals"),
            ))

        # Sort by learned weight (higher = historically more successful)
        candidates.sort(key=lambda c: c[1], reverse=True)
        experiments = [exp for exp, _weight in candidates]

        return experiments

    def _auto_apply_experiment_result(self, area: str, outcome_text: str) -> None:
        """Auto-apply successful experiment results to routing weights."""
        area_to_agents = {
            "knowledge": [("researcher", "knowledge")],
            "skills": [("builder", "skills"), ("coder", "skills")],
            "memory": [("researcher", "memory")],
            "agents": [("analyst", "agents")],
            "goals": [("analyst", "goals"), ("researcher", "goals")],
            "trading": [("swarm", "trading"), ("analyst", "trading")],
            "strategy": [("analyst", "strategy"), ("miro", "strategy")],
        }
        pairs = area_to_agents.get(area, [])
        for agent_id, category in pairs:
            try:
                new_weight = self._learning.boost_routing_weight(
                    agent_id, category, amount=0.03,
                )
                logger.info(
                    "Auto-applied experiment win: boosted %s/%s → %.3f",
                    agent_id, category, new_weight,
                )
            except Exception as exc:
                logger.warning("Failed to boost %s: %s", agent_id, exc)

    def _get_area_weight(self, area: str) -> float:
        """Get learned success weight for an experiment area."""
        if self._learning:
            return self._learning.get_experiment_weight(area)
        return 0.5  # neutral default

    async def _run_experiment(self, exp: Experiment) -> Optional[Experiment]:
        """Execute a single experiment and record outcome for future learning."""
        running = Experiment(
            id=exp.id,
            area=exp.area,
            hypothesis=exp.hypothesis,
            approach=exp.approach,
            status="running",
            created_at=exp.created_at,
        )
        self._experiments = [*self._experiments, running]
        if len(self._experiments) > 200:
            keep_from = len(self._experiments) - 200
            self._experiments = [self._experiments[i] for i in range(keep_from, len(self._experiments))]

        # Capture maturity before experiment
        maturity_before = 0.0
        if self._self_dev:
            maturity_before = self._self_dev.assess().get("maturity_score", 0.0)

        try:
            if exp.area == "knowledge" and self._collab:
                result = await self._collab.delegate(
                    from_agent="autonomous_loop",
                    to_agent="researcher",
                    task=(
                        f"Research and find one new useful piece of knowledge for ROOT. "
                        f"Focus on: {exp.hypothesis}. "
                        f"Return a concise fact or learning that can be stored."
                    ),
                )
                outcome_text = result.final_result or ""
                success = bool(outcome_text and len(outcome_text) > 20)

            elif exp.area == "skills" and self._self_dev:
                # Let self-dev engine propose the improvement
                self._self_dev.propose_improvement(
                    area="skills",
                    description=exp.approach,
                    rationale=exp.hypothesis,
                )
                success = True
                outcome_text = "Improvement proposed to self-dev engine"

            elif exp.area == "memory" and self._memory:
                # Evaluate low-confidence memories
                from backend.models.memory import MemoryQuery
                low_conf = self._memory.search(MemoryQuery(query="", limit=50, min_confidence=0.0))
                prunable = [m for m in low_conf if m.confidence < 0.3]
                success = True
                outcome_text = f"Found {len(prunable)} low-confidence memories for review"

            elif exp.area == "agents" and self._collab:
                # Analyze agent routing failures and suggest improvements
                result = await self._collab.delegate(
                    from_agent="autonomous_loop",
                    to_agent="analyst",
                    task=(
                        f"Analyze ROOT's agent routing and performance. "
                        f"Hypothesis: {exp.hypothesis}. "
                        f"Identify which agent types handle which tasks best, "
                        f"and suggest routing improvements. Be concise."
                    ),
                )
                outcome_text = result.final_result or ""
                success = bool(outcome_text and len(outcome_text) > 20)

            elif exp.area == "goals" and self._goal_engine:
                # Decompose stalled goals into tasks
                goal_id = exp.approach.split("goal ")[-1].split(" ")[0] if "goal " in exp.approach else ""
                if goal_id:
                    task_ids = await self._goal_engine.decompose_goal(goal_id)
                    success = len(task_ids) > 0
                    outcome_text = f"Decomposed goal {goal_id} into {len(task_ids)} tasks"
                else:
                    success = False
                    outcome_text = "Could not extract goal ID"

            elif exp.area == "trading" and self._collab:
                result = await self._collab.delegate(
                    from_agent="autonomous_loop",
                    to_agent="swarm",
                    task=(
                        "Research and propose one new trading strategy. "
                        "Include backtest criteria and expected Sharpe ratio."
                    ),
                )
                outcome_text = result.final_result or ""
                success = bool(outcome_text and len(outcome_text) > 20)

            elif exp.area == "strategy" and self._collab:
                result = await self._collab.delegate(
                    from_agent="autonomous_loop",
                    to_agent="analyst",
                    task=(
                        "Analyze ROOT's current strategies and propose one optimization. "
                        "Look at routing weights, directive success rates, and prediction accuracy."
                    ),
                )
                outcome_text = result.final_result or ""
                success = bool(outcome_text and len(outcome_text) > 20)

            elif exp.area == "tools" and self._collab:
                # Discover tool usage patterns and suggest new tools
                result = await self._collab.delegate(
                    from_agent="autonomous_loop",
                    to_agent="researcher",
                    task=(
                        f"Research useful tools or APIs that could extend ROOT's capabilities. "
                        f"Focus on: {exp.hypothesis}. "
                        f"List top 3 most useful tools/APIs with what they do and why. Be concise."
                    ),
                )
                outcome_text = result.final_result or ""
                success = bool(outcome_text and len(outcome_text) > 20)

            else:
                success = False
                outcome_text = f"No handler for area '{exp.area}'"

            status = "kept" if success else "discarded"
            completed = Experiment(
                id=exp.id,
                area=exp.area,
                hypothesis=exp.hypothesis,
                approach=exp.approach,
                status=status,
                outcome=outcome_text[:500],
                created_at=exp.created_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )

            # AUTO-APPLY: When experiment succeeds, update routing weights
            if success and self._learning:
                self._auto_apply_experiment_result(exp.area, outcome_text)

            # Store learning
            if success and self._memory and outcome_text:
                from backend.models.memory import MemoryEntry, MemoryType
                entry = MemoryEntry(
                    content=f"Autonomous experiment ({exp.area}): {outcome_text[:300]}",
                    memory_type=MemoryType.LEARNING,
                    tags=["autonomous", exp.area, "experiment"],
                    source="autonomous_loop",
                    confidence=0.7,
                )
                self._memory.store(entry)

            # Record outcome to learning engine for future proposal weighting
            if self._learning:
                maturity_after = 0.0
                if self._self_dev:
                    maturity_after = self._self_dev.assess().get("maturity_score", 0.0)
                try:
                    self._learning.record_experiment_outcome(
                        area=exp.area,
                        hypothesis=exp.hypothesis,
                        success=success,
                        maturity_before=maturity_before,
                        maturity_after=maturity_after,
                    )
                except Exception as le:
                    logger.error("Learning engine record failed: %s", le)

            # Update history
            self._experiments = [
                *(e for e in self._experiments if e.id != exp.id),
                completed,
            ]

            # Persist experiment to state store
            if self._state_store:
                self._state_store.save_experiment(
                    experiment_id=completed.id,
                    area=completed.area,
                    hypothesis=completed.hypothesis,
                    status=completed.status,
                    baseline=completed.approach,
                    result=completed.outcome or "",
                    improvement=maturity_after - maturity_before if success else 0,
                )

            return completed

        except Exception as exc:
            logger.error("Experiment %s failed: %s", exp.id, exc)
            failed = Experiment(
                id=exp.id,
                area=exp.area,
                hypothesis=exp.hypothesis,
                approach=exp.approach,
                status="discarded",
                outcome=f"Error: {exc}",
                created_at=exp.created_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
            )
            self._experiments = [
                *(e for e in self._experiments if e.id != exp.id),
                failed,
            ]
            return failed

    async def _learn(self, cycle_results: dict) -> None:
        """Store learnings from the cycle into memory + experience memory."""
        if not self._memory:
            return

        from backend.models.memory import MemoryEntry, MemoryType

        summary = (
            f"Autonomous cycle #{cycle_results['cycle']}: "
            f"{cycle_results['experiments_run']} experiments run, "
            f"{cycle_results['kept']} kept, "
            f"{cycle_results['discarded']} discarded."
        )

        entry = MemoryEntry(
            content=summary,
            memory_type=MemoryType.LEARNING,
            tags=["autonomous", "cycle", "meta"],
            source="autonomous_loop",
            confidence=0.8,
        )
        self._memory.store(entry)

        # Feed outcomes into experience memory for long-term wisdom
        if self._experience_memory and cycle_results.get("kept", 0) > 0:
            try:
                self._experience_memory.record_experience(
                    experience_type="success",
                    domain="autonomous_loop",
                    title=f"Autonomous cycle #{cycle_results['cycle']}",
                    description=(
                        f"Self-improvement cycle completed: {cycle_results['kept']} experiments "
                        f"produced improvements out of {cycle_results['experiments_run']} run."
                    ),
                    context=cycle_results,
                )
            except Exception as exc:
                logger.debug("Experience memory record failed: %s", exc)

        if self._experience_memory and cycle_results.get("discarded", 0) > 0:
            try:
                self._experience_memory.record_experience(
                    experience_type="failure",
                    domain="autonomous_loop",
                    title=f"Autonomous cycle #{cycle_results['cycle']} failures",
                    description=(
                        f"{cycle_results['discarded']} experiments discarded — "
                        f"approaches didn't improve system metrics."
                    ),
                    context=cycle_results,
                )
            except Exception as exc:
                logger.debug("Experience memory record failed: %s", exc)

    # ── Background loop ───────────────────────────────────────────

    async def _loop(self, interval: int) -> None:
        """Run cycles on interval."""
        await asyncio.sleep(120)  # Initial delay — let other systems start

        while self._running:
            try:
                await self.run_cycle()
                self._failure_count = 0
            except Exception as exc:
                self._failure_count = self._failure_count + 1
                logger.error("Autonomous loop error: %s", exc)
                if self._failure_count >= 5:
                    logger.critical(
                        "Autonomous loop: %d consecutive failures — backing off 300s",
                        self._failure_count,
                    )
                    self._failure_count = 0
                    await asyncio.sleep(300)
                    continue
            await asyncio.sleep(interval)

    # ── Status ────────────────────────────────────────────────────

    def get_experiments(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get recent experiments."""
        recent = self._experiments[-limit:]
        return [
            {
                "id": e.id,
                "area": e.area,
                "hypothesis": e.hypothesis,
                "status": e.status,
                "outcome": e.outcome,
                "created_at": e.created_at,
                "completed_at": e.completed_at,
            }
            for e in reversed(recent)
        ]

    def stats(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "cycles_completed": self._cycle_count,
            "total_experiments": len(self._experiments),
            "kept": sum(1 for e in self._experiments if e.status == "kept"),
            "discarded": sum(1 for e in self._experiments if e.status == "discarded"),
            "by_area": {
                area: sum(1 for e in self._experiments if e.area == area)
                for area in {"knowledge", "skills", "memory", "agents", "tools", "trading", "strategy"}
            },
        }
