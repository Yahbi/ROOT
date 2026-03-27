"""
Routes for ROOT v0.8.0 autonomy systems:
- Task Queue (persistent tasks)
- Goals (autonomous goal management)
- Triggers (event-driven automation)
- Digests (daily/weekly reports)
- User Patterns (behavior learning)
- Escalation (confidence-gated decisions)
- Directives (autonomous strategic decisions)
- Agent Network (inter-agent knowledge sharing)
"""

from __future__ import annotations

import logging

logger = logging.getLogger("root.routes.autonomy")

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Any, Optional

router = APIRouter(prefix="/api/autonomy", tags=["autonomy"])


# ── Request Models ───────────────────────────────────────────────

class EnqueueRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=5000)
    priority: int = Field(default=5, ge=1, le=9)
    source: str = Field(default="user", max_length=50)
    schedule_cron: Optional[str] = None
    max_retries: int = Field(default=2, ge=0, le=10)


class GoalRequest(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=2000)
    priority: int = Field(default=5, ge=1, le=9)
    category: str = Field(default="general", max_length=50)
    milestones: list[str] = Field(default_factory=list)
    deadline: Optional[str] = None


class ProgressRequest(BaseModel):
    progress: float = Field(ge=0.0, le=1.0)
    note: str = Field(default="", max_length=500)


class TriggerRuleRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    trigger_type: str = Field(pattern=r"^(file_watch|schedule|webhook|condition)$")
    config: dict[str, Any] = Field(default_factory=dict)
    action_type: str = Field(pattern=r"^(delegate|enqueue|proactive|custom)$")
    action_config: dict[str, Any] = Field(default_factory=dict)


class DirectiveRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    rationale: str = Field(default="", max_length=500)
    priority: int = Field(default=5, ge=1, le=9)
    category: str = Field(default="general", pattern=r"^(trading|research|learning|automation|product|health|general)$")
    assigned_agents: list[str] = Field(default_factory=list)
    collab_pattern: str = Field(default="delegate", pattern=r"^(delegate|pipeline|fanout|council)$")
    task_description: str = Field(default="", max_length=1000)
    ttl_minutes: int = Field(default=120, ge=1, le=1440)


# ── Task Queue ───────────────────────────────────────────────────

@router.post("/queue")
async def enqueue_task(req: EnqueueRequest, request: Request):
    """Add a task to the persistent queue."""
    tq = getattr(request.app.state, "task_queue", None)
    if not tq:
        raise HTTPException(503, "Task queue not available")
    task = tq.enqueue(
        goal=req.goal, priority=req.priority, source=req.source,
        schedule_cron=req.schedule_cron, max_retries=req.max_retries,
    )
    return {"id": task.id, "status": task.status, "goal": task.goal}


@router.get("/queue")
async def list_queue(
    request: Request,
    status: Optional[str] = Query(None, pattern=r"^(pending|running|completed|failed|cancelled|scheduled)$"),
    limit: int = Query(20, ge=1, le=100),
):
    tq = getattr(request.app.state, "task_queue", None)
    if not tq:
        raise HTTPException(503, "Task queue not available")

    if status == "pending":
        tasks = tq.get_pending(limit)
    elif status == "running":
        tasks = tq.get_active()
    else:
        tasks = tq.get_recent(limit)

    return {
        "tasks": [
            {"id": t.id, "goal": t.goal[:200], "priority": t.priority,
             "status": t.status, "source": t.source, "created_at": t.created_at}
            for t in tasks
        ],
        "stats": tq.stats(),
    }


@router.post("/queue/{task_id}/cancel")
async def cancel_queued_task(task_id: str, request: Request):
    tq = getattr(request.app.state, "task_queue", None)
    if not tq:
        raise HTTPException(503, "Task queue not available")
    if not tq.cancel(task_id):
        raise HTTPException(404, "Task not found or already completed")
    return {"cancelled": True, "task_id": task_id}


