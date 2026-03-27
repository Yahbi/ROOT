"""
Routes for Action Chain Engine — reactive pipelines connecting proactive
behaviors so scans trigger follow-up actions instead of being disconnected.
"""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/action-chains", tags=["action-chains"])


# ── Request Models ──────────────────────────────────────────────

class ChainCreateRequest(BaseModel):
    trigger_action: str = Field(min_length=1, max_length=100)
    follow_up_action: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    priority: int = Field(default=5, ge=0, le=20)
    cooldown_minutes: int = Field(default=5, ge=1, le=1440)
    enabled: bool = True


class ChainUpdateRequest(BaseModel):
    description: Optional[str] = Field(default=None, max_length=500)
    priority: Optional[int] = Field(default=None, ge=0, le=20)
    cooldown_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    enabled: Optional[bool] = None


# ── List Chains ──────────────────────────────────────────────────

@router.get("")
async def list_chains(request: Request):
    """List all registered action chains."""
    engine = getattr(request.app.state, "chain_engine", None)
    if not engine:
        raise HTTPException(503, "Action chain engine not available")

    chains = engine.get_chains()
    return {"chains": chains, "total": len(chains)}


# ── Recent Executions ────────────────────────────────────────────

@router.get("/executions")
async def list_executions(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
):
    """Recent chain executions."""
    engine = getattr(request.app.state, "chain_engine", None)
    if not engine:
        raise HTTPException(503, "Action chain engine not available")

    executions = engine.get_executions(limit=limit)
    return {"executions": executions, "total": len(executions)}


# ── Stats ────────────────────────────────────────────────────────

@router.get("/stats")
async def chain_stats(request: Request):
    """Execution statistics for the action chain engine."""
    engine = getattr(request.app.state, "chain_engine", None)
    if not engine:
        raise HTTPException(503, "Action chain engine not available")
    return engine.stats()


# ── Trigger Chain ────────────────────────────────────────────────

@router.post("/{chain_id}/trigger")
async def trigger_chain(chain_id: str, request: Request):
    """Manually fire a chain's follow-up action."""
    engine = getattr(request.app.state, "chain_engine", None)
    if not engine:
        raise HTTPException(503, "Action chain engine not available")

    # Verify the chain exists
    chains = engine.get_chains()
    chain = next((c for c in chains if c["id"] == chain_id), None)
    if not chain:
        raise HTTPException(404, f"Chain not found: {chain_id}")

    try:
        body = await request.json()
    except Exception:
        body = {}

    executions = await engine.evaluate_trigger(
        action_name=chain["trigger_action"],
        result=body,
    )

    return {
        "chain_id": chain_id,
        "triggered": len(executions) > 0,
        "executions": [
            {
                "id": e.id,
                "chain_id": e.chain_id,
                "success": e.success,
                "follow_up_result": e.follow_up_result[:200],
                "triggered_at": e.triggered_at,
                "completed_at": e.completed_at,
            }
            for e in executions
        ],
    }


# ── Create Chain ────────────────────────────────────────────────

@router.post("")
async def create_chain(req: ChainCreateRequest, request: Request):
    """Create a new action chain (user-defined, with always-true condition)."""
    import uuid
    from backend.core.action_chains import ActionChain

    engine = getattr(request.app.state, "chain_engine", None)
    if not engine:
        raise HTTPException(503, "Action chain engine not available")

    chain_id = f"custom_{uuid.uuid4().hex[:12]}"
    chain = ActionChain(
        id=chain_id,
        trigger_action=req.trigger_action,
        trigger_condition=lambda _result: True,
        follow_up_action=req.follow_up_action,
        follow_up_args={},
        description=req.description,
        enabled=req.enabled,
        priority=req.priority,
        cooldown_minutes=req.cooldown_minutes,
    )
    engine.register_chain(chain)
    return {
        "id": chain_id,
        "trigger_action": req.trigger_action,
        "follow_up_action": req.follow_up_action,
        "description": req.description,
    }


# ── Update Chain ────────────────────────────────────────────────

@router.patch("/{chain_id}")
async def update_chain(chain_id: str, req: ChainUpdateRequest, request: Request):
    """Update an existing action chain's metadata."""
    from dataclasses import replace as dc_replace

    engine = getattr(request.app.state, "chain_engine", None)
    if not engine:
        raise HTTPException(503, "Action chain engine not available")

    existing = engine._chains.get(chain_id)
    if not existing:
        raise HTTPException(404, f"Chain not found: {chain_id}")

    updates: dict[str, Any] = {}
    if req.description is not None:
        updates["description"] = req.description
    if req.priority is not None:
        updates["priority"] = req.priority
    if req.cooldown_minutes is not None:
        updates["cooldown_minutes"] = req.cooldown_minutes
    if req.enabled is not None:
        updates["enabled"] = req.enabled

    if updates:
        engine._chains[chain_id] = dc_replace(existing, **updates)

    return {"updated": True, "chain_id": chain_id}


# ── Delete Chain ────────────────────────────────────────────────

@router.delete("/{chain_id}")
async def delete_chain(chain_id: str, request: Request):
    """Remove an action chain."""
    engine = getattr(request.app.state, "chain_engine", None)
    if not engine:
        raise HTTPException(503, "Action chain engine not available")

    if chain_id not in engine._chains:
        raise HTTPException(404, f"Chain not found: {chain_id}")

    del engine._chains[chain_id]
    return {"deleted": True, "chain_id": chain_id}
