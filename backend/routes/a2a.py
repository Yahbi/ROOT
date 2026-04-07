"""
A2A Protocol Routes — Agent-to-Agent discovery and task delegation.

Endpoints:
- GET  /.well-known/agent.json  — A2A discovery (top-level Agent Card)
- GET  /api/a2a/agents           — List all agent cards
- GET  /api/a2a/agents/{id}      — Single agent card
- POST /api/a2a                  — Receive an A2A task from an external agent
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.core.a2a_cards import generate_agent_card, generate_root_agent_card

logger = logging.getLogger("root.a2a")

router = APIRouter()


# ── Models ────────────────────────────────────────────────────────

class A2ATaskRequest(BaseModel):
    """Incoming A2A task from an external agent."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    skill_id: str = ""
    message: str = ""
    context: dict[str, Any] = Field(default_factory=dict)


class A2ATaskResponse(BaseModel):
    """Response to an A2A task."""
    id: str
    status: str  # "completed", "failed", "pending"
    result: str = ""
    error: str | None = None


# ── Discovery ─────────────────────────────────────────────────────

@router.get("/.well-known/agent.json", tags=["a2a"])
async def agent_discovery(request: Request):
    """A2A discovery endpoint — returns the top-level ROOT Agent Card."""
    registry = getattr(request.app.state, "registry", None)
    if not registry:
        return generate_root_agent_card([], base_url=str(request.base_url).rstrip("/"))

    agents = [
        {
            "id": a.id,
            "name": a.name,
            "description": a.description,
            "role": a.role,
        }
        for a in registry.list_agents()
    ]
    base_url = str(request.base_url).rstrip("/")
    return generate_root_agent_card(agents, base_url=base_url)


@router.get("/api/a2a/agents", tags=["a2a"])
async def list_agent_cards(request: Request):
    """List A2A Agent Cards for all ROOT agents."""
    registry = getattr(request.app.state, "registry", None)
    if not registry:
        return {"agents": []}

    base_url = str(request.base_url).rstrip("/")
    cards = []
    for agent in registry.list_agents():
        caps = [{"name": c.name, "description": c.description} for c in agent.capabilities]
        card = generate_agent_card(
            agent.id, agent.name, agent.description, agent.role,
            caps, base_url=base_url,
        )
        cards.append(card)
    return {"agents": cards, "total": len(cards)}


@router.get("/api/a2a/agents/{agent_id}", tags=["a2a"])
async def get_agent_card(agent_id: str, request: Request):
    """Get A2A Agent Card for a specific ROOT agent."""
    registry = getattr(request.app.state, "registry", None)
    if not registry:
        raise HTTPException(404, "Agent registry not available")

    agent = registry.get(agent_id)
    if not agent:
        raise HTTPException(404, f"Agent '{agent_id}' not found")

    base_url = str(request.base_url).rstrip("/")
    caps = [{"name": c.name, "description": c.description} for c in agent.capabilities]
    return generate_agent_card(
        agent.id, agent.name, agent.description, agent.role,
        caps, base_url=base_url,
    )


# ── Task Endpoint ─────────────────────────────────────────────────

@router.post("/api/a2a", tags=["a2a"], response_model=A2ATaskResponse)
async def receive_a2a_task(task: A2ATaskRequest, request: Request):
    """Receive a task from an external agent via A2A protocol.

    Routes the task through ROOT's brain or delegates to a specific agent.
    """
    brain = getattr(request.app.state, "brain", None)
    if not brain:
        return A2ATaskResponse(
            id=task.id,
            status="failed",
            error="ROOT brain not available",
        )

    try:
        # Route through brain (ASTRA decides which agent handles it)
        message = task.message or task.context.get("message", "")
        if not message:
            return A2ATaskResponse(
                id=task.id,
                status="failed",
                error="No message provided in task",
            )

        result = await brain.chat(message)
        logger.info("A2A task %s completed via brain", task.id)
        return A2ATaskResponse(
            id=task.id,
            status="completed",
            result=result.content if hasattr(result, "content") else str(result),
        )
    except Exception as e:
        logger.error("A2A task %s failed: %s", task.id, e)
        return A2ATaskResponse(
            id=task.id,
            status="failed",
            error=str(e),
        )
