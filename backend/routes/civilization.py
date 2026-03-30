"""API routes for the ASTRA-ROOT civilization systems."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

router = APIRouter(prefix="/api/civilization", tags=["civilization"])


# ── Agent Civilization ──────────────────────────────────────────

@router.get("/agents")
async def list_all_agents(request: Request):
    """List all agents (core + civilization)."""
    registry = request.app.state.registry
    agents = registry.list_agents()
    return {
        "total": len(agents),
        "core": len(registry.list_core_agents()),
        "divisions": registry.list_divisions(),
        "agents": [
            {"id": a.id, "name": a.name, "role": a.role, "tier": a.tier}
            for a in agents
        ],
    }


@router.get("/agents/divisions")
async def list_divisions(request: Request):
    """List all agent divisions with full agent data."""
    registry = request.app.state.registry
    divisions_data = {}
    for name in registry.list_divisions():
        agents = registry.list_division(name)
        divisions_data[name] = [
            {"id": a.id, "name": a.name, "role": a.role, "tier": a.tier,
             "description": getattr(a, "description", ""),
             "capabilities": [c.name for c in a.capabilities] if a.capabilities else []}
            for a in agents
        ]
    return {"divisions": divisions_data, "total_agents": registry.agent_count()}


@router.get("/agents/division/{name}")
async def get_division(name: str, request: Request):
    """Get agents in a specific division."""
    registry = request.app.state.registry
    agents = registry.list_division(name)
    if not agents:
        raise HTTPException(404, f"Division '{name}' not found")
    return {
        "division": name,
        "count": len(agents),
        "agents": [
            {"id": a.id, "name": a.name, "role": a.role, "description": a.description,
             "capabilities": [c.name for c in a.capabilities]}
            for a in agents
        ],
    }


# ── Experience Memory ──────────────────────────────────────────

class RecordExperienceRequest(BaseModel):
    experience_type: str
    domain: str
    title: str
    description: str
    outcome: Optional[str] = None
    confidence: float = 1.0
    tags: Optional[list[str]] = None


@router.post("/experience")
async def record_experience(body: RecordExperienceRequest, request: Request):
    """Record a new experience."""
    exp_mem = request.app.state.experience_memory
    exp = exp_mem.record_experience(
        experience_type=body.experience_type,
        domain=body.domain,
        title=body.title,
        description=body.description,
        outcome=body.outcome,
        confidence=body.confidence,
        tags=body.tags,
    )
    return {"id": exp.id, "type": exp.experience_type.value, "domain": exp.domain}


@router.get("/experience")
async def get_experiences(
    request: Request,
    domain: Optional[str] = None,
    experience_type: Optional[str] = None,
    limit: int = 20,
):
    """Query experiences."""
    exp_mem = request.app.state.experience_memory
    exps = exp_mem.get_experiences(
        domain=domain, experience_type=experience_type, limit=limit,
    )
    return {
        "count": len(exps),
        "experiences": [
            {"id": e.id, "type": e.experience_type.value, "domain": e.domain,
             "title": e.title, "confidence": e.confidence, "times_applied": e.times_applied}
            for e in exps
        ],
    }


@router.get("/experience/stats")
async def experience_stats(request: Request):
    """Experience memory statistics."""
    return request.app.state.experience_memory.stats()


# ── Experiment Lab ─────────────────────────────────────────────

class ProposeExperimentRequest(BaseModel):
    title: str
    hypothesis: str
    category: str
    design: str = ""
    success_criteria: str = ""
    confidence: float = 0.5


@router.post("/experiments")
async def propose_experiment(body: ProposeExperimentRequest, request: Request):
    """Propose a new experiment."""
    lab = request.app.state.experiment_lab
    exp = lab.propose(
        title=body.title,
        hypothesis=body.hypothesis,
        category=body.category,
        design=body.design,
        success_criteria=body.success_criteria,
        confidence=body.confidence,
    )
    return {"id": exp.id, "title": exp.title, "status": exp.status.value}


@router.get("/experiments")
async def list_experiments(
    request: Request,
    status: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = 20,
):
    """List experiments with optional filters."""
    lab = request.app.state.experiment_lab
    if category:
        exps = lab.get_by_category(category, limit=limit)
    elif status == "proposed":
        exps = lab.get_proposed(limit=limit)
    elif status == "running":
        exps = lab.get_running(limit=limit)
    elif status == "completed":
        exps = lab.get_completed(limit=limit)
    elif status == "scaled":
        exps = lab.get_scaled(limit=limit)
    else:
        exps = lab.get_proposed(limit=limit)
    return {
        "count": len(exps),
        "experiments": [
            {"id": e.id, "title": e.title, "category": e.category.value,
             "status": e.status.value, "confidence": e.confidence}
            for e in exps
        ],
    }


@router.post("/experiments/{experiment_id}/approve")
async def approve_experiment(experiment_id: str, request: Request):
    """Yohan approves an experiment."""
    lab = request.app.state.experiment_lab
    if not lab.approve(experiment_id):
        raise HTTPException(400, "Experiment not found or not pending approval")
    return {"status": "approved", "id": experiment_id}


@router.post("/experiments/{experiment_id}/reject")
async def reject_experiment(experiment_id: str, request: Request):
    """Yohan rejects an experiment."""
    lab = request.app.state.experiment_lab
    if not lab.reject(experiment_id):
        raise HTTPException(400, "Experiment not found or not pending approval")
    return {"status": "rejected", "id": experiment_id}


@router.post("/experiments/{experiment_id}/start")
async def start_experiment(experiment_id: str, request: Request):
    """Start a proposed or approved experiment."""
    lab = request.app.state.experiment_lab
    if not lab.start_experiment(experiment_id):
        raise HTTPException(400, "Experiment not found or not in proposed/approved state")
    return {"status": "running", "id": experiment_id}


@router.get("/experiments/stats")
async def experiment_stats(request: Request):
    """Experiment lab statistics."""
    return request.app.state.experiment_lab.stats()


# ── Self-Writing Code ──────────────────────────────────────────

class CodeProposalRequest(BaseModel):
    title: str
    description: str
    file_path: str
    inefficiency: str
    proposed_change: str
    scope: str = "minor"


@router.post("/code-proposals")
async def propose_code_change(body: CodeProposalRequest, request: Request):
    """Submit a code improvement proposal."""
    swc = request.app.state.self_writing_code
    proposal = swc.propose_improvement(
        title=body.title,
        description=body.description,
        file_path=body.file_path,
        inefficiency=body.inefficiency,
        proposed_change=body.proposed_change,
        scope=body.scope,
    )
    return {"id": proposal.id, "title": proposal.title, "scope": proposal.scope.value}


@router.get("/code-proposals")
async def list_code_proposals(request: Request, status: Optional[str] = None, limit: int = 20):
    """List code proposals."""
    swc = request.app.state.self_writing_code
    if status == "pending_approval":
        proposals = swc.get_pending_approval(limit=limit)
    elif status == "approved":
        proposals = swc.get_approved(limit=limit)
    elif status == "deployed":
        proposals = swc.get_deployed(limit=limit)
    else:
        proposals = swc.get_history(limit=limit)
    return {
        "count": len(proposals),
        "proposals": [
            {"id": p.id, "title": p.title, "scope": p.scope.value,
             "status": p.status.value, "file": p.file_path,
             "description": p.description, "proposed_change": p.proposed_change,
             "agent_id": p.agent_id, "created_at": p.created_at}
            for p in proposals
        ],
    }


@router.post("/code-proposals/{proposal_id}/approve")
async def approve_code_proposal(proposal_id: str, request: Request):
    """Approve a pending code proposal (Yohan approval)."""
    swc = request.app.state.self_writing_code
    if not swc.approve(proposal_id):
        raise HTTPException(400, "Proposal not found or not pending approval")
    return {"status": "approved", "id": proposal_id}


@router.post("/code-proposals/{proposal_id}/reject")
async def reject_code_proposal(proposal_id: str, request: Request):
    """Reject a pending code proposal."""
    swc = request.app.state.self_writing_code
    if not swc.reject(proposal_id):
        raise HTTPException(400, "Proposal not found or not pending approval")
    return {"status": "rejected", "id": proposal_id}


@router.get("/code-proposals/stats")
async def code_proposal_stats(request: Request):
    """Code proposal statistics."""
    return request.app.state.self_writing_code.stats()


# ── Revenue Engine ─────────────────────────────────────────────

class AddProductRequest(BaseModel):
    name: str
    stream: str
    description: str = ""
    monthly_cost: float = 0.0


@router.post("/revenue/products")
async def add_product(body: AddProductRequest, request: Request):
    """Add a new revenue product."""
    rev = request.app.state.revenue_engine
    product = rev.add_product(
        name=body.name, stream=body.stream,
        description=body.description, monthly_cost=body.monthly_cost,
    )
    return {"id": product.id, "name": product.name, "stream": product.stream.value}


@router.get("/revenue/products")
async def list_products(
    request: Request,
    stream: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
):
    """List revenue products."""
    rev = request.app.state.revenue_engine
    products = rev.get_products(stream=stream, status=status, limit=limit)
    return {
        "count": len(products),
        "products": [
            {"id": p.id, "name": p.name, "stream": p.stream.value,
             "status": p.status.value, "revenue": p.monthly_revenue,
             "cost": p.monthly_cost}
            for p in products
        ],
    }


@router.get("/revenue/snapshot")
async def financial_snapshot(request: Request):
    """Get current financial snapshot."""
    rev = request.app.state.revenue_engine
    snap = rev.get_financial_snapshot()
    return {
        "total_revenue": snap.total_revenue,
        "total_cost": snap.total_cost,
        "profit": snap.profit,
        "by_stream": snap.by_stream,
        "emergency_mode": snap.emergency_mode,
        "survival_budget": 400.0,
    }


@router.get("/revenue/stats")
async def revenue_stats(request: Request):
    """Revenue engine statistics."""
    return request.app.state.revenue_engine.stats()


# ── System Overview ────────────────────────────────────────────

@router.get("/status")
async def civilization_status(request: Request):
    """Full civilization status overview."""
    registry = request.app.state.registry
    exp_mem = request.app.state.experience_memory
    lab = request.app.state.experiment_lab
    swc = request.app.state.self_writing_code
    rev = request.app.state.revenue_engine

    return {
        "civilization": {
            "total_agents": registry.agent_count(),
            "core_agents": len(registry.list_core_agents()),
            "divisions": registry.list_divisions(),
        },
        "experience_memory": exp_mem.stats(),
        "experiment_lab": lab.stats(),
        "self_writing_code": swc.stats(),
        "revenue": rev.stats(),
    }
