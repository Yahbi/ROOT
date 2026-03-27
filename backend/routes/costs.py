"""Cost tracking routes — LLM usage and spend analytics."""

from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/costs", tags=["costs"])


_EMPTY = {"total_cost": 0.0, "total_input_tokens": 0, "total_output_tokens": 0, "total_calls": 0}


@router.get("/summary")
async def cost_summary(request: Request):
    """Get overall LLM cost summary with daily/weekly/monthly breakdowns."""
    tracker = getattr(request.app.state, "cost_tracker", None)
    if not tracker:
        return _EMPTY
    return tracker.summary()


@router.get("/by-agent")
async def cost_by_agent(request: Request, limit: int = 20):
    """Get cost breakdown by caller agent."""
    tracker = getattr(request.app.state, "cost_tracker", None)
    if not tracker:
        return []
    return tracker.by_agent(limit=limit)


@router.get("/by-model")
async def cost_by_model(request: Request):
    """Get cost breakdown by model."""
    tracker = getattr(request.app.state, "cost_tracker", None)
    if not tracker:
        return []
    return tracker.by_model()


@router.get("/daily")
async def cost_daily(request: Request, days: int = 30):
    """Get daily cost trend for the last N days."""
    tracker = getattr(request.app.state, "cost_tracker", None)
    if not tracker:
        return []
    return tracker.daily_trend(days=days)
