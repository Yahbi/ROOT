"""Agent evolution, self-rewrite, task queue, trading, and goal actions."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("root.proactive.execution")


async def evolve_agents(*, self_dev: Any = None) -> str:
    """Assess agent performance and propose concrete improvements."""
    if not self_dev:
        return "no self-dev engine"

    assessment = self_dev.assess()
    gaps = assessment.get("capability_gaps", [])

    # Actually propose improvements for each gap found
    proposed = 0
    for gap in gaps[:3]:
        area = gap.get("area", "unknown")
        suggestion = gap.get("suggestion", "")
        if suggestion:
            self_dev.propose_improvement(
                area=area,
                description=suggestion,
                rationale=f"Proactive agent evolution — gap: {gap.get('description', '')}",
            )
            proposed += 1

    if proposed:
        return f"Agent evolution: proposed {proposed} improvements for {len(gaps)} gaps"
    return f"Maturity: {assessment.get('maturity_level', '?')} — no gaps"


async def self_rewrite(
    *,
    collab: Any = None,
    llm: Any = None,
    self_dev: Any = None,
) -> str:
    """ROOT analyzes itself and proposes code enhancements via Coder agent."""
    if not collab or not llm:
        return "requires LLM + collaboration"

    result = await collab.pipeline(
        initiator="proactive_engine",
        goal="Self-improvement: analyze ROOT and propose enhancements",
        steps=[
            {
                "agent_id": "analyst",
                "task": (
                    "Analyze ROOT's current capabilities and identify the single most "
                    "impactful improvement that could be made. Consider: "
                    "1) What capability is most lacking? "
                    "2) What existing feature could be enhanced? "
                    "3) What integration would add the most value for Yohan? "
                    "Be specific and actionable."
                ),
            },
            {
                "agent_id": "coder",
                "task": (
                    "Based on the analysis below, propose a concrete code enhancement "
                    "for ROOT. Describe: 1) What file to create or modify, "
                    "2) The key functions/classes needed, 3) How it integrates with "
                    "existing systems. Do NOT write full code — just the design. "
                    "Context from analysis: {prev_result}"
                ),
            },
        ],
    )

    # Store the proposal
    if result.final_result and self_dev:
        self_dev.propose_improvement(
            area="self_rewrite",
            description=result.final_result[:300],
            rationale="Autonomous self-improvement proposal from Analyst + Coder pipeline",
        )

    return result.final_result or "self-rewrite analysis complete"


async def drain_task_queue(
    *,
    task_queue: Any = None,
    task_executor: Any = None,
) -> str:
    """Pull pending tasks from persistent queue and submit to executor."""
    if not task_queue or not task_executor:
        return "requires task_queue + task_executor"

    # First sync completed executor tasks back to queue
    synced = await task_queue.sync_from_executor(task_executor)

    # Then drain new pending tasks to executor
    submitted = await task_queue.drain_to_executor(task_executor, limit=3)

    # Activate any due scheduled tasks
    task_queue.activate_scheduled()

    return f"Task queue: {submitted} submitted, {synced} synced back"


async def auto_trade_cycle(
    *,
    hedge_fund: Any = None,
    escalation: Any = None,
) -> str:
    """Run hedge fund trading cycle with escalation-gated approval."""
    if not hedge_fund:
        return "requires hedge_fund engine"

    # Check escalation confidence before running
    if escalation:
        decision = escalation.should_auto_execute(
            "auto_trade_cycle", risk_level="critical",
        )
        if not decision.should_auto_execute:
            logger.info("Auto-trade blocked by escalation: %s", decision.reason)
            return f"Escalation blocked: {decision.reason}"

        # Record the decision
        escalation.record_decision(
            "auto_trade_cycle",
            "Proactive autonomous trading cycle",
            auto_executed=True,
        )

    results = await hedge_fund.run_cycle()

    # Record outcome in escalation
    if escalation and results.get("trades_executed", 0) > 0:
        escalation.record_decision(
            "auto_trade_cycle",
            f"Executed {results['trades_executed']} trades",
            auto_executed=True,
        )

    return (
        f"Trade cycle: {results.get('signals_generated', 0)} signals, "
        f"{results.get('trades_executed', 0)} executed, "
        f"{results.get('trades_blocked', 0)} blocked"
    )


async def assess_goals(*, goal_engine: Any = None) -> str:
    """Assess active goals, detect stalled progress, propose task generation."""
    if not goal_engine:
        return "requires goal_engine"

    assessment = await goal_engine.assess_all_goals()
    stalled = [u for u in assessment.get("updates", []) if u.get("status") == "stalled"]

    # For stalled goals, auto-decompose into tasks
    decomposed = 0
    for stall in stalled[:2]:  # Max 2 decompositions per cycle
        goal_id = stall["goal_id"]
        tasks = await goal_engine.decompose_goal(goal_id)
        if tasks:
            decomposed += 1
            logger.info(
                "Auto-decomposed stalled goal %s into %d tasks",
                goal_id, len(tasks),
            )

    return (
        f"Goals: {assessment.get('goals_assessed', 0)} assessed, "
        f"{len(stalled)} stalled, {decomposed} decomposed into tasks"
    )


async def track_goals(
    *,
    memory: Any = None,
    llm: Any = None,
) -> str:
    """Track progress toward Yohan's goals using LLM assessment."""
    if not memory:
        return "no memory engine"

    from backend.models.memory import MemoryQuery, MemoryType
    query = MemoryQuery(query="goal", memory_type=MemoryType.GOAL, limit=10)
    goals = memory.search(query)
    if not goals:
        return "no goals found"

    goal_list = "\n".join(f"- {g.content}" for g in goals)

    if llm:
        # Use LLM to assess goal progress
        recent = memory.search(
            MemoryQuery(query="", limit=20, min_confidence=0.5)
        )
        recent_context = "\n".join(f"- {m.content[:150]}" for m in recent[:10])

        prompt = (
            f"Yohan's active goals:\n{goal_list}\n\n"
            f"Recent activity/knowledge:\n{recent_context}\n\n"
            "For each goal: 1) Progress status (on-track/stalled/blocked), "
            "2) What's been done, 3) Next step needed. Be concise."
        )
        assessment = await llm.complete(
            system="You are ROOT's goal tracker. Assess progress concisely.",
            messages=[{"role": "user", "content": prompt}],
            model_tier="fast", max_tokens=800,
        )

        # Store assessment as observation
        from backend.models.memory import MemoryEntry
        memory.store(MemoryEntry(
            content=f"Goal tracking: {assessment[:300]}",
            memory_type=MemoryType.OBSERVATION,
            tags=["goals", "tracking", "proactive"],
            source="goal_tracker",
            confidence=0.7,
        ))
        return assessment[:500]

    return f"Tracking {len(goals)} goals: {goal_list[:200]}"


async def validate_strategies(*, strategy_validator: Any = None) -> str:
    """Run autonomous strategy validation: discover → backtest → rank → promote."""
    if not strategy_validator:
        return "requires strategy_validator"

    results = await strategy_validator.validate_all_strategies()
    promoted = [r for r in results if r.get("promoted")]
    top = results[0] if results else None

    summary = (
        f"Strategy scan: {len(results)} tested, {len(promoted)} promoted"
    )
    if top:
        summary += (
            f". Top: {top['strategy_name']} "
            f"(Sharpe={top.get('sharpe_ratio', 0):.2f}, "
            f"return={top.get('total_return_pct', 0):.1f}%)"
        )

    return summary