@router.get("/queue/stats")
async def queue_stats(request: Request):
    tq = getattr(request.app.state, "task_queue", None)
    if not tq:
        raise HTTPException(503, "Task queue not available")
    return tq.stats()


# ── Goals ────────────────────────────────────────────────────────

@router.post("/goals")
async def create_goal(req: GoalRequest, request: Request):
    ge = getattr(request.app.state, "goal_engine", None)
    if not ge:
        raise HTTPException(503, "Goal engine not available")
    goal = ge.add_goal(
        title=req.title, description=req.description,
        priority=req.priority, category=req.category,
        milestones=req.milestones, deadline=req.deadline,
    )
    return {"id": goal.id, "title": goal.title, "status": goal.status}


@router.get("/goals")
async def list_goals(
    request: Request,
    category: Optional[str] = None,
    limit: int = Query(20, ge=1, le=100),
):
    ge = getattr(request.app.state, "goal_engine", None)
    if not ge:
        raise HTTPException(503, "Goal engine not available")

    if category:
        goals = ge.get_goals_by_category(category)
    else:
        goals = ge.get_active_goals(limit)

    return {
        "goals": [
            {"id": g.id, "title": g.title, "priority": g.priority,
             "status": g.status, "progress": g.progress,
             "category": g.category, "created_at": g.created_at}
            for g in goals
        ],
        "stats": ge.stats(),
    }


@router.get("/goals/{goal_id}")
async def get_goal(goal_id: str, request: Request):
    ge = getattr(request.app.state, "goal_engine", None)
    if not ge:
        raise HTTPException(503, "Goal engine not available")
    goal = ge.get_goal(goal_id)
    if not goal:
        raise HTTPException(404, "Goal not found")
    events = ge.get_goal_events(goal_id)
    return {
        "id": goal.id, "title": goal.title, "description": goal.description,
        "priority": goal.priority, "status": goal.status,
        "progress": goal.progress, "category": goal.category,
        "milestones": list(goal.milestones),
        "completed_milestones": list(goal.completed_milestones),
        "tasks_generated": goal.tasks_generated,
        "tasks_completed": goal.tasks_completed,
        "events": events,
    }


@router.post("/goals/{goal_id}/progress")
async def update_goal_progress(goal_id: str, req: ProgressRequest, request: Request):
    ge = getattr(request.app.state, "goal_engine", None)
    if not ge:
        raise HTTPException(503, "Goal engine not available")
    goal = ge.update_progress(goal_id, req.progress, req.note)
    if not goal:
        raise HTTPException(404, "Goal not found")
    return {"id": goal.id, "progress": goal.progress, "status": goal.status}


@router.post("/goals/{goal_id}/decompose")
async def decompose_goal(goal_id: str, request: Request):
    ge = getattr(request.app.state, "goal_engine", None)
    if not ge:
        raise HTTPException(503, "Goal engine not available")
    task_ids = await ge.decompose_goal(goal_id)
    return {"goal_id": goal_id, "tasks_created": len(task_ids), "task_ids": task_ids}


@router.post("/goals/{goal_id}/pause")
async def pause_goal(goal_id: str, request: Request):
    ge = getattr(request.app.state, "goal_engine", None)
    if not ge:
        raise HTTPException(503, "Goal engine not available")
    if not ge.pause_goal(goal_id):
        raise HTTPException(404, "Goal not found or not active")
    return {"paused": True}


@router.post("/goals/{goal_id}/resume")
async def resume_goal(goal_id: str, request: Request):
    ge = getattr(request.app.state, "goal_engine", None)
    if not ge:
        raise HTTPException(503, "Goal engine not available")
    if not ge.resume_goal(goal_id):
        raise HTTPException(404, "Goal not found or not paused")
    return {"resumed": True}


# ── Triggers ─────────────────────────────────────────────────────

@router.get("/triggers")
async def list_triggers(request: Request):
    te = getattr(request.app.state, "triggers", None)
    if not te:
        raise HTTPException(503, "Trigger engine not available")
    return {"rules": te.get_rules(), "stats": te.stats()}


