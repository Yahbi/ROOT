"""Plugin routes — manage and invoke ROOT's plugins."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


class InvokeRequest(BaseModel):
    tool: str
    args: dict[str, Any] = {}


@router.get("")
async def list_plugins(request: Request):
    """List all registered plugins."""
    engine = request.app.state.plugins
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "version": p.version,
            "status": p.status.value,
            "category": p.category,
            "tags": p.tags,
            "tools": [{"name": t.name, "description": t.description} for t in p.tools],
        }
        for p in engine.list_plugins()
    ]


@router.get("/tools")
async def list_tools(request: Request):
    """List all available plugin tools."""
    return request.app.state.plugins.list_tools()


@router.post("/invoke")
async def invoke_tool(req: InvokeRequest, request: Request):
    """Invoke a plugin tool by name."""
    engine = request.app.state.plugins
    result = await engine.invoke(req.tool, req.args)
    return {
        "success": result.success,
        "output": result.output,
        "error": result.error,
        "duration_ms": result.duration_ms,
    }


@router.post("/{plugin_id}/enable")
async def enable_plugin(plugin_id: str, request: Request):
    ok = request.app.state.plugins.enable(plugin_id)
    return {"status": "enabled" if ok else "not_found"}


@router.post("/{plugin_id}/disable")
async def disable_plugin(plugin_id: str, request: Request):
    ok = request.app.state.plugins.disable(plugin_id)
    return {"status": "disabled" if ok else "not_found"}


@router.get("/stats")
async def plugin_stats(request: Request):
    return request.app.state.plugins.stats()


@router.get("/log")
async def plugin_log(request: Request, limit: int = Query(50, ge=1, le=500)):
    return [
        {
            "plugin_id": r.plugin_id,
            "tool_name": r.tool_name,
            "success": r.success,
            "duration_ms": r.duration_ms,
            "timestamp": r.timestamp,
        }
        for r in request.app.state.plugins.get_log(limit)
    ]
