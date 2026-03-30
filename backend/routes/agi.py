"""AGI Systems routes — expose all AGI subsystems to the dashboard."""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.models.response import APIResponse

logger = logging.getLogger("root.routes.agi")

router = APIRouter(prefix="/api/agi", tags=["AGI Systems"])


# ── Helpers ─────────────────────────────────────────────────────────

def _get_service(request: Request, name: str) -> Any:
    """Get a service from app.state, raising 503 if not initialized."""
    svc = getattr(request.app.state, name, None)
    if svc is None:
        raise HTTPException(status_code=503, detail=f"{name} not initialized")
    return svc


def _safe_stats(request: Request, name: str) -> dict:
    """Get stats from a service, returning error dict if unavailable."""
    svc = getattr(request.app.state, name, None)
    if svc is None:
        return {"error": "not initialized"}
    try:
        return svc.stats()
    except Exception as exc:
        logger.warning("Failed to get stats for %s: %s", name, exc)
        return {"error": str(exc)}


# ── Request Models ──────────────────────────────────────────────────

class PlanRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=5000)
    context: Optional[str] = Field(default=None, max_length=5000)


# ── 1. GET /status — Overview of all AGI subsystems ─────────────────

@router.get("/status")
async def agi_status(request: Request):
    """Overview of all AGI subsystems — stats and health."""
    # outcome_evaluator: no stats method, just report active
    outcome_evaluator_status = (
        {"active": True}
        if getattr(request.app.state, "outcome_evaluator", None) is not None
        else {"error": "not initialized"}
    )

    # outcome_registry
    outcome_registry_stats = _safe_stats(request, "outcome_registry")

    # adaptive_config
    adaptive_config = getattr(request.app.state, "adaptive_config", None)
    adaptive_config_data = (
        adaptive_config.get_all()
        if adaptive_config is not None
        else {"error": "not initialized"}
    )

    # adaptive_tuner
    adaptive_tuner_stats = _safe_stats(request, "adaptive_tuner")

    # planning_engine: just report existence
    planning_engine_status = (
        {"active": True}
        if getattr(request.app.state, "planning_engine", None) is not None
        else {"error": "not initialized"}
    )

    # trading_autonomy
    trading_autonomy_stats = _safe_stats(request, "trading_autonomy")

    # team_formation
    team_formation_stats = _safe_stats(request, "team_formation")

    # skill_executor
    skill_executor_stats = _safe_stats(request, "skill_executor")

    # conflict_detector
    conflict_detector_stats = _safe_stats(request, "conflict_detector")

    # emergency_protocol
    emergency_protocol_stats = _safe_stats(request, "emergency_protocol")

    # code_deployment
    code_deployment_stats = _safe_stats(request, "code_deployment")

    # embedding_service (optional)
    embedding_svc = getattr(request.app.state, "embedding_service", None)
    if embedding_svc is not None and hasattr(embedding_svc, "stats"):
        try:
            embedding_stats = embedding_svc.stats()
        except Exception as exc:
            logger.warning("Failed to get embedding_service stats: %s", exc)
            embedding_stats = {"error": str(exc)}
    else:
        embedding_stats = {"error": "not initialized"}

    return APIResponse.ok({
        "outcome_evaluator": outcome_evaluator_status,
        "outcome_registry": outcome_registry_stats,
        "adaptive_config": adaptive_config_data,
        "adaptive_tuner": adaptive_tuner_stats,
        "planning_engine": planning_engine_status,
        "trading_autonomy": trading_autonomy_stats,
        "team_formation": team_formation_stats,
        "skill_executor": skill_executor_stats,
        "conflict_detector": conflict_detector_stats,
        "emergency_protocol": emergency_protocol_stats,
        "code_deployment": code_deployment_stats,
        "embedding_service": embedding_stats,
    })


# ── 2. GET /outcomes — Recent outcomes from outcome_registry ────────

