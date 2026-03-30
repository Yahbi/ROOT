"""Perpetual Intelligence + Agent Swarm routes."""
from __future__ import annotations
import logging
from fastapi import APIRouter, Request
from backend.models.response import APIResponse

logger = logging.getLogger("root.routes.perpetual")
router = APIRouter(prefix="/api/perpetual", tags=["Perpetual Intelligence"])

@router.get("/status")
async def perpetual_status(request: Request):
    """Get perpetual intelligence cycle metrics."""
    pi = getattr(request.app.state, 'perpetual_intelligence', None)
    swarm = getattr(request.app.state, 'agent_swarm', None)

    data = {
        "perpetual": pi.stats() if pi else {"error": "not initialized"},
        "swarm": swarm.stats() if swarm else {"error": "not initialized"},
    }
    return APIResponse.ok(data)

@router.get("/history")
async def perpetual_history(request: Request):
    """Get recent cycle results."""
    pi = getattr(request.app.state, 'perpetual_intelligence', None)
    if not pi:
        return APIResponse.ok([])
    history = getattr(pi, '_cycle_history', [])
    return APIResponse.ok(history[-20:])

@router.post("/trigger")
async def trigger_cycle(request: Request):
    """Manually trigger a perpetual intelligence cycle."""
    pi = getattr(request.app.state, 'perpetual_intelligence', None)
    if not pi:
        return APIResponse.ok({"error": "not initialized"})
    try:
        result = await pi.run_cycle()
        return APIResponse.ok(result)
    except Exception as e:
        return APIResponse.ok({"error": str(e)})

@router.get("/swarm/status")
async def swarm_status(request: Request):
    """Get agent swarm dispatch metrics."""
    swarm = getattr(request.app.state, 'agent_swarm', None)
    if not swarm:
        return APIResponse.ok({"error": "not initialized"})
    return APIResponse.ok(swarm.stats())

@router.get("/swarm/divisions")
async def swarm_divisions(request: Request):
    """Get per-division activity breakdown."""
    swarm = getattr(request.app.state, 'agent_swarm', None)
    if not swarm:
        return APIResponse.ok({})
    return APIResponse.ok(getattr(swarm, '_by_division', {}))

@router.get("/research")
async def research_findings(request: Request):
    """Get latest research findings from memory."""
    mem = getattr(request.app.state, 'memory', None)
    if not mem:
        return APIResponse.ok([])
    from backend.models.memory import MemoryQuery, MemoryType
    results = mem.search(MemoryQuery(
        query="research trading analysis strategy",
        memory_type=MemoryType.FACT,
        limit=20,
    ))
    return APIResponse.ok([
        {"content": m.content[:200], "tags": m.tags, "confidence": m.confidence,
         "created_at": m.created_at, "type": m.memory_type.value}
        for m in results
    ])
