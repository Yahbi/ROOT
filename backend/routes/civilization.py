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


@router.get("/experience/search")
async def search_experiences_scored(
    request: Request,
    q: str = "",
    domain: Optional[str] = None,
    limit: int = 10,
    age_penalty: bool = True,
):
    """Relevance-scored experience search."""
    exp_mem = request.app.state.experience_memory
    results = exp_mem.search_experiences_scored(
        query=q, limit=limit, domain=domain, age_penalty=age_penalty,
    )
    return {
        "count": len(results),
        "results": [
            {
                "score": r.score,
                "id": r.experience.id,
                "type": r.experience.experience_type.value,
                "domain": r.experience.domain,
                "title": r.experience.title,
                "confidence": r.experience.confidence,
                "times_applied": r.experience.times_applied,
            }
            for r in results
        ],
    }


@router.get("/experience/patterns")
async def detect_patterns(
    request: Request,
    domain: Optional[str] = None,
    min_occurrences: int = 2,
    window_days: int = 180,
):
    """Detect recurring success/failure patterns."""
    exp_mem = request.app.state.experience_memory
    patterns = exp_mem.detect_patterns(
        domain=domain, min_occurrences=min_occurrences, window_days=window_days,
    )
    return {
        "count": len(patterns),
        "patterns": [
            {
                "pattern_id": p.pattern_id,
                "pattern_type": p.pattern_type,
                "domain": p.domain,
                "title": p.title,
                "description": p.description,
                "occurrence_count": p.occurrence_count,
                "avg_confidence": p.avg_confidence,
                "keywords": p.keywords,
                "example_ids": p.example_ids,
            }
            for p in patterns
        ],
    }


@router.get("/experience/clusters")
async def cluster_experiences(
    request: Request,
    domain: Optional[str] = None,
    max_clusters: int = 10,
):
    """Cluster experiences by topic/domain similarity."""
    exp_mem = request.app.state.experience_memory
    clusters = exp_mem.cluster_experiences(domain=domain, max_clusters=max_clusters)
    return {
        "count": len(clusters),
        "clusters": [
            {
                "cluster_id": c.cluster_id,
                "label": c.label,
                "domain": c.domain,
                "size": c.size,
                "dominant_type": c.dominant_type,
                "avg_confidence": c.avg_confidence,
                "keywords": c.keywords,
                "experience_ids": c.experience_ids,
            }
            for c in clusters
        ],
    }


@router.get("/experience/wisdom")
async def extract_wisdom(
    request: Request,
    domain: Optional[str] = None,
    min_support: int = 2,
    min_confidence: float = 0.5,
):
    """Synthesize experiences into actionable wisdom."""
    exp_mem = request.app.state.experience_memory
    wisdoms = exp_mem.extract_wisdom(
        domain=domain, min_support=min_support, min_confidence=min_confidence,
    )
    return {
        "count": len(wisdoms),
        "wisdom": [
            {
                "wisdom_id": w.wisdom_id,
                "domain": w.domain,
                "insight": w.insight,
                "source_types": w.source_types,
                "supporting_count": w.supporting_count,
                "confidence": w.confidence,
                "keywords": w.keywords,
                "cross_domain_applicable": w.cross_domain_applicable,
            }
            for w in wisdoms
        ],
    }


@router.post("/experience/age-decay")
async def apply_age_decay(
    request: Request,
    half_life_days: int = 180,
    min_confidence: float = 0.1,
    dry_run: bool = False,
):
    """Apply time-based confidence decay to old experiences."""
    exp_mem = request.app.state.experience_memory
    return exp_mem.apply_age_decay(
        half_life_days=half_life_days, min_confidence=min_confidence, dry_run=dry_run,
    )


@router.post("/experience/transfer")
async def transfer_lesson(
    request: Request,
    source_domain: str = "",
    target_domain: str = "",
    min_confidence: float = 0.6,
    max_transfer: int = 5,
):
    """Transfer lessons from one domain to another (cross-domain learning)."""
    if not source_domain or not target_domain:
        from fastapi import HTTPException
        raise HTTPException(400, "source_domain and target_domain are required")
    exp_mem = request.app.state.experience_memory
    transferred = exp_mem.transfer_lesson(
        source_domain=source_domain,
        target_domain=target_domain,
        min_confidence=min_confidence,
        max_transfer=max_transfer,
    )
    return {
        "transferred": len(transferred),
        "source_domain": source_domain,
        "target_domain": target_domain,
        "experiences": [
            {"id": e.id, "title": e.title, "confidence": e.confidence, "tags": e.tags}
            for e in transferred
        ],
    }


@router.get("/experience/domain-connections")
async def get_domain_connections(request: Request):
    """Get cross-domain learning connection graph."""
    exp_mem = request.app.state.experience_memory
    connections = exp_mem.get_domain_connections()
    return {"connections": connections}


@router.get("/experience/visualization")
async def get_visualization_data(request: Request):
    """Get aggregated visualization data for frontend charts."""
    exp_mem = request.app.state.experience_memory
    return exp_mem.get_visualization_data()


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
