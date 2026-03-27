"""Routes for Council Store — debate history and deep-dive analysis."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/api/councils", tags=["councils"])


class DebateRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    symbols: str = Field(default="", max_length=200)


@router.post("/debate")
async def trigger_council_debate(req: DebateRequest, request: Request):
    """Trigger a MiRo council debate on a topic."""
    miro = getattr(request.app.state, "registry", None)
    if not miro:
        raise HTTPException(503, "Agent registry not available")

    connector = miro._connectors.get("miro")
    if not connector:
        raise HTTPException(503, "MiRo connector not available")

    try:
        result = await connector.run_council_debate(
            topic=req.topic,
            symbols=req.symbols,
        )
    except Exception as exc:
        raise HTTPException(500, f"Council debate failed: {str(exc)[:200]}")

    # Store in council store if available
    council_store = getattr(request.app.state, "council_store", None)
    debate_id = None
    if council_store:
        from backend.core.council_store import CouncilPerspective

        # Parse perspectives from the council debate result
        perspectives = _parse_perspectives(result)
        debate_id = council_store.record_debate(
            topic=req.topic,
            symbols=req.symbols,
            perspectives=perspectives,
            consensus=result.get("council_debate", "")[:1000],
            verdict=result.get("result", "")[:2000],
        )

    return {
        "debate_id": debate_id,
        "topic": req.topic,
        "result": result.get("result", ""),
        "observe_data": result.get("observe_data", ""),
        "entities": result.get("entities", ""),
        "scenarios": result.get("scenarios", ""),
        "council_debate": result.get("council_debate", ""),
        "market_session": result.get("market_session", ""),
    }


@router.get("")
async def list_debates(
    request: Request,
    limit: int = Query(default=20, ge=1, le=100),
):
    """List recent council debates."""
    store = getattr(request.app.state, "council_store", None)
    if not store:
        raise HTTPException(503, "Council store not available")

    debates = store.list_debates(limit=limit)
    return {"debates": debates, "total": len(debates)}


@router.get("/stats")
async def council_stats(request: Request):
    """Get council debate statistics."""
    store = getattr(request.app.state, "council_store", None)
    if not store:
        raise HTTPException(503, "Council store not available")
    return store.stats()


@router.get("/{debate_id}")
async def get_debate(debate_id: str, request: Request):
    """Get full council debate with all agent perspectives."""
    store = getattr(request.app.state, "council_store", None)
    if not store:
        raise HTTPException(503, "Council store not available")

    debate = store.get_debate(debate_id)
    if not debate:
        raise HTTPException(404, "Debate not found")

    return {
        "id": debate.id,
        "topic": debate.topic,
        "symbols": debate.symbols,
        "consensus": debate.consensus,
        "verdict": debate.verdict,
        "perspectives": [
            {
                "agent_id": p.agent_id,
                "agent_role": p.agent_role,
                "stance": p.stance,
                "reasoning": p.reasoning,
                "confidence": p.confidence,
                "key_points": p.key_points,
            }
            for p in debate.perspectives
        ],
        "created_at": debate.created_at,
    }


def _parse_perspectives(result: dict) -> list:
    """Parse agent perspectives from council debate result text."""
    from backend.core.council_store import CouncilPerspective

    perspectives = []
    council_text = result.get("council_debate", "")
    result_text = result.get("result", "")

    # Create perspectives for the agents that participated
    agent_roles = {
        "researcher": ("researcher", "Research Analyst"),
        "analyst": ("analyst", "Business Analyst"),
        "guardian": ("guardian", "Risk Guardian"),
        "miro": ("miro", "MiRo Synthesis"),
    }

    for agent_id, (aid, role) in agent_roles.items():
        # Determine stance from result text
        stance = "neutral"
        lower_result = result_text.lower()
        if any(w in lower_result for w in ("bullish", "buy", "long", "upside")):
            stance = "bullish"
        elif any(w in lower_result for w in ("bearish", "sell", "short", "downside")):
            stance = "bearish"

        reasoning = council_text[:500] if council_text else result_text[:500]

        perspectives.append(CouncilPerspective(
            agent_id=aid,
            agent_role=role,
            stance=stance,
            reasoning=reasoning,
            confidence=0.6,
            key_points=[],
        ))

    return perspectives
