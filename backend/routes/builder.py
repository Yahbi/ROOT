"""Builder Agent routes — monitor and control the self-improving agent."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/builder", tags=["builder"])


@router.get("/status")
async def builder_status(request: Request):
    """Get builder agent status and stats."""
    builder = getattr(request.app.state, "builder", None)
    if not builder:
        raise HTTPException(status_code=503, detail="Builder agent not initialized")
    return builder.stats()


@router.post("/run")
async def trigger_build(request: Request):
    """Manually trigger a single builder improvement cycle."""
    builder = getattr(request.app.state, "builder", None)
    if not builder:
        raise HTTPException(status_code=503, detail="Builder agent not initialized")
    tasks = await builder.run_once()
    return {
        "tasks": [
            {
                "id": t.id,
                "type": t.task_type,
                "description": t.description,
                "status": t.status,
                "result": t.result,
            }
            for t in tasks
        ]
    }


@router.get("/history")
async def builder_history(request: Request, limit: int = Query(default=30, ge=1, le=500)):
    """Get builder task history."""
    builder = getattr(request.app.state, "builder", None)
    if not builder:
        raise HTTPException(status_code=503, detail="Builder agent not initialized")
    return [
        {
            "id": t.id,
            "type": t.task_type,
            "description": t.description,
            "status": t.status,
            "result": t.result,
            "impact": t.impact_score,
            "created_at": t.created_at,
            "completed_at": t.completed_at,
        }
        for t in builder.get_history(limit)
    ]
