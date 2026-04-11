"""
Routes for Context Manager — HERMES-style conversation context
compression and windowing stats.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger("root.routes.context")

router = APIRouter(prefix="/api/context", tags=["context"])


# ── Stats ────────────────────────────────────────────────────────

@router.get("/stats")
async def context_stats(request: Request):
    """Context window stats from the context manager."""
    cm = getattr(request.app.state, "context_manager", None)
    if not cm:
        raise HTTPException(503, "Context manager not available")
    return cm.stats()


# ── Reset ────────────────────────────────────────────────────────

@router.post("/reset")
async def reset_context(request: Request):
    """Clear/reset context manager state."""
    cm = getattr(request.app.state, "context_manager", None)
    if not cm:
        raise HTTPException(503, "Context manager not available")

    # Known pattern: no public reset method on ContextManager.
    # Direct mutation of internal counter is intentional until a reset() API is added.
    try:
        cm._compression_count = 0
    except AttributeError:
        logger.debug("Context manager internal layout change — compression_count reset skipped")

    return {"reset": True, "stats": cm.stats()}
