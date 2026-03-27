"""Dashboard routes — aggregated system status with all subsystems."""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger("root.routes.dashboard")

from fastapi import APIRouter, Query, Request

from backend.models.response import APIResponse

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/status")
async def system_status(request: Request):
    """Full system status — all subsystems."""
    registry = request.app.state.registry
    memory = request.app.state.memory
    reflection = request.app.state.reflection
    skills = request.app.state.skills
    self_dev = request.app.state.self_dev
    hooks = request.app.state.hooks
    orchestrator = request.app.state.orchestrator
    plugins = getattr(request.app.state, "plugins", None)

    agents = registry.list_agents()

    # Check health of all external agents concurrently
    health_tasks = {}
    for agent in agents:
        connector = registry.get_connector(agent.id)
        if connector and hasattr(connector, "health_check"):
            health_tasks[agent.id] = connector.health_check()

    health_results = {}
    if health_tasks:
        results = await asyncio.gather(*health_tasks.values(), return_exceptions=True)
        for agent_id, result in zip(health_tasks.keys(), results):
            if isinstance(result, Exception):
                logger.warning("Health check failed for agent %s: %s", agent_id, result)
                health_results[agent_id] = {"status": "error", "reason": str(result)}
            else:
                health_results[agent_id] = result

    assessment = self_dev.assess()

    status_data = {
        "mode": getattr(request.app.state, "mode", "unknown"),
        "agents": [
            {
                **a.model_dump(),
                "health": health_results.get(a.id, {"status": "internal" if a.connector_type == "internal" else "unknown"}),
            }
            for a in agents
        ],
        "memory": memory.stats(),
        "skills": skills.stats(),
        "hooks": hooks.stats(),
        "plugins": plugins.stats() if plugins else {},
        "orchestrator": orchestrator.stats(),
        "self_dev": assessment,
        "reflections": [r.model_dump() for r in reflection.get_reflections(limit=5)],
        "learning": _get_learning_stats(request),
    }
    return APIResponse.ok(status_data)


def _get_learning_stats(request: Request) -> dict:
    """Extract learning engine stats if available."""
    learning = getattr(request.app.state, "learning", None)
    if not learning:
        return {}
    try:
        return {**learning.stats(), "insights": learning.get_insights()}
    except Exception as exc:
        logger.warning("Learning stats unavailable: %s", exc)
        return {}


@router.post("/reflect")
async def trigger_reflection(request: Request):
    """Manually trigger a self-reflection cycle."""
    reflection = request.app.state.reflection
    result = await reflection.reflect(trigger="manual")
    if result:
        return {"status": "completed", "reflection": result.model_dump()}
    return {"status": "skipped", "reason": "No LLM available or nothing to reflect on"}


@router.get("/assessment")
async def self_assessment(request: Request):
    """Get ROOT's self-assessment."""
    return request.app.state.self_dev.assess()


@router.get("/evolution")
async def evolution_log(request: Request, limit: int = Query(default=50, ge=1, le=500)):
    """Get ROOT's evolution history."""
    log = request.app.state.self_dev.get_evolution_log(limit=limit)
    return [
        {"id": e.id, "action_type": e.action_type, "description": e.description,
         "impact_score": e.impact_score, "timestamp": e.timestamp}
        for e in log
    ]


@router.get("/skills")
async def skill_index(request: Request):
    """Get full skill index."""
    categories = request.app.state.skills.list_categories()
    return {
        cat: [{"name": s.name, "description": s.description, "version": s.version,
               "tags": s.tags, "author": s.author} for s in skill_list]
        for cat, skill_list in sorted(categories.items())
    }


@router.get("/hooks")
async def hook_status(request: Request):
    """Get hook engine status and recent log."""
    hooks = request.app.state.hooks
    return {
        "stats": hooks.stats(),
        "recent_log": [
            {"hook": r.hook_name, "event": r.event.value, "success": r.success,
             "output": r.output[:200], "timestamp": r.timestamp}
            for r in hooks.get_log(limit=20)
        ],
    }


@router.get("/gaps")
async def capability_gaps(request: Request):
    """Get identified capability gaps."""
    return {"gaps": request.app.state.self_dev.identify_gaps()}


@router.get("/learning")
async def learning_status(request: Request):
    """Get learning engine stats, insights, and routing weights."""
    learning = getattr(request.app.state, "learning", None)
    if not learning:
        return {"status": "not_available"}
    return {
        "stats": learning.stats(),
        "insights": learning.get_insights(),
        "routing_weights": learning.get_routing_weights(),
        "experiment_stats": learning.get_experiment_stats(),
    }


@router.get("/providers")
async def provider_status(request: Request):
    """Get LLM provider status — all registered providers with health."""
    llm_router = getattr(request.app.state, "llm_router", None)
    if not llm_router or not hasattr(llm_router, "stats"):
        # Single-provider mode (legacy)
        llm = getattr(request.app.state, "llm", None)
        return {
            "mode": "single",
            "active_provider": getattr(llm, "provider", "offline") if llm else "offline",
            "providers": {},
        }
    return {"mode": "multi", **llm_router.stats()}
