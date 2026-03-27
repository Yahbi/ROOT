"""Routes for autonomous systems — collaboration, approval, proactive, bus."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/autonomous", tags=["autonomous"])


# ── Request models ────────────────────────────────────────────

class DelegateRequest(BaseModel):
    from_agent: str
    to_agent: str
    task: str

class PipelineRequest(BaseModel):
    initiator: str = "yohan"
    goal: str
    steps: list[dict]  # [{"agent_id": "...", "task": "..."}, ...]

class FanoutRequest(BaseModel):
    initiator: str = "yohan"
    goal: str
    agents: list[str]
    task: str
    merge_prompt: Optional[str] = None

class CouncilRequest(BaseModel):
    question: str
    agents: list[str]

class ApprovalAction(BaseModel):
    request_id: str


# ── Collaboration routes ──────────────────────────────────────

@router.post("/delegate")
async def collab_delegate(req: DelegateRequest, request: Request):
    """One agent delegates a task to another."""
    collab = request.app.state.collab
    result = await collab.delegate(req.from_agent, req.to_agent, req.task)
    return {
        "workflow_id": result.id,
        "pattern": result.pattern.value,
        "status": result.status.value,
        "result": result.final_result,
        "steps": [
            {"agent": s.agent_id, "status": s.status, "result": (s.result or "")[:500]}
            for s in result.steps
        ],
    }


@router.post("/pipeline")
async def collab_pipeline(req: PipelineRequest, request: Request):
    """Chain multiple agents in sequence."""
    collab = request.app.state.collab
    result = await collab.pipeline(req.initiator, req.goal, req.steps)
    return {
        "workflow_id": result.id,
        "pattern": result.pattern.value,
        "status": result.status.value,
        "result": result.final_result,
        "steps": [
            {"agent": s.agent_id, "status": s.status, "result": (s.result or "")[:500]}
            for s in result.steps
        ],
    }


@router.post("/fanout")
async def collab_fanout(req: FanoutRequest, request: Request):
    """Send task to multiple agents in parallel, merge results."""
    collab = request.app.state.collab
    result = await collab.fanout(
        req.initiator, req.goal, req.agents, req.task, req.merge_prompt,
    )
    return {
        "workflow_id": result.id,
        "pattern": result.pattern.value,
        "status": result.status.value,
        "result": result.final_result,
        "steps": [
            {"agent": s.agent_id, "status": s.status, "result": (s.result or "")[:500]}
            for s in result.steps
        ],
    }


@router.post("/council")
async def collab_council(req: CouncilRequest, request: Request):
    """Multiple agents discuss and reach consensus."""
    collab = request.app.state.collab
    result = await collab.council("yohan", req.question, req.agents)
    return {
        "workflow_id": result.id,
        "pattern": result.pattern.value,
        "status": result.status.value,
        "result": result.final_result,
        "steps": [
            {"agent": s.agent_id, "status": s.status, "result": (s.result or "")[:500]}
            for s in result.steps
        ],
    }


@router.get("/collab/history")
async def collab_history(request: Request, limit: int = Query(default=20, ge=1, le=500)):
    """Get recent collaboration workflows."""
    collab = request.app.state.collab
    workflows = collab.get_history(limit)
    return [
        {
            "id": w.id,
            "pattern": w.pattern.value,
            "initiator": w.initiator,
            "goal": w.goal,
            "status": w.status.value,
            "steps": len(w.steps),
            "created_at": w.created_at,
            "completed_at": w.completed_at,
        }
        for w in workflows
    ]


@router.get("/collab/stats")
async def collab_stats(request: Request):
    return request.app.state.collab.stats()


# ── Approval routes ───────────────────────────────────────────

@router.get("/approvals/pending")
async def pending_approvals(request: Request):
    """Get all pending approval requests."""
    approval = request.app.state.approval
    pending = approval.get_pending()
    return [
        {
            "id": r.id,
            "agent": r.agent_id,
            "action": r.action,
            "description": r.description,
            "risk_level": r.risk_level.value,
            "created_at": r.created_at,
        }
        for r in pending
    ]


@router.post("/approvals/approve")
async def approve_request(req: ApprovalAction, request: Request):
    """Approve a pending request."""
    approval = request.app.state.approval
    result = approval.approve(req.request_id)
    if not result:
        raise HTTPException(status_code=404, detail="Request not found or already resolved")
    return {"status": result.status.value, "id": result.id}


@router.post("/approvals/reject")
async def reject_request(req: ApprovalAction, request: Request):
    """Reject a pending request."""
    approval = request.app.state.approval
    result = approval.reject(req.request_id)
    if not result:
        raise HTTPException(status_code=404, detail="Request not found or already resolved")
    return {"status": result.status.value, "id": result.id}


@router.get("/approvals/history")
async def approval_history(request: Request, limit: int = Query(default=50, ge=1, le=500)):
    approval = request.app.state.approval
    history = approval.get_history(limit)
    return [
        {
            "id": r.id,
            "agent": r.agent_id,
            "action": r.action,
            "risk_level": r.risk_level.value,
            "status": r.status.value,
            "resolved_at": r.resolved_at,
            "resolver": r.resolver,
        }
        for r in history
    ]


@router.get("/approvals/stats")
async def approval_stats(request: Request):
    return request.app.state.approval.stats()


# ── Proactive engine routes ───────────────────────────────────

@router.get("/proactive/actions")
async def proactive_actions(request: Request):
    """List all proactive behaviors."""
    proactive = request.app.state.proactive
    return await proactive.get_actions()


@router.post("/proactive/trigger/{action_name}")
async def trigger_proactive(action_name: str, request: Request):
    """Manually trigger a proactive action."""
    proactive = request.app.state.proactive
    result = await proactive.trigger(action_name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Action '{action_name}' not found")
    return {"action": action_name, "result": result}


@router.get("/proactive/stats")
async def proactive_stats(request: Request):
    return await request.app.state.proactive.stats()


# ── Autonomous loop routes ────────────────────────────────────

@router.post("/loop/cycle")
async def run_cycle(request: Request):
    """Manually trigger an autonomous improvement cycle."""
    auto_loop = request.app.state.auto_loop
    result = await auto_loop.run_cycle()
    return result


@router.get("/loop/experiments")
async def get_experiments(request: Request, limit: int = Query(default=20, ge=1, le=500)):
    """Get recent experiments."""
    auto_loop = request.app.state.auto_loop
    return auto_loop.get_experiments(limit)


@router.get("/loop/stats")
async def loop_stats(request: Request):
    return request.app.state.auto_loop.stats()


# ── Message bus routes ────────────────────────────────────────

@router.get("/bus/history")
async def bus_history(
    request: Request,
    topic: Optional[str] = None,
    sender: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
):
    """Get recent bus messages."""
    bus = request.app.state.bus
    messages = bus.get_history(topic, sender, limit)
    return [
        {
            "id": m.id,
            "topic": m.topic,
            "sender": m.sender,
            "payload": m.payload,
            "priority": m.priority.value,
            "timestamp": m.timestamp,
        }
        for m in messages
    ]


@router.get("/bus/stats")
async def bus_stats(request: Request):
    return request.app.state.bus.stats()


# ── Combined status ───────────────────────────────────────────

@router.get("/status")
async def autonomous_status(request: Request):
    """Full autonomous system status."""
    return {
        "collab": request.app.state.collab.stats(),
        "approval": request.app.state.approval.stats(),
        "proactive": await request.app.state.proactive.stats(),
        "autonomous_loop": request.app.state.auto_loop.stats(),
        "continuous_learning": request.app.state.continuous_learning.stats(),
        "message_bus": request.app.state.bus.stats(),
    }


@router.get("/learning/stats")
async def learning_stats(request: Request):
    """Continuous learning engine stats."""
    return request.app.state.continuous_learning.stats()


@router.get("/learning/records")
async def learning_records(request: Request, limit: int = 20):
    """Recent learning records from all agents."""
    return request.app.state.continuous_learning.get_recent_records(limit=limit)


@router.get("/learning/coverage")
async def learning_coverage(request: Request):
    """Per-division learning coverage."""
    return request.app.state.continuous_learning.get_division_coverage()


@router.get("/learning/agent/{agent_id}")
async def learning_agent_stats(request: Request, agent_id: str):
    """Learning stats for a specific agent."""
    stats = request.app.state.continuous_learning.get_agent_stats(agent_id)
    if not stats:
        return {"agent_id": agent_id, "message": "No learning data yet"}
    return {"agent_id": agent_id, **stats}


@router.post("/learning/trigger")
async def trigger_learning_cycle(request: Request):
    """Manually trigger a learning cycle."""
    result = await request.app.state.continuous_learning.run_cycle()
    return result