@router.get("/outcomes")
async def get_outcomes(
    request: Request,
    action_type: Optional[str] = Query(default=None),
    min_quality: float = Query(default=0.0, ge=0.0, le=1.0),
    limit: int = Query(default=50, ge=1, le=500),
):
    """Recent outcomes from the outcome registry."""
    registry = _get_service(request, "outcome_registry")
    try:
        outcomes = registry.get_outcomes(
            action_type=action_type,
            min_quality=min_quality,
            limit=limit,
        )
        return APIResponse.ok(outcomes)
    except Exception as exc:
        logger.error("Failed to get outcomes: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── 3. GET /outcomes/effectiveness — Action type effectiveness ──────

@router.get("/outcomes/effectiveness")
async def outcome_effectiveness(request: Request):
    """Action type effectiveness from the outcome registry."""
    registry = _get_service(request, "outcome_registry")
    try:
        effectiveness = registry.effectiveness()
        return APIResponse.ok(effectiveness)
    except Exception as exc:
        logger.error("Failed to get effectiveness: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── 4. GET /adaptive-config — All adaptive parameters ──────────────

@router.get("/adaptive-config")
async def adaptive_config(request: Request):
    """All adaptive parameters with current values, bounds, and history."""
    config = _get_service(request, "adaptive_config")
    try:
        return APIResponse.ok(config.get_all())
    except Exception as exc:
        logger.error("Failed to get adaptive config: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── 5. GET /adaptive-config/{param}/history — Parameter history ─────

@router.get("/adaptive-config/{param}/history")
async def adaptive_config_history(
    request: Request,
    param: str,
    limit: int = Query(default=50, ge=1, le=500),
):
    """History for a specific adaptive parameter."""
    config = _get_service(request, "adaptive_config")
    try:
        history = config.get_history(param, limit=limit)
        return APIResponse.ok(history)
    except Exception as exc:
        logger.error("Failed to get history for param '%s': %s", param, exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── 6. POST /plan — Generate an execution plan ─────────────────────

@router.post("/plan")
async def generate_plan(request: Request, body: PlanRequest):
    """Generate an execution plan for a goal."""
    engine = _get_service(request, "planning_engine")
    try:
        plan = await engine.plan(body.goal, body.context)
        return APIResponse.ok(plan)
    except Exception as exc:
        logger.error("Failed to generate plan: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── 7. GET /emergency — Current emergency status ───────────────────

@router.get("/emergency")
async def emergency_status(request: Request):
    """Current emergency protocol status."""
    protocol = _get_service(request, "emergency_protocol")
    try:
        stats = protocol.stats()
        paused = protocol.get_paused()
        return APIResponse.ok({**stats, "paused": paused})
    except Exception as exc:
        logger.error("Failed to get emergency status: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── 8. GET /skills/executable — List executable skills ─────────────

@router.get("/skills/executable")
async def executable_skills(request: Request):
    """List all executable skills."""
    executor = _get_service(request, "skill_executor")
    try:
        skills = executor.list_executable()
        return APIResponse.ok(skills)
    except Exception as exc:
        logger.error("Failed to list executable skills: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── 9. GET /trading-autonomy — Trading autonomy configuration ──────

@router.get("/trading-autonomy")
async def trading_autonomy(request: Request):
    """Trading autonomy configuration and stats."""
    autonomy = _get_service(request, "trading_autonomy")
    try:
        return APIResponse.ok(autonomy.stats())
    except Exception as exc:
        logger.error("Failed to get trading autonomy stats: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── 10. POST /ingest/url — Ingest a URL into ROOT's knowledge base ──

class IngestURLRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2000)
    tags: Optional[list[str]] = Field(default=None)


@router.post("/ingest/url")
async def ingest_url(request: Request, body: IngestURLRequest):
    """Fetch a URL, extract knowledge, and store in ROOT's memory."""
    ingestion = _get_service(request, "content_ingestion")
    try:
        result = await ingestion.ingest_url(body.url, tags=body.tags or [])
        return APIResponse.ok({
            "source": result.source,
            "source_type": result.source_type,
            "content_length": result.content_length,
            "facts_extracted": result.facts_extracted,
            "memories_stored": result.memories_stored,
            "key_points": list(result.key_points),
            "analysis_type": result.analysis_type,
            "success": result.success,
            "error": result.error,
        })
    except Exception as exc:
        logger.error("URL ingestion failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── 11. POST /ingest/text — Ingest text into ROOT's knowledge base ──

class IngestTextRequest(BaseModel):
    text: str = Field(min_length=1, max_length=100000)
    source: str = Field(default="api_input", max_length=500)
    tags: Optional[list[str]] = Field(default=None)


@router.post("/ingest/text")
async def ingest_text(request: Request, body: IngestTextRequest):
    """Analyze text and store extracted knowledge in ROOT's memory."""
    ingestion = _get_service(request, "content_ingestion")
    try:
        result = await ingestion.ingest_text(
            body.text, source=body.source, tags=body.tags or [],
        )
        return APIResponse.ok({
            "source": result.source,
            "source_type": result.source_type,
            "content_length": result.content_length,
            "facts_extracted": result.facts_extracted,
            "memories_stored": result.memories_stored,
            "key_points": list(result.key_points),
            "analysis_type": result.analysis_type,
            "success": result.success,
            "error": result.error,
        })
    except Exception as exc:
        logger.error("Text ingestion failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── 12. POST /ingest/batch — Batch ingest multiple items ─────────────

@router.post("/ingest/batch")
async def ingest_batch(request: Request, body: dict):
    """Batch ingest multiple items (URLs, text, files) into ROOT's memory.

    Body: {"items": [{"type": "url"|"text"|"file", "content": "...", "tags": [...]}]}
    """
    ingestion = _get_service(request, "content_ingestion")
    items = body.get("items", [])
    if not items:
        raise HTTPException(status_code=422, detail="No items provided")
    if len(items) > 20:
        raise HTTPException(status_code=422, detail="Maximum 20 items per batch")

    try:
        results = await ingestion.ingest_batch(items)
        return APIResponse.ok({
            "results": [
                {
                    "source": r.source,
                    "source_type": r.source_type,
                    "content_length": r.content_length,
                    "facts_extracted": r.facts_extracted,
                    "memories_stored": r.memories_stored,
                    "key_points": list(r.key_points),
                    "success": r.success,
                    "error": r.error,
                }
                for r in results
            ],
            "total_success": sum(1 for r in results if r.success),
            "total_failed": sum(1 for r in results if not r.success),
        })
    except Exception as exc:
        logger.error("Batch ingestion failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── 13. GET /ingestion/stats — Content ingestion statistics ──────────

@router.get("/ingestion/stats")
async def ingestion_stats(request: Request):
    """Content ingestion engine statistics."""
    ingestion = _get_service(request, "content_ingestion")
    try:
        return APIResponse.ok(ingestion.stats())
    except Exception as exc:
        logger.error("Failed to get ingestion stats: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))
