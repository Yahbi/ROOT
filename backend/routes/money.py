"""Money routes — Strategy Council endpoints for wealth generation."""

from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request

router = APIRouter(prefix="/api/money", tags=["money"])


@router.post("/council")
async def convene_council(request: Request, focus: Optional[str] = None):
    """Convene the Strategy Council — all agents collaborate on money-making."""
    money = request.app.state.money
    session = await money.convene_council(focus=focus)
    return {
        "session_id": session.id,
        "mode": session.mode,
        "agents_consulted": session.agents_consulted,
        "total_opportunities": session.total_opportunities,
        "duration_seconds": session.session_duration_seconds,
        "top_recommendation": asdict(session.top_recommendation) if session.top_recommendation else None,
        "opportunities": [asdict(o) for o in session.opportunities],
    }


@router.post("/council/online")
async def convene_council_online(request: Request, focus: Optional[str] = None):
    """Convene online Strategy Council — LLM + multi-agent deliberation."""
    money = request.app.state.money
    session = await money.convene_council_online(focus=focus)
    return {
        "session_id": session.id,
        "mode": session.mode,
        "agents_consulted": session.agents_consulted,
        "total_opportunities": session.total_opportunities,
        "duration_seconds": session.session_duration_seconds,
        "top_recommendation": asdict(session.top_recommendation) if session.top_recommendation else None,
        "opportunities": [asdict(o) for o in session.opportunities],
    }


@router.get("/opportunities")
async def list_opportunities(request: Request, limit: int = Query(default=10, ge=1, le=500)):
    """Get latest opportunities from most recent council session."""
    money = request.app.state.money
    opps = money.get_latest_opportunities(limit=limit)
    return [asdict(o) for o in opps]


@router.get("/opportunities/{opp_id}")
async def get_opportunity(request: Request, opp_id: str):
    """Get a specific opportunity by ID."""
    money = request.app.state.money
    opp = money.get_opportunity(opp_id)
    if not opp:
        raise HTTPException(404, "Opportunity not found")
    return asdict(opp)


@router.get("/sessions")
async def list_sessions(request: Request, limit: int = Query(default=20, ge=1, le=500)):
    """List previous council sessions."""
    money = request.app.state.money
    sessions = money.get_sessions(limit=limit)
    return [
        {
            "id": s.id,
            "total_opportunities": s.total_opportunities,
            "top_title": s.top_recommendation.title if s.top_recommendation else None,
            "top_confidence": s.top_recommendation.confidence_score if s.top_recommendation else None,
            "agents_consulted": s.agents_consulted,
            "duration_seconds": s.session_duration_seconds,
            "mode": s.mode,
            "created_at": s.created_at,
        }
        for s in sessions
    ]


@router.get("/stats")
async def money_stats(request: Request):
    """Strategy Council statistics."""
    return request.app.state.money.stats()