@router.post("/triggers/{rule_id}/enable")
async def enable_trigger(rule_id: str, request: Request):
    te = getattr(request.app.state, "triggers", None)
    if not te:
        raise HTTPException(503, "Trigger engine not available")
    if not te.enable_rule(rule_id):
        raise HTTPException(404, "Trigger rule not found")
    return {"enabled": True}


@router.post("/triggers/{rule_id}/disable")
async def disable_trigger(rule_id: str, request: Request):
    te = getattr(request.app.state, "triggers", None)
    if not te:
        raise HTTPException(503, "Trigger engine not available")
    if not te.disable_rule(rule_id):
        raise HTTPException(404, "Trigger rule not found")
    return {"disabled": True}


@router.post("/triggers")
async def create_trigger(req: TriggerRuleRequest, request: Request):
    """Create a new trigger rule."""
    import uuid
    from backend.core.trigger_engine import TriggerRule
    te = getattr(request.app.state, "triggers", None)
    if not te:
        raise HTTPException(503, "Trigger engine not available")
    rule_id = f"trigger_{uuid.uuid4().hex[:12]}"
    rule = TriggerRule(
        id=rule_id,
        name=req.name,
        trigger_type=req.trigger_type,
        config=req.config,
        action_type=req.action_type,
        action_config=req.action_config,
    )
    te.add_rule(rule)
    return {"id": rule_id, "name": req.name, "trigger_type": req.trigger_type}


@router.delete("/triggers/{rule_id}")
async def delete_trigger(rule_id: str, request: Request):
    """Delete a trigger rule."""
    te = getattr(request.app.state, "triggers", None)
    if not te:
        raise HTTPException(503, "Trigger engine not available")
    if not te.remove_rule(rule_id):
        raise HTTPException(404, "Trigger rule not found")
    return {"deleted": True, "rule_id": rule_id}


@router.post("/triggers/webhook/{trigger_id}")
async def fire_webhook(trigger_id: str, request: Request):
    """External webhook endpoint to fire a trigger."""
    te = getattr(request.app.state, "triggers", None)
    if not te:
        raise HTTPException(503, "Trigger engine not available")
    try:
        body = await request.json()
    except Exception:
        body = {}
        logger.debug("Invalid JSON body, using empty dict")
    fired = await te.fire_webhook(trigger_id, body)
    if not fired:
        raise HTTPException(404, "Webhook trigger not found or disabled")
    return {"fired": True, "trigger_id": trigger_id}


# ── Digests ──────────────────────────────────────────────────────

@router.get("/digests")
async def list_digests(
    request: Request,
    digest_type: Optional[str] = Query(None, pattern=r"^(daily|weekly|alert|portfolio|custom)$"),
    limit: int = Query(10, ge=1, le=50),
):
    de = getattr(request.app.state, "digest", None)
    if not de:
        raise HTTPException(503, "Digest engine not available")
    digests = de.get_digests(digest_type, limit)
    return {
        "digests": [
            {"id": d.id, "type": d.digest_type, "title": d.title,
             "highlights": list(d.highlights), "created_at": d.created_at}
            for d in digests
        ],
        "stats": de.stats(),
    }


@router.get("/digests/latest")
async def latest_digest(
    request: Request,
    digest_type: str = Query("daily", pattern=r"^(daily|weekly|alert)$"),
):
    de = getattr(request.app.state, "digest", None)
    if not de:
        raise HTTPException(503, "Digest engine not available")
    digest = de.get_latest(digest_type)
    if not digest:
        raise HTTPException(404, f"No {digest_type} digest found")
    return {
        "id": digest.id, "type": digest.digest_type,
        "title": digest.title, "content": digest.content,
        "highlights": list(digest.highlights),
        "metrics": digest.metrics,
        "period_start": digest.period_start,
        "period_end": digest.period_end,
    }


