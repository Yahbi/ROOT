"""Plugin routes — manage and invoke ROOT's plugins."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/plugins", tags=["plugins"])


class InvokeRequest(BaseModel):
    tool: str
    args: dict[str, Any] = {}


@router.get("")
async def list_plugins(request: Request):
    """List all registered plugins with extended metadata."""
    engine = request.app.state.plugins
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "version": p.version,
            "author": p.author,
            "status": p.status.value,
            "category": p.category,
            "tags": p.tags,
            "dependencies": list(p.dependencies),
            "tools": [{"name": t.name, "description": t.description} for t in p.tools],
            "marketplace": {
                "rating": p.marketplace.rating,
                "downloads": p.marketplace.downloads,
                "verified": p.marketplace.verified,
                "license": p.marketplace.license,
            },
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


@router.post("/{plugin_id}/reload")
async def reload_plugin(plugin_id: str, request: Request):
    """Hot-reload a plugin (re-register with same definition, bumping version history)."""
    engine = request.app.state.plugins
    plugin = engine.get_plugin(plugin_id)
    if not plugin:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    engine.reload(plugin, version_note="Manual hot-reload via API")
    return {"status": "reloaded", "plugin_id": plugin_id, "version": plugin.version}


@router.get("/stats")
async def plugin_stats(request: Request):
    return request.app.state.plugins.stats()


@router.get("/health")
async def plugin_health_all(request: Request):
    """Return health metrics for all plugins."""
    return request.app.state.plugins.all_health()


@router.get("/health/unhealthy")
async def plugin_health_unhealthy(
    request: Request,
    min_error_rate: float = Query(0.5, ge=0.0, le=1.0),
    min_invocations: int = Query(5, ge=1),
):
    """List plugin IDs with error rate above the threshold."""
    engine = request.app.state.plugins
    return {"unhealthy": engine.unhealthy_plugins(min_error_rate, min_invocations)}


@router.get("/{plugin_id}/health")
async def plugin_health(plugin_id: str, request: Request):
    """Return health metrics for a single plugin."""
    engine = request.app.state.plugins
    health = engine.get_health(plugin_id)
    if health is None:
        raise HTTPException(status_code=404, detail=f"No health data for plugin '{plugin_id}'")
    return health.to_dict()


@router.get("/marketplace")
async def marketplace_all(request: Request):
    """Return marketplace listings for all plugins."""
    return request.app.state.plugins.marketplace_all()


@router.get("/marketplace/{plugin_id}")
async def marketplace_plugin(plugin_id: str, request: Request):
    """Return marketplace listing for a single plugin."""
    engine = request.app.state.plugins
    listing = engine.marketplace_listing(plugin_id)
    if listing is None:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return listing


@router.get("/dependencies")
async def dependency_graph(request: Request):
    """Return the full plugin dependency graph."""
    return request.app.state.plugins.dependency_graph()


@router.get("/{plugin_id}/versions")
async def plugin_version_history(plugin_id: str, request: Request):
    """Return version history for a plugin."""
    engine = request.app.state.plugins
    history = engine.version_history(plugin_id)
    if not history and not engine.get_plugin(plugin_id):
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return {"plugin_id": plugin_id, "history": history}


@router.get("/{plugin_id}/config-schema")
async def plugin_config_schema(plugin_id: str, request: Request):
    """Return the frontend configuration schema for a plugin."""
    engine = request.app.state.plugins
    schema = engine.config_schema(plugin_id)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"Plugin '{plugin_id}' not found")
    return {"plugin_id": plugin_id, "schema": schema}


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
