"""Custom agent registration routes — create, update, and remove agents at runtime."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/agents/custom", tags=["agents-custom"])


# ── Request Models ──────────────────────────────────────────────

class CreateAgentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    tier: int = Field(default=2, ge=1, le=2)
    capabilities: list[dict[str, str]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdateAgentRequest(BaseModel):
    name: Optional[str] = Field(default=None, max_length=100)
    role: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1000)
    tier: Optional[int] = Field(default=None, ge=1, le=2)
    metadata: Optional[dict[str, Any]] = None


# ── Create ──────────────────────────────────────────────────────

@router.post("")
async def create_custom_agent(req: CreateAgentRequest, request: Request):
    """Register a new custom agent at runtime."""
    import uuid
    from backend.models.agent import AgentCapability, AgentProfile

    registry = request.app.state.registry
    agent_id = f"custom_{uuid.uuid4().hex[:8]}"

    caps = [
        AgentCapability(
            name=c.get("name", "general"),
            description=c.get("description", ""),
        )
        for c in req.capabilities
    ]

    agent = AgentProfile(
        id=agent_id,
        name=req.name,
        role=req.role,
        description=req.description,
        tier=req.tier,
        capabilities=caps,
        connector_type="internal",
        metadata={**req.metadata, "custom": True},
    )
    registry.register(agent)
    return {
        "id": agent_id,
        "name": req.name,
        "role": req.role,
        "tier": req.tier,
        "capabilities": len(caps),
    }


# ── Update ──────────────────────────────────────────────────────

@router.patch("/{agent_id}")
async def update_custom_agent(
    agent_id: str, req: UpdateAgentRequest, request: Request,
):
    """Update a custom agent's profile (immutable copy-on-write)."""
    registry = request.app.state.registry
    existing = registry.get(agent_id)
    if not existing:
        raise HTTPException(404, "Agent not found")
    if not existing.metadata.get("custom"):
        raise HTTPException(403, "Cannot modify built-in agents")

    updates: dict[str, Any] = {}
    if req.name is not None:
        updates["name"] = req.name
    if req.role is not None:
        updates["role"] = req.role
    if req.description is not None:
        updates["description"] = req.description
    if req.tier is not None:
        updates["tier"] = req.tier
    if req.metadata is not None:
        updates["metadata"] = {**existing.metadata, **req.metadata, "custom": True}

    if updates:
        updated = existing.model_copy(update=updates)
        registry._agents[agent_id] = updated

    return {"updated": True, "agent_id": agent_id}


# ── Delete ──────────────────────────────────────────────────────

@router.delete("/{agent_id}")
async def delete_custom_agent(agent_id: str, request: Request):
    """Remove a custom agent from the registry."""
    registry = request.app.state.registry
    existing = registry.get(agent_id)
    if not existing:
        raise HTTPException(404, "Agent not found")
    if not existing.metadata.get("custom"):
        raise HTTPException(403, "Cannot delete built-in agents")
    registry.unregister(agent_id)
    return {"deleted": True, "agent_id": agent_id}


# ── List Custom Only ────────────────────────────────────────────

@router.get("")
async def list_custom_agents(request: Request):
    """List only custom (user-created) agents."""
    registry = request.app.state.registry
    custom = [
        a.model_dump()
        for a in registry.list_agents()
        if a.metadata.get("custom")
    ]
    return {"agents": custom, "total": len(custom)}
