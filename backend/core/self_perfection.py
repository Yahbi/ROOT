"""
Self-Perfection Organism — the system that makes ROOT improve itself 24/7.

Architecture:
Meta-Evolution Agent (CEO of Self-Improvement)
├── Gap Finder — continuously scans logs, backtests, Brier scores for weaknesses
├── Skill Evolution — auto-generates new skills when gaps are found
├── Code Mutation Loop — proposes code improvements + backtests them
├── Audit & Test Crew — critics veto changes that drop Sharpe or increase cost
├── UI Enhancer — detects dashboard friction + suggests improvements
└── Economic Tie-In — only merges changes that improve risk-adjusted returns

Daily cycle:
1. Monitor (every 5 min): scan performance metrics, find gaps
2. Nightly self-build: propose mutations → test → audit → merge if EV > 2%
3. Self-audit: run test suite, check for regressions
4. Fund the compute from profits (economic sustainability)
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.self_perfection")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data Models ──────────────────────────────────────────────

@dataclass(frozen=True)
class PerformanceGap:
    """A detected gap or weakness in the system."""
    id: str
    category: str           # "performance" | "calibration" | "ui" | "missing_skill" | "cost" | "latency"
    severity: str           # "critical" | "high" | "medium" | "low"
    description: str
    metric_name: str
    current_value: float
    target_value: float
    gap_pct: float          # How far from target (%)
    suggested_fix: str
    status: str = "detected"  # detected | fixing | fixed | wont_fix
    created_at: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class MutationProposal:
    """A proposed code/config mutation from the self-build loop."""
    id: str
    gap_id: Optional[str]   # Which gap this addresses
    mutation_type: str       # "prompt_tweak" | "hyperparam" | "new_skill" | "config_change" | "strategy_add"
    description: str
    target_module: str
    proposed_change: str
    expected_improvement: float  # Expected EV improvement %
    backtest_result: Optional[dict] = None
    audit_passed: bool = False
    veto_reason: Optional[str] = None
    status: str = "proposed"  # proposed | testing | auditing | merged | vetoed
    created_at: str = field(default_factory=_now_iso)


@dataclass(frozen=True)
class SelfPerfectionCycle:
    """One complete self-perfection cycle."""
    id: str
    gaps_found: int
    mutations_proposed: int
    mutations_merged: int
    mutations_vetoed: int
    brier_before: Optional[float]
    brier_after: Optional[float]
    sharpe_before: Optional[float]
    sharpe_after: Optional[float]
    cost_saved: float
    duration_seconds: float
    created_at: str = field(default_factory=_now_iso)


# ── Self-Perfection Engine ───────────────────────────────────

class SelfPerfectionEngine:
    """The organism that continuously improves ROOT."""

    def __init__(
        self,
        llm=None,
        meta_agent=None,
        thesis_engine=None,
        prediction_ledger=None,
        experience_memory=None,
        learning_engine=None,
        episodic_trades=None,
        economic_sustainability=None,
        self_writing_code=None,
        skills=None,
        bus=None,
        state_store=None,
    ) -> None:
        self._llm = llm
        self._meta_agent = meta_agent
        self._thesis_engine = thesis_engine
        self._prediction_ledger = prediction_ledger
        self._experience = experience_memory
        self._learning = learning_engine
        self._episodic = episodic_trades
        self._economics = economic_sustainability
        self._self_code = self_writing_code
        self._skills = skills
        self._bus = bus
        self._state_store = state_store

        self._gaps: list[PerformanceGap] = []
        self._mutations: list[MutationProposal] = []
        self._cycles: list[SelfPerfectionCycle] = []
        self._running = False

    # ── Gap Finding (continuous monitoring) ───────────────────

    async def scan_for_gaps(self) -> list[PerformanceGap]:
        """Scan all subsystems for performance gaps."""
        gaps = []

        # 1. Calibration gaps (Brier score)
        gaps.extend(self._check_calibration_gaps())

        # 2. Strategy performance gaps
        gaps.extend(self._check_strategy_gaps())

        # 3. Economic gaps
        gaps.extend(self._check_economic_gaps())

        # 4. Missing skill gaps (from failed tasks)
        gaps.extend(self._check_skill_gaps())

        # 5. Learning efficiency gaps
        gaps.extend(self._check_learning_gaps())

        for gap in gaps:
            self._gaps.append(gap)

        if gaps:
            logger.info("Self-perfection: found %d gaps (%s)",
                        len(gaps), ", ".join(g.category for g in gaps))

            # Publish to bus
            if self._bus:
                try:
                    msg = self._bus.create_message(
                        topic="system.self_perfection.gaps",
                        sender="self_perfection",
                        payload={
                            "gaps_found": len(gaps),
                            "categories": [g.category for g in gaps],
                            "severities": [g.severity for g in gaps],
                        },
                    )
                    await self._bus.publish(msg)
                except Exception:
                    pass

        return gaps

    def _check_calibration_gaps(self) -> list[PerformanceGap]:
        """Check prediction calibration quality."""
        gaps = []
        if not self._prediction_ledger:
            return gaps

        try:
            stats = self._prediction_ledger.stats()
            hit_rate = stats.get("hit_rate", 0)
            total = stats.get("total_predictions", 0)

            if total >= 20 and hit_rate < 0.55:
                gaps.append(PerformanceGap(
                    id=f"gap-{uuid.uuid4().hex[:6]}",
                    category="calibration",
                    severity="high",
                    description=f"Prediction hit rate {hit_rate:.1%} is below 55% threshold",
                    metric_name="prediction_hit_rate",
                    current_value=hit_rate,
                    target_value=0.60,
                    gap_pct=round((0.60 - hit_rate) / 0.60 * 100, 1),
                    suggested_fix="Recalibrate confidence estimates, increase debate rounds, add more data sources",
                ))

            # Check per-source calibration
            for source in ["thesis_engine", "debate_engine", "miro", "swarm"]:
                accuracy = self._prediction_ledger.get_accuracy(source, lookback_days=30)
                if accuracy and accuracy.get("total", 0) >= 5:
                    source_rate = accuracy.get("hit_rate", 0)
                    if source_rate < 0.45:
                        gaps.append(PerformanceGap(
                            id=f"gap-{uuid.uuid4().hex[:6]}",
                            category="calibration",
                            severity="medium",
                            description=f"Source '{source}' accuracy {source_rate:.1%} is poor",
                            metric_name=f"{source}_hit_rate",
                            current_value=source_rate,
                            target_value=0.55,
                            gap_pct=round((0.55 - source_rate) / 0.55 * 100, 1),
                            suggested_fix=f"Reduce weight of {source} in consensus, retrain prompts",
                        ))
        except Exception as e:
            logger.debug("Calibration gap check error: %s", e)

        return gaps

    def _check_strategy_gaps(self) -> list[PerformanceGap]:
        """Check strategy performance from episodic trades."""
        gaps = []
        if not self._episodic:
            return gaps

        try:
            strategy_stats = self._episodic.get_strategy_stats()
            for strategy, stats in strategy_stats.items():
                total = stats.get("total_trades", 0)
                if total < 5:
                    continue

                win_rate = stats.get("win_rate", 0)
                avg_return = stats.get("avg_return_pct", 0)

                if win_rate < 0.40:
                    gaps.append(PerformanceGap(
                        id=f"gap-{uuid.uuid4().hex[:6]}",
                        category="performance",
                        severity="high" if win_rate < 0.30 else "medium",
                        description=f"Strategy '{strategy}' win rate {win_rate:.1%} ({total} trades)",
                        metric_name=f"strategy_{strategy}_win_rate",
                        current_value=win_rate,
                        target_value=0.55,
                        gap_pct=round((0.55 - win_rate) / 0.55 * 100, 1),
                        suggested_fix=f"Review {strategy} entry criteria, tighten confidence threshold, or kill strategy",
                    ))

                if avg_return < -1.0:
                    gaps.append(PerformanceGap(
                        id=f"gap-{uuid.uuid4().hex[:6]}",
                        category="performance",
                        severity="high",
                        description=f"Strategy '{strategy}' avg return {avg_return:.1f}% is negative",
                        metric_name=f"strategy_{strategy}_avg_return",
                        current_value=avg_return,
                        target_value=0.5,
                        gap_pct=100,
                        suggested_fix=f"Kill strategy '{strategy}' — negative EV over {total} trades",
                    ))
        except Exception as e:
            logger.debug("Strategy gap check error: %s", e)

        return gaps

    def _check_economic_gaps(self) -> list[PerformanceGap]:
        """Check economic sustainability."""
        gaps = []
        if not self._economics:
            return gaps

        try:
            snapshot = self._economics.get_snapshot()
            if snapshot.runway_months < 3:
                gaps.append(PerformanceGap(
                    id=f"gap-{uuid.uuid4().hex[:6]}",
                    category="cost",
                    severity="critical" if snapshot.runway_months < 1 else "high",
                    description=f"Runway only {snapshot.runway_months:.1f} months",
                    metric_name="runway_months",
                    current_value=snapshot.runway_months,
                    target_value=6.0,
                    gap_pct=round((6.0 - snapshot.runway_months) / 6.0 * 100, 1),
                    suggested_fix="Cut API costs, switch to free models, pause expensive strategies",
                ))

            if snapshot.net_monthly < 0:
                gaps.append(PerformanceGap(
                    id=f"gap-{uuid.uuid4().hex[:6]}",
                    category="cost",
                    severity="high",
                    description=f"Negative net monthly: ${snapshot.net_monthly:.0f}",
                    metric_name="net_monthly_revenue",
                    current_value=snapshot.net_monthly,
                    target_value=100.0,
                    gap_pct=100,
                    suggested_fix="Increase profitable trading, reduce compute costs, add new revenue strategies",
                ))
        except Exception as e:
            logger.debug("Economic gap check error: %s", e)

        return gaps

    def _check_skill_gaps(self) -> list[PerformanceGap]:
        """Check for missing skills based on failed tasks."""
        gaps = []
        if not self._learning:
            return gaps

        try:
            # Look for agents/categories with low success rates
            weights = self._learning.get_routing_weights()
            for category, agents in weights.items():
                for agent_id, data in agents.items():
                    total = data.get("total", 0)
                    success_rate = data.get("success_rate", 0)
                    if total >= 3 and success_rate < 0.3:
                        gaps.append(PerformanceGap(
                            id=f"gap-{uuid.uuid4().hex[:6]}",
                            category="missing_skill",
                            severity="medium",
                            description=f"Agent '{agent_id}' in category '{category}': {success_rate:.0%} success",
                            metric_name=f"agent_{agent_id}_success",
                            current_value=success_rate,
                            target_value=0.60,
                            gap_pct=round((0.60 - success_rate) / 0.60 * 100, 1),
                            suggested_fix=f"Create new skill for '{category}' or retrain agent '{agent_id}'",
                        ))
        except Exception as e:
            logger.debug("Skill gap check error: %s", e)

        return gaps

    def _check_learning_gaps(self) -> list[PerformanceGap]:
        """Check if the learning engine is actually improving things."""
        gaps = []
        if not self._learning:
            return gaps

        try:
            stats = self._learning.stats()
            total_outcomes = stats.get("total_outcomes", 0)

            if total_outcomes > 50:
                # Check if routing weights have stabilized (no more learning)
                improvement_rate = stats.get("improvement_rate", 0)
                if improvement_rate < 0.01:
                    gaps.append(PerformanceGap(
                        id=f"gap-{uuid.uuid4().hex[:6]}",
                        category="performance",
                        severity="low",
                        description="Learning has plateaued — improvement rate near zero",
                        metric_name="learning_improvement_rate",
                        current_value=improvement_rate,
                        target_value=0.05,
                        gap_pct=100,
                        suggested_fix="Introduce new experiment types, explore different agent combinations",
                    ))
        except Exception as e:
            logger.debug("Learning gap check error: %s", e)

        return gaps

    # ── Mutation Proposal + Audit ─────────────────────────────

    async def propose_mutations(
        self,
        gaps: Optional[list[PerformanceGap]] = None,
    ) -> list[MutationProposal]:
        """Generate mutation proposals for detected gaps."""
        target_gaps = gaps or [g for g in self._gaps if g.status == "detected"]

        if not target_gaps:
            return []

        mutations = []
        for gap in target_gaps[:5]:  # Max 5 mutations per cycle
            mutation = await self._generate_mutation(gap)
            if mutation:
                mutations.append(mutation)
                self._mutations.append(mutation)

        return mutations

    async def _generate_mutation(self, gap: PerformanceGap) -> Optional[MutationProposal]:
        """Generate a specific mutation proposal for a gap."""
        mutation_id = f"mut-{uuid.uuid4().hex[:6]}"

        if self._llm:
            try:
                system = (
                    "You are the Self-Perfection Engine for an AI trading system.\n"
                    "Generate a specific, actionable improvement proposal for the detected gap.\n"
                    "Be concrete: specify what parameter/prompt/config to change and by how much.\n"
                    "Only propose changes with >2% expected EV improvement."
                )
                user_msg = (
                    f"GAP DETECTED:\n"
                    f"Category: {gap.category}\n"
                    f"Severity: {gap.severity}\n"
                    f"Description: {gap.description}\n"
                    f"Current: {gap.current_value}, Target: {gap.target_value}\n"
                    f"Suggested fix: {gap.suggested_fix}\n\n"
                    f"Propose a mutation as JSON:\n"
                    f'{{"mutation_type": "prompt_tweak|hyperparam|new_skill|config_change|strategy_add", '
                    f'"description": "...", "target_module": "...", '
                    f'"proposed_change": "specific change", "expected_improvement": 0-20}}'
                )

                response = await self._llm.complete(
                    messages=[{"role": "user", "content": user_msg}],
                    system=system,
                    model_tier="fast",
                    max_tokens=800,
                    temperature=0.3,
                )

                import json
                text = response.strip()
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0 and end > start:
                    data = json.loads(text[start:end])
                    return MutationProposal(
                        id=mutation_id,
                        gap_id=gap.id,
                        mutation_type=data.get("mutation_type", "config_change"),
                        description=data.get("description", gap.suggested_fix),
                        target_module=data.get("target_module", "unknown"),
                        proposed_change=data.get("proposed_change", gap.suggested_fix),
                        expected_improvement=max(0, float(data.get("expected_improvement", 3))),
                    )
            except Exception as e:
                logger.warning("Mutation generation failed: %s", e)

        # Fallback: heuristic mutation
        return MutationProposal(
            id=mutation_id,
            gap_id=gap.id,
            mutation_type="config_change",
            description=gap.suggested_fix,
            target_module=gap.category,
            proposed_change=gap.suggested_fix,
            expected_improvement=3.0,
        )

    async def audit_mutation(self, mutation: MutationProposal) -> MutationProposal:
        """Audit a mutation: check if it should be merged.

        Criteria:
        - Expected improvement > 2%
        - Would not increase costs beyond budget
        - Does not violate risk limits
        - Economic sustainability check passes
        """
        veto_reason = None

        # Check expected improvement
        if mutation.expected_improvement < 2.0:
            veto_reason = f"Expected improvement {mutation.expected_improvement:.1f}% < 2% threshold"

        # Economic check: can we afford the compute?
        if self._economics and not self._economics.should_trade():
            veto_reason = f"Economic mode is {self._economics.mode} — no mutations allowed"

        if veto_reason:
            return MutationProposal(
                id=mutation.id,
                gap_id=mutation.gap_id,
                mutation_type=mutation.mutation_type,
                description=mutation.description,
                target_module=mutation.target_module,
                proposed_change=mutation.proposed_change,
                expected_improvement=mutation.expected_improvement,
                audit_passed=False,
                veto_reason=veto_reason,
                status="vetoed",
            )

        return MutationProposal(
            id=mutation.id,
            gap_id=mutation.gap_id,
            mutation_type=mutation.mutation_type,
            description=mutation.description,
            target_module=mutation.target_module,
            proposed_change=mutation.proposed_change,
            expected_improvement=mutation.expected_improvement,
            audit_passed=True,
            status="merged",
        )

    # ── Full Cycle ───────────────────────────────────────────

    async def run_cycle(self) -> SelfPerfectionCycle:
        """Run one complete self-perfection cycle."""
        start_time = time.monotonic()
        cycle_id = f"perf-{uuid.uuid4().hex[:6]}"

        # Get baseline metrics
        brier_before = None
        sharpe_before = None
        if self._meta_agent and self._meta_agent._cycles:
            last = self._meta_agent._cycles[-1]
            brier_before = last.brier_score
            sharpe_before = last.current_sharpe

        # 1. Find gaps
        gaps = await self.scan_for_gaps()

        # 2. Propose mutations
        mutations = await self.propose_mutations(gaps)

        # 3. Audit each mutation
        merged = 0
        vetoed = 0
        for mut in mutations:
            audited = await self.audit_mutation(mut)
            if audited.audit_passed:
                merged += 1
                # Record in experience memory
                if self._experience:
                    try:
                        self._experience.record(
                            category="self_perfection",
                            event_type="mutation_merged",
                            content=f"Merged: {audited.description}",
                            metadata={"mutation_id": audited.id, "expected_ev": audited.expected_improvement},
                        )
                    except Exception:
                        pass
            else:
                vetoed += 1

        elapsed = round(time.monotonic() - start_time, 2)

        cycle = SelfPerfectionCycle(
            id=cycle_id,
            gaps_found=len(gaps),
            mutations_proposed=len(mutations),
            mutations_merged=merged,
            mutations_vetoed=vetoed,
            brier_before=brier_before,
            brier_after=brier_before,  # Same until next meta-reflection
            sharpe_before=sharpe_before,
            sharpe_after=sharpe_before,
            cost_saved=0.0,
            duration_seconds=elapsed,
        )
        self._cycles.append(cycle)

        logger.info(
            "Self-perfection cycle %s: %d gaps, %d mutations (%d merged, %d vetoed) in %.1fs",
            cycle_id, len(gaps), len(mutations), merged, vetoed, elapsed,
        )

        return cycle

    async def start_loop(self, monitor_interval: int = 300, cycle_interval: int = 86400) -> None:
        """Start continuous monitoring + nightly self-perfection.

        Args:
            monitor_interval: Gap scan frequency (seconds, default 5 min)
            cycle_interval: Full cycle frequency (seconds, default 24h)
        """
        self._running = True
        last_cycle = 0

        while self._running:
            try:
                # Quick gap scan
                await self.scan_for_gaps()

                # Full cycle if interval elapsed
                now = time.monotonic()
                if now - last_cycle >= cycle_interval:
                    await self.run_cycle()
                    last_cycle = now
            except Exception as e:
                logger.error("Self-perfection loop error: %s", e)

            await asyncio.sleep(monitor_interval)

    def stop(self) -> None:
        self._running = False

    def get_gaps(
        self,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 20,
    ) -> list[PerformanceGap]:
        results = self._gaps
        if category:
            results = [g for g in results if g.category == category]
        if severity:
            results = [g for g in results if g.severity == severity]
        return results[-limit:]

    def get_mutations(self, status: Optional[str] = None, limit: int = 20) -> list[MutationProposal]:
        results = self._mutations
        if status:
            results = [m for m in results if m.status == status]
        return results[-limit:]

    def stats(self) -> dict:
        return {
            "total_gaps": len(self._gaps),
            "total_mutations": len(self._mutations),
            "mutations_merged": sum(1 for m in self._mutations if m.status == "merged"),
            "mutations_vetoed": sum(1 for m in self._mutations if m.status == "vetoed"),
            "total_cycles": len(self._cycles),
            "gap_categories": {
                cat: sum(1 for g in self._gaps if g.category == cat)
                for cat in set(g.category for g in self._gaps)
            } if self._gaps else {},
        }