@router.post("/digests/generate")
async def generate_digest(
    request: Request,
    digest_type: str = Query("daily", pattern=r"^(daily|weekly)$"),
):
    de = getattr(request.app.state, "digest", None)
    if not de:
        raise HTTPException(503, "Digest engine not available")
    if digest_type == "weekly":
        digest = await de.generate_weekly()
    else:
        digest = await de.generate_daily()
    return {
        "id": digest.id, "title": digest.title,
        "content": digest.content, "highlights": list(digest.highlights),
    }


# ── User Patterns ───────────────────────────────────────────────

@router.get("/patterns")
async def get_patterns(request: Request):
    up = getattr(request.app.state, "user_patterns", None)
    if not up:
        raise HTTPException(503, "User patterns not available")
    return {
        "stats": up.stats(),
        "active_hours": up.get_active_hours(),
        "active_days": up.get_active_days(),
        "top_topics": up.get_top_topics(),
        "recurring": up.get_recurring_patterns(),
        "anticipation": up.get_anticipation_candidates(),
    }


@router.get("/patterns/preferences")
async def get_preferences(request: Request):
    up = getattr(request.app.state, "user_patterns", None)
    if not up:
        raise HTTPException(503, "User patterns not available")
    return up.get_all_preferences()


@router.get("/patterns/proactive-usefulness")
async def proactive_usefulness(request: Request):
    up = getattr(request.app.state, "user_patterns", None)
    if not up:
        raise HTTPException(503, "User patterns not available")
    return up.get_proactive_usefulness()


# ── Escalation ──────────────────────────────────────────────────

@router.get("/escalation")
async def escalation_status(request: Request):
    esc = getattr(request.app.state, "escalation", None)
    if not esc:
        raise HTTPException(503, "Escalation engine not available")
    return {
        "stats": esc.stats(),
        "confidence_scores": esc.get_confidence_scores(),
        "recent_decisions": esc.get_recent_decisions(10),
    }


@router.post("/escalation/{record_id}/override")
async def record_override(record_id: str, request: Request):
    esc = getattr(request.app.state, "escalation", None)
    if not esc:
        raise HTTPException(503, "Escalation engine not available")
    try:
        body = await request.json()
    except Exception:
        body = {}
        logger.debug("Invalid JSON body, using empty dict")
    esc.record_override(record_id, body.get("action", "user_override"))
    return {"overridden": True}


@router.post("/escalation/{record_id}/outcome")
async def record_outcome(record_id: str, request: Request):
    esc = getattr(request.app.state, "escalation", None)
    if not esc:
        raise HTTPException(503, "Escalation engine not available")
    try:
        body = await request.json()
    except Exception:
        body = {}
        logger.debug("Invalid JSON body, using empty dict")
    positive = body.get("positive", True)
    esc.record_outcome(record_id, positive)
    return {"recorded": True, "positive": positive}


# ── Directives ─────────────────────────────────────────────────

@router.get("/directives")
async def list_directives(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
):
    de = getattr(request.app.state, "directive", None)
    if not de:
        raise HTTPException(503, "Directive engine not available")
    return {
        "active": de.get_active_directives(),
        "history": de.get_history(limit),
        "stats": de.stats(),
    }


@router.get("/directives/active")
async def active_directives(request: Request):
    de = getattr(request.app.state, "directive", None)
    if not de:
        raise HTTPException(503, "Directive engine not available")
    return {"directives": de.get_active_directives()}


@router.post("/directives/cycle")
async def run_directive_cycle(request: Request):
    """Manually trigger a directive generation cycle."""
    de = getattr(request.app.state, "directive", None)
    if not de:
        raise HTTPException(503, "Directive engine not available")
    results = await de.run_cycle()
    return {
        "directives_generated": len(results),
        "directives": [
            {"id": d.id, "title": d.title, "category": d.category,
             "status": d.status, "assigned_agents": list(d.assigned_agents)}
            for d in results
        ],
    }


