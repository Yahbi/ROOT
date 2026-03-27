"""Analytics API — time-series data for charts and dashboards."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query, Request

from backend.config import DATA_DIR

logger = logging.getLogger("root.routes.analytics")

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _query_db(db_path: str, sql: str, params: tuple = ()) -> list[dict]:
    """Execute a read query and return rows as dicts."""
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as exc:
        logger.warning("Analytics DB query failed: %s", exc)
        return []


@router.get("/memory-growth")
async def memory_growth(
    request: Request,
    days: int = Query(30, ge=1, le=365),
):
    """Memory count over time (daily)."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = _query_db(
        DATA_DIR / "memory.db",
        """
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM memories
        WHERE created_at >= ?
        GROUP BY DATE(created_at)
        ORDER BY date
        """,
        (cutoff,),
    )
    # Cumulative
    total = request.app.state.memory.count() - sum(r["count"] for r in rows)
    cumulative = []
    running = max(total, 0)
    for r in rows:
        running += r["count"]
        cumulative.append({"date": r["date"], "total": running, "added": r["count"]})
    return {"data": cumulative, "period_days": days}


@router.get("/agent-activity")
async def agent_activity(
    days: int = Query(7, ge=1, le=90),
):
    """Agent interaction counts over time."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = _query_db(
        DATA_DIR / "learning.db",
        """
        SELECT DATE(timestamp) as date, agent_id,
               COUNT(*) as interactions,
               AVG(result_quality) as avg_quality
        FROM interactions
        WHERE timestamp >= ?
        GROUP BY DATE(timestamp), agent_id
        ORDER BY date, interactions DESC
        """,
        (cutoff,),
    )
    # Group by date
    by_date: dict[str, list] = {}
    for r in rows:
        by_date.setdefault(r["date"], []).append({
            "agent": r["agent_id"],
            "count": r["interactions"],
            "quality": round(r["avg_quality"] or 0, 2),
        })
    return {"data": [{"date": d, "agents": a} for d, a in by_date.items()], "period_days": days}


@router.get("/cost-trend")
async def cost_trend(
    request: Request,
    days: int = Query(30, ge=1, le=365),
):
    """LLM cost over time (daily)."""
    tracker = getattr(request.app.state, "cost_tracker", None)
    if not tracker:
        return {"data": [], "period_days": days}

    daily = tracker.daily_trend(days=days)
    return {"data": daily, "period_days": days}


@router.get("/portfolio-history")
async def portfolio_history(
    days: int = Query(30, ge=1, le=365),
):
    """Trading portfolio snapshots over time."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
    rows = _query_db(
        DATA_DIR / "hedge_fund.db",
        """
        SELECT DATE(timestamp) as date,
               AVG(total_value) as avg_value,
               SUM(CASE WHEN pnl > 0 THEN pnl ELSE 0 END) as gains,
               SUM(CASE WHEN pnl < 0 THEN pnl ELSE 0 END) as losses
        FROM portfolio_snapshots
        WHERE timestamp >= ?
        GROUP BY DATE(timestamp)
        ORDER BY date
        """,
        (cutoff,),
    )
    return {"data": rows, "period_days": days}


@router.get("/routing-weights")
async def routing_weights(request: Request):
    """Current ASTRA routing weights for all agents."""
    learning = getattr(request.app.state, "learning", None)
    if not learning:
        return {"data": []}

    weights = learning.get_routing_weights()
    # Top 15 agents by weight
    sorted_weights = sorted(weights.items(), key=lambda x: x[1], reverse=True)[:15]
    return {
        "data": [{"agent": a, "weight": round(w, 3)} for a, w in sorted_weights],
    }


@router.get("/system-pulse")
async def system_pulse(request: Request):
    """Real-time system health metrics for live dashboard."""
    mem = request.app.state.memory
    learning = getattr(request.app.state, "learning", None)
    cost_tracker = getattr(request.app.state, "cost_tracker", None)
    proactive = getattr(request.app.state, "proactive", None)
    hedge_fund = getattr(request.app.state, "hedge_fund", None)

    pulse: dict[str, Any] = {
        "timestamp": datetime.utcnow().isoformat(),
        "memory_count": mem.count(),
        "agent_count": request.app.state.registry.agent_count(),
    }

    if learning:
        stats = learning.stats()
        pulse["total_interactions"] = stats.get("total_interactions", 0)
        pulse["avg_quality"] = round(stats.get("average_quality", 0), 2)

    if cost_tracker:
        summary = cost_tracker.summary()
        pulse["cost_today_usd"] = round(summary.get("today_usd", 0), 4)
        pulse["cost_month_usd"] = round(summary.get("month_usd", 0), 4)
        pulse["total_llm_calls"] = summary.get("total_calls", 0)

    if proactive:
        p_stats = await proactive.stats()
        pulse["proactive_runs"] = p_stats.get("total_runs", 0)

    if hedge_fund:
        pulse["open_positions"] = hedge_fund.stats().get("open_positions", 0)

    return pulse


@router.get("/experience-summary")
async def experience_summary(request: Request):
    """Experience memory breakdown by type and domain."""
    exp = getattr(request.app.state, "experience_memory", None)
    if not exp:
        return {"data": {}}
    return {"data": exp.stats()}
