"""Health, knowledge consolidation, and economic survival actions."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("root.proactive.health")


async def check_health(
    *,
    registry: Any = None,
    bus: Any = None,
) -> str:
    """Check health of all agents."""
    if not registry:
        return "no registry"

    agents = registry.list_agents()
    issues: list[str] = []

    for agent in agents:
        connector = registry.get_connector(agent.id)
        if connector and hasattr(connector, "health_check"):
            try:
                health = await connector.health_check()
                if health.get("status") not in ("online", "internal"):
                    issues.append(f"{agent.name}: {health.get('status', 'unknown')}")
            except Exception as exc:
                issues.append(f"{agent.name}: error ({exc})")

    if issues:
        result = f"Health issues: {', '.join(issues)}"
        logger.warning(result)

        if bus:
            msg = bus.create_message(
                topic="system.alert",
                sender="proactive_engine",
                payload={"type": "health_issue", "issues": issues},
            )
            await bus.publish(msg)
        return result

    return f"All {len(agents)} agents healthy"


async def consolidate_knowledge(*, memory: Any = None) -> str:
    """Consolidate and optimize ROOT's memory."""
    if not memory:
        return "no memory engine"

    stats_before = memory.count()
    decayed = memory.decay()

    return f"Memory consolidation: {stats_before} entries, {decayed} decayed"


async def survival_economics(
    *,
    hedge_fund: Any = None,
    goal_engine: Any = None,
    task_queue: Any = None,
    memory: Any = None,
) -> str:
    """Assess economic health and ensure system sustainability."""
    findings: list[str] = []

    # Check hedge fund portfolio status
    if hedge_fund:
        try:
            portfolio = hedge_fund.get_portfolio_summary()
            equity = portfolio.get("equity", 0)
            daily_pl = portfolio.get("daily_pl", 0)
            findings.append(f"Portfolio: ${equity:,.0f} (daily P&L: ${daily_pl:,.0f})")

            # Revenue health check
            if daily_pl < -100:
                findings.append("WARNING: Negative daily P&L — consider reducing positions")
        except Exception:
            findings.append("Portfolio check unavailable")

    # Check pending revenue opportunities in goals
    if goal_engine:
        goals = goal_engine.get_active_goals(limit=20)
        revenue_goals = [g for g in goals if g.category in ("trading", "product")]
        findings.append(f"Revenue goals: {len(revenue_goals)} active")

    # Check task throughput
    if task_queue:
        stats = task_queue.stats()
        completed = stats.get("by_status", {}).get("completed", 0)
        pending = stats.get("by_status", {}).get("pending", 0)
        findings.append(f"Task throughput: {completed} completed, {pending} pending")

    # Store economic assessment to memory
    if memory and findings:
        from backend.models.memory import MemoryEntry, MemoryType
        memory.store(MemoryEntry(
            content=f"Economic health check: {'; '.join(findings)}",
            memory_type=MemoryType.OBSERVATION,
            tags=["economics", "survival", "health"],
            source="proactive_engine",
            confidence=0.7,
        ))

    return f"Survival economics: {'; '.join(findings)}"


async def check_approval_timeouts(
    *,
    approval_chain: Any = None,
) -> str:
    """Expire stale pending approvals — HIGH auto-approved, CRITICAL expired."""
    if not approval_chain:
        return "no approval chain"

    resolved = approval_chain.expire_stale(timeout_minutes=60)
    if not resolved:
        pending = len(approval_chain.get_pending())
        return f"No stale approvals ({pending} pending)"

    approved = sum(1 for r in resolved if r.status.value == "approved")
    expired = sum(1 for r in resolved if r.status.value == "expired")
    return f"Approval timeouts: {approved} auto-approved, {expired} expired"


async def auto_recover_goals(
    *,
    goal_engine: Any = None,
) -> str:
    """Auto-recover stalled goals by decomposing into tasks."""
    if not goal_engine:
        return "no goal engine"

    result = await goal_engine.auto_recover_stalled(max_recoveries=3)
    recovered = result.get("recovered", [])
    total_stalled = result.get("total_stalled", 0)

    if not recovered:
        return f"No goals to recover ({total_stalled} stalled)"

    actions = [f"{r['goal_id']}: {r['action']}" for r in recovered]
    return f"Goal recovery: {', '.join(actions)} ({total_stalled} total stalled)"


async def auto_remediate_revenue(
    *,
    revenue_engine: Any = None,
) -> str:
    """Auto-remediate revenue emergencies — pause bad products, flag opportunities."""
    if not revenue_engine:
        return "no revenue engine"

    result = revenue_engine.auto_remediate()
    if not result.get("emergency"):
        return "No revenue emergency"

    paused = len(result.get("paused", []))
    earners = len(result.get("top_earners", []))
    near = len(result.get("near_profitable", []))
    return (
        f"Revenue remediation: {paused} products paused, "
        f"{earners} top earners, {near} near-profitable"
    )