@router.post("/directives")
async def create_directive(req: DirectiveRequest, request: Request):
    """Manually create a strategic directive."""
    import uuid
    from backend.core.directive_engine import Directive, _CATEGORY_AGENTS
    de = getattr(request.app.state, "directive", None)
    if not de:
        raise HTTPException(503, "Directive engine not available")
    agents = req.assigned_agents
    if not agents:
        agents = _CATEGORY_AGENTS.get(req.category, ["researcher"])
    directive = Directive(
        id=f"dir_{uuid.uuid4().hex[:12]}",
        title=req.title,
        rationale=req.rationale,
        priority=req.priority,
        category=req.category,
        assigned_agents=tuple(agents),
        collab_pattern=req.collab_pattern,
        task_description=req.task_description,
        ttl_minutes=req.ttl_minutes,
        source_signals=("manual",),
    )
    de._store_directive(directive)
    return {
        "id": directive.id, "title": directive.title,
        "category": directive.category, "status": directive.status,
        "assigned_agents": list(directive.assigned_agents),
    }


@router.delete("/directives/{directive_id}")
async def delete_directive(directive_id: str, request: Request):
    """Delete a directive by ID."""
    de = getattr(request.app.state, "directive", None)
    if not de:
        raise HTTPException(503, "Directive engine not available")
    try:
        existing = de.conn.execute(
            "SELECT id FROM directives WHERE id = ?", (directive_id,)
        ).fetchone()
        if not existing:
            raise HTTPException(404, "Directive not found")
        de.conn.execute("DELETE FROM directives WHERE id = ?", (directive_id,))
        de.conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Failed to delete directive: {exc}")
    return {"deleted": True, "directive_id": directive_id}


@router.get("/directives/stats")
async def directive_stats(request: Request):
    de = getattr(request.app.state, "directive", None)
    if not de:
        raise HTTPException(503, "Directive engine not available")
    return de.stats()


# ── Agent Network ──────────────────────────────────────────────

class InsightRequest(BaseModel):
    source_agent: str = Field(min_length=1, max_length=50)
    insight_type: str = Field(default="discovery", max_length=50)
    domain: str = Field(default="research", max_length=50)
    content: str = Field(min_length=1, max_length=2000)
    confidence: float = Field(default=0.7, ge=0.0, le=1.0)
    ttl_hours: int = Field(default=48, ge=1, le=720)


@router.get("/network")
async def network_status(request: Request):
    net = getattr(request.app.state, "agent_network", None)
    if not net:
        raise HTTPException(503, "Agent network not available")
    return {
        "stats": net.stats(),
        "recent_insights": net.get_all_recent(limit=20),
    }


@router.get("/network/insights/{agent_id}")
async def agent_insights(agent_id: str, request: Request):
    """Get network insights relevant to a specific agent."""
    net = getattr(request.app.state, "agent_network", None)
    if not net:
        raise HTTPException(503, "Agent network not available")
    insights = net.get_insights_for(agent_id, limit=15)
    return {
        "agent_id": agent_id,
        "insights": [
            {"id": i.id, "source_agent": i.source_agent, "domain": i.domain,
             "insight_type": i.insight_type, "content": i.content,
             "confidence": i.confidence, "applied_count": i.applied_count,
             "created_at": i.created_at}
            for i in insights
        ],
        "context": net.get_network_context(agent_id),
    }


@router.post("/network/share")
async def share_insight(req: InsightRequest, request: Request):
    """Manually share an insight into the agent network."""
    net = getattr(request.app.state, "agent_network", None)
    if not net:
        raise HTTPException(503, "Agent network not available")
    insight = net.share_insight(
        source_agent=req.source_agent,
        insight_type=req.insight_type,
        domain=req.domain,
        content=req.content,
        confidence=req.confidence,
        ttl_hours=req.ttl_hours,
    )
    return {"id": insight.id, "source_agent": insight.source_agent,
            "domain": insight.domain, "relevance_agents": list(insight.relevance_agents)}


@router.get("/network/stats")
async def network_stats(request: Request):
    net = getattr(request.app.state, "agent_network", None)
    if not net:
        raise HTTPException(503, "Agent network not available")
    return net.stats()
