"""Agent management routes."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.models.response import APIResponse

logger = logging.getLogger("root.routes.agents")

router = APIRouter(prefix="/api/agents", tags=["agents"])


class DelegateRequest(BaseModel):
    agent_id: str
    task: str


class SubtaskRequest(BaseModel):
    agent_id: str
    task: str
    priority: int = 5


class ParallelRequest(BaseModel):
    """Dispatch multiple agent tasks in parallel via the Orchestrator."""

    subtasks: list[SubtaskRequest] = Field(min_length=1)


class OpenClawSwarmRequest(BaseModel):
    """Run OpenClaw data discovery and MiRo swarm analysis in parallel.

    openclaw_task: what OpenClaw should do (e.g. "run full cycle", "gaps", "discover")
    swarm_task: what MiRo should analyze (e.g. a scenario, prediction, or topic)
    """

    openclaw_task: str = "status"
    swarm_task: str = ""
    swarm_agent_count: int = 5
    swarm_rounds: int = 1


@router.get("")
async def list_agents(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """List all registered agents and their status."""
    registry = request.app.state.registry
    agents = registry.list_agents()
    items = [a.model_dump() for a in agents]
    items = items[offset: offset + limit]
    return APIResponse.ok(items)


@router.get("/{agent_id}")
async def get_agent(agent_id: str, request: Request):
    """Get details for a specific agent."""
    registry = request.app.state.registry
    agent = registry.get(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent.model_dump()


@router.get("/{agent_id}/health")
async def agent_health(agent_id: str, request: Request):
    """Check health of a specific agent's external service."""
    registry = request.app.state.registry
    connector = registry.get_connector(agent_id)
    if not connector:
        return {"status": "no_connector"}
    if hasattr(connector, "health_check"):
        return await connector.health_check()
    return {"status": "unknown"}


@router.post("/delegate")
async def delegate(req: DelegateRequest, request: Request):
    """Delegate a task to a specific agent."""
    brain = request.app.state.brain
    result = await brain.delegate(req.agent_id, req.task)
    return result


@router.post("/parallel")
async def parallel_dispatch(req: ParallelRequest, request: Request):
    """Dispatch multiple agent tasks in parallel via the Orchestrator.

    Example body:
    {
      "subtasks": [
        {"agent_id": "openclaw", "task": "run gaps analysis"},
        {"agent_id": "miro", "task": "analyze US housing market trends"}
      ]
    }
    """
    orchestrator = request.app.state.orchestrator
    subtask_dicts = [st.model_dump() for st in req.subtasks]
    result = await orchestrator.execute_parallel(subtask_dicts)
    return {
        "workflow_id": result.workflow_id,
        "total_duration_seconds": result.total_duration_seconds,
        "success_count": result.success_count,
        "failure_count": result.failure_count,
        "tasks": [
            {
                "id": t.id,
                "agent_id": t.agent_id,
                "description": t.description,
                "status": t.status.value,
                "result": t.result,
                "error": t.error,
            }
            for t in result.tasks
        ],
    }


@router.post("/openclaw-swarm")
async def openclaw_swarm_parallel(req: OpenClawSwarmRequest, request: Request):
    """Run OpenClaw + MiRo swarm in parallel and return combined results.

    OpenClaw handles data source discovery/validation while MiRo runs
    multi-perspective swarm analysis — both execute concurrently.
    """
    orchestrator = request.app.state.orchestrator
    subtasks = [
        {"agent_id": "openclaw", "task": req.openclaw_task, "priority": 3},
    ]
    if req.swarm_task:
        swarm_desc = (
            f"Run a swarm simulation with {req.swarm_agent_count} virtual agents "
            f"over {req.swarm_rounds} round(s) on: {req.swarm_task}"
        )
        subtasks.append({"agent_id": "miro", "task": swarm_desc, "priority": 3})

    result = await orchestrator.execute_parallel(subtasks)

    response: dict = {
        "workflow_id": result.workflow_id,
        "total_duration_seconds": result.total_duration_seconds,
        "success_count": result.success_count,
        "failure_count": result.failure_count,
    }
    for t in result.tasks:
        key = t.agent_id  # "openclaw" or "miro"
        response[key] = {
            "status": t.status.value,
            "result": t.result,
            "error": t.error,
        }
    return response


@router.get("/{agent_id}/stats")
async def agent_stats(agent_id: str, request: Request):
    """Get performance stats for an agent."""
    registry = request.app.state.registry
    agent = registry.get(agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    learning = getattr(request.app.state, "learning", None)
    stats: dict = {
        "agent_id": agent_id,
        "total_tasks": agent.tasks_completed,
        "recent_tasks": [],
    }

    if learning:
        try:
            outcomes = learning.get_agent_outcomes(agent_id, limit=10)
            stats["recent_tasks"] = [
                {
                    "description": o.get("task_description", "") if isinstance(o, dict) else "",
                    "status": o.get("status", "") if isinstance(o, dict) else "",
                    "completed_at": o.get("completed_at", "") if isinstance(o, dict) else "",
                    "result_quality": o.get("result_quality", 0) if isinstance(o, dict) else 0,
                }
                for o in (outcomes if isinstance(outcomes, list) else [])
            ]
            weights = learning.get_routing_weights()
            stats["routing_weight"] = weights.get(agent_id, 0.0) if isinstance(weights, dict) else 0.0
            total = len(stats["recent_tasks"])
            completed = sum(1 for t in stats["recent_tasks"] if t["status"] == "completed")
            stats["success_rate"] = completed / total if total > 0 else 0.0
        except Exception as exc:
            logger.warning("Failed to fetch learning stats for agent %s: %s", agent_id, exc)

    return stats


@router.get("/{agent_id}/skills")
async def agent_skills(agent_id: str, request: Request):
    """List skills for agents that support it (e.g., HERMES)."""
    connector = request.app.state.registry.get_connector(agent_id)
    if connector and hasattr(connector, "list_skills"):
        return await connector.list_skills()
    return []
