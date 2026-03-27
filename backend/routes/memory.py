"""Memory routes — inspect and manage ROOT's persistent memory."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger("root.routes.memory")

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.models.response import APIResponse

router = APIRouter(prefix="/api/memory", tags=["memory"])


class SearchRequest(BaseModel):
    query: str = ""
    memory_type: Optional[str] = None
    tags: list[str] = []
    min_confidence: float = 0.0
    limit: int = 20


class CreateMemoryRequest(BaseModel):
    content: str = Field(min_length=1, max_length=5000)
    memory_type: str = Field(default="fact", max_length=50)
    source: str = Field(default="manual", max_length=100)
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)


@router.get("/stats")
async def memory_stats(request: Request):
    """Get memory statistics."""
    memory = request.app.state.memory
    return memory.stats()


@router.get("/recent")
async def recent_memories(
    request: Request,
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at", pattern="^(created_at|confidence|memory_type)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Get most recent memories with pagination and sorting."""
    memory = request.app.state.memory
    # Fetch extra entries to support offset slicing
    entries = memory.get_recent(limit=limit + offset)
    items = [e.model_dump() for e in entries]

    # Sort by requested field
    reverse = sort_order == "desc"
    items = sorted(items, key=lambda x: x.get(sort_by, ""), reverse=reverse)

    # Apply offset pagination
    items = items[offset: offset + limit]

    return APIResponse.ok(items)


@router.get("/strongest")
async def strongest_memories(request: Request, limit: int = Query(default=20, ge=1, le=500)):
    """Get highest-confidence memories."""
    memory = request.app.state.memory
    entries = memory.get_strongest(limit=limit)
    return [e.model_dump() for e in entries]


@router.post("/search")
async def search_memories(req: SearchRequest, request: Request):
    """Full-text search across memories."""
    from backend.models.memory import MemoryQuery, MemoryType

    try:
        mt = MemoryType(req.memory_type) if req.memory_type else None
    except ValueError:
        mt = None

    query = MemoryQuery(
        query=req.query,
        memory_type=mt,
        tags=req.tags,
        min_confidence=req.min_confidence,
        limit=req.limit,
    )
    memory = request.app.state.memory
    entries = memory.search(query)
    return [e.model_dump() for e in entries]


@router.get("/search")
async def search_memories_get(request: Request, q: str = Query("", max_length=2000), limit: int = Query(20, ge=1, le=500), min_confidence: float = 0.0):
    """GET-based search for convenience (e.g. curl, browser)."""
    from backend.models.memory import MemoryQuery
    query = MemoryQuery(query=q, limit=limit, min_confidence=min_confidence)
    memory = request.app.state.memory
    entries = memory.search(query)
    return [e.model_dump() for e in entries]


@router.post("/rebuild-fts")
async def rebuild_fts(request: Request):
    """Rebuild the FTS5 full-text search index (fixes stale/missing results)."""
    memory = request.app.state.memory
    count = memory.rebuild_fts()
    return {"status": "rebuilt", "indexed_entries": count}


@router.get("/{memory_id}")
async def get_memory(memory_id: str, request: Request):
    """Get a specific memory by ID."""
    memory = request.app.state.memory
    entry = memory.recall(memory_id)
    if not entry:
        raise HTTPException(404, "Memory not found")
    return entry.model_dump()


@router.post("")
async def create_memory(req: CreateMemoryRequest, request: Request):
    """Create a new memory entry."""
    import uuid
    from datetime import datetime, timezone
    from backend.models.memory import MemoryEntry, MemoryType

    try:
        mt = MemoryType(req.memory_type)
    except ValueError:
        mt = MemoryType.FACT

    entry = MemoryEntry(
        id=f"mem_{uuid.uuid4().hex[:12]}",
        content=req.content,
        memory_type=mt,
        source=req.source,
        tags=tuple(req.tags),
        confidence=req.confidence,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    memory = request.app.state.memory
    stored = memory.store(entry)
    return {"id": stored.id, "content": stored.content, "memory_type": stored.memory_type.value}


@router.post("/{memory_id}/strengthen")
async def strengthen_memory(memory_id: str, request: Request):
    """Boost a memory's confidence score."""
    memory = request.app.state.memory
    entry = memory.recall(memory_id)
    if not entry:
        raise HTTPException(404, "Memory not found")
    memory.strengthen(memory_id)
    return {"strengthened": True, "memory_id": memory_id}


@router.delete("/{memory_id}")
async def delete_memory(memory_id: str, request: Request):
    """Delete a memory by ID."""
    memory = request.app.state.memory
    entry = memory.recall(memory_id)
    if not entry:
        raise HTTPException(404, "Memory not found")
    try:
        memory.supersede(memory_id, "")
    except Exception as exc:
        logger.warning("supersede failed, falling back to DELETE: %s", exc)
        memory.conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        memory.conn.commit()
    return {"deleted": True, "memory_id": memory_id}


@router.post("/decay")
async def trigger_decay(request: Request, factor: float = Query(0.995, ge=0.01, le=1.0)):
    """Manually trigger memory decay."""
    memory = request.app.state.memory
    affected = memory.decay(factor=factor)
    return {"affected": affected, "remaining": memory.count()}
