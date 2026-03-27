"""Task routes — autonomous goal decomposition and execution API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskSubmitRequest(BaseModel):
    goal: str = Field(..., min_length=1, max_length=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)


def _subtask_to_dict(s) -> dict:
    return {
        "id": s.id,
        "index": s.index,
        "description": s.description,
        "agent_id": s.agent_id,
        "tools_hint": list(s.tools_hint),
        "depends_on": list(s.depends_on),
        "risk_level": s.risk_level,
        "status": s.status,
        "result": (s.result or "")[:2000] if s.result else None,
        "error": s.error,
        "attempt": s.attempt,
        "started_at": s.started_at,
        "completed_at": s.completed_at,
    }


def _task_to_dict(t) -> dict:
    return {
        "id": t.id,
        "goal": t.goal,
        "status": t.status,
        "plan": {
            "reasoning": t.plan.reasoning,
            "estimated_duration_seconds": t.plan.estimated_duration_seconds,
            "subtask_count": len(t.plan.subtasks),
        } if t.plan else None,
        "subtasks": [_subtask_to_dict(s) for s in t.subtasks],
        "final_result": (t.final_result or "")[:3000] if t.final_result else None,
        "created_at": t.created_at,
        "started_at": t.started_at,
        "completed_at": t.completed_at,
        "metadata": t.metadata,
    }


@router.post("")
async def submit_task(req: TaskSubmitRequest, request: Request):
    """Submit a new autonomous task for decomposition and execution."""
    executor = request.app.state.task_executor
    task = await executor.submit(req.goal, req.metadata)
    return _task_to_dict(task)


@router.get("")
async def list_tasks(request: Request, limit: int = Query(default=50, ge=1, le=500)):
    """List all tasks, newest first."""
    executor = request.app.state.task_executor
    return {"tasks": [_task_to_dict(t) for t in executor.get_all(limit)]}


@router.get("/active")
async def active_tasks(request: Request):
    """Get currently executing tasks."""
    executor = request.app.state.task_executor
    return {"tasks": [_task_to_dict(t) for t in executor.get_active()]}


@router.get("/stats")
async def task_stats(request: Request):
    """Task executor statistics."""
    return request.app.state.task_executor.stats()


@router.get("/{task_id}")
async def get_task(task_id: str, request: Request):
    """Get task status and results."""
    executor = request.app.state.task_executor
    task = executor.get_task(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str, request: Request):
    """Cancel a running task."""
    executor = request.app.state.task_executor
    task = await executor.cancel(task_id)
    if not task:
        raise HTTPException(404, f"Task {task_id} not found")
    return _task_to_dict(task)
