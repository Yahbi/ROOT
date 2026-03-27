"""Interest Assessment routes — evaluate if decisions serve Yohan's interests."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/interest", tags=["interest"])


class AssessRequest(BaseModel):
    subject: str = Field(..., max_length=1000)
    context: str = Field(default="", max_length=5000)
    financial_impact: float = 0.0
    time_cost_hours: float = 0.0
    risk_level: str = Field(default="medium", pattern=r"^(low|medium|high)$")
    use_llm: bool = False


@router.post("/assess")
async def assess_interest(req: AssessRequest, request: Request):
    """Assess whether something serves Yohan's interests."""
    engine = getattr(request.app.state, "interest", None)
    if not engine:
        raise HTTPException(status_code=503, detail="Interest engine not initialized")

    if req.use_llm:
        result = await engine.assess_with_llm(req.subject, req.context)
    else:
        result = engine.assess(
            subject=req.subject,
            context=req.context,
            financial_impact=req.financial_impact,
            time_cost_hours=req.time_cost_hours,
            risk_level=req.risk_level,
        )

    return {
        "subject": result.subject,
        "verdict": result.verdict.value,
        "score": result.score,
        "financial_impact": result.financial_impact,
        "time_cost_hours": result.time_cost_hours,
        "risk_level": result.risk_level.value,
        "reasoning": result.reasoning,
        "benefits": result.benefits,
        "risks": result.risks,
        "recommendation": result.recommendation,
        "knowledge_domains": result.knowledge_domains,
    }


@router.get("/history")
async def assessment_history(request: Request, limit: int = Query(default=20, ge=1, le=500)):
    """Get recent interest assessments."""
    engine = getattr(request.app.state, "interest", None)
    if not engine:
        return []
    return [
        {
            "subject": a.subject,
            "verdict": a.verdict.value,
            "score": a.score,
            "recommendation": a.recommendation,
            "timestamp": a.timestamp,
        }
        for a in engine.get_history(limit)
    ]


@router.get("/stats")
async def interest_stats(request: Request):
    """Get interest assessment statistics."""
    engine = getattr(request.app.state, "interest", None)
    if not engine:
        return {"total_assessments": 0}
    return engine.stats()


@router.get("/profile")
async def yohan_profile(request: Request):
    """Get Yohan's interest profile used for assessments."""
    from backend.core.interest_engine import YOHAN_PROFILE
    return YOHAN_PROFILE
