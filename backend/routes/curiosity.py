"""Curiosity Engine API — ROOT's intrinsic learning drive."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/curiosity", tags=["curiosity"])


@router.get("/stats")
async def curiosity_stats(request: Request):
    """Get curiosity engine statistics."""
    curiosity = getattr(request.app.state, "curiosity", None)
    if not curiosity:
        return {"error": "Curiosity engine not available"}
    return curiosity.stats()


@router.get("/queue")
async def curiosity_queue(request: Request, limit: int = 20):
    """Get the current curiosity queue — what ROOT wants to learn."""
    curiosity = getattr(request.app.state, "curiosity", None)
    if not curiosity:
        return []
    return curiosity.get_queue(limit=limit)


@router.get("/resolved")
async def curiosity_resolved(request: Request, limit: int = 20):
    """Get recently resolved curiosity items — what ROOT has learned."""
    curiosity = getattr(request.app.state, "curiosity", None)
    if not curiosity:
        return []
    return curiosity.get_resolved(limit=limit)


@router.post("/ask")
async def curiosity_ask(request: Request):
    """Inject a question into ROOT's curiosity queue."""
    curiosity = getattr(request.app.state, "curiosity", None)
    if not curiosity:
        return {"error": "Curiosity engine not available"}

    body = await request.json()
    question = body.get("question", "")
    domain = body.get("domain", "general")
    priority = float(body.get("priority", 0.7))

    if not question:
        return JSONResponse(status_code=400, content={"error": "question is required"})

    item = curiosity.add_curiosity(question=question, domain=domain, priority=priority)
    return {
        "id": item.id,
        "question": item.question,
        "domain": item.domain,
        "priority": item.priority,
    }
