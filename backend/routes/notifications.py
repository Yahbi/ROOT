"""Notification center API — exposes NotificationEngine history and controls."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, Query, Request

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


# ── History & Search ─────────────────────────────────────────────────────────


@router.get("")
async def get_notifications(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    level: str | None = Query(None, description="Filter by level: low, medium, high, critical"),
    source: str | None = Query(None, description="Filter by source system/agent"),
    notification_type: str | None = Query(None, description="Filter by notification type"),
    search: str | None = Query(None, description="Full-text keyword search in title and body"),
    since: str | None = Query(None, description="ISO datetime — include notifications at or after"),
    until: str | None = Query(None, description="ISO datetime — include notifications at or before"),
    unread_only: bool = Query(False, description="Return only unread notifications"),
    unacknowledged_only: bool = Query(False, description="Return only unacknowledged HIGH/CRITICAL"),
):
    """Get notification history with optional filtering and full-text search."""
    engine = request.app.state.notifications
    history = engine.get_history(
        limit=limit,
        level=level,
        source=source,
        notification_type=notification_type,
        search=search,
        since=since,
        until=until,
        unread_only=unread_only,
        unacknowledged_only=unacknowledged_only,
    )
    unread = sum(1 for n in history if not n.get("read"))
    return {
        "notifications": history,
        "total": len(history),
        "unread": unread,
    }


@router.get("/search")
async def search_notifications(
    request: Request,
    q: str = Query(..., description="Search query"),
    limit: int = Query(50, ge=1, le=500),
):
    """Full-text search across notification title and body."""
    engine = request.app.state.notifications
    results = engine.search_history(query=q, limit=limit)
    return {
        "query": q,
        "notifications": results,
        "total": len(results),
    }


# ── Read & Acknowledge ────────────────────────────────────────────────────────


@router.post("/read/{notification_id}")
async def mark_read(request: Request, notification_id: str):
    """Mark a notification as read."""
    engine = request.app.state.notifications
    for notif in engine._history:
        if getattr(notif, "id", "") == notification_id:
            notif.read = True
            return {"success": True}
    return {"success": False, "error": "Notification not found"}


@router.post("/read-all")
async def mark_all_read(request: Request):
    """Mark all notifications as read."""
    engine = request.app.state.notifications
    count = 0
    for notif in engine._history:
        if not getattr(notif, "read", False):
            notif.read = True
            count += 1
    return {"success": True, "marked": count}


@router.post("/acknowledge/{notification_id}")
async def acknowledge_notification(request: Request, notification_id: str):
    """Acknowledge a HIGH/CRITICAL notification to stop escalation."""
    engine = request.app.state.notifications
    success = engine.acknowledge(notification_id)
    if success:
        return {"success": True, "message": "Notification acknowledged — escalation stopped"}
    return {"success": False, "error": "Notification not found"}


# ── Stats ─────────────────────────────────────────────────────────────────────


@router.get("/stats")
async def notification_stats(request: Request):
    """Notification engine statistics (delivery counts, queue sizes, config)."""
    engine = request.app.state.notifications
    stats = engine.stats()
    return stats


# ── Templates ─────────────────────────────────────────────────────────────────


@router.get("/templates")
async def list_templates(request: Request):
    """List all registered notification templates."""
    engine = request.app.state.notifications
    names = engine.list_templates()
    templates = []
    for name in names:
        tmpl = engine.get_template(name)
        if tmpl:
            templates.append({
                "name": tmpl.name,
                "title_template": tmpl.title_template,
                "body_template": tmpl.body_template,
                "default_level": tmpl.default_level,
                "default_type": tmpl.default_type,
            })
    return {"templates": templates, "total": len(templates)}


@router.post("/templates")
async def register_template(
    request: Request,
    body: dict[str, Any] = Body(...),
):
    """Register a new notification template.

    Body: {name, title_template, body_template, default_level?, default_type?}
    """
    engine = request.app.state.notifications
    name = body.get("name", "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Template name is required")
    title_template = body.get("title_template", "")
    body_template = body.get("body_template", "")
    if not title_template or not body_template:
        raise HTTPException(status_code=400, detail="title_template and body_template are required")
    engine.register_template(
        name=name,
        title_template=title_template,
        body_template=body_template,
        default_level=body.get("default_level", "high"),
        default_type=body.get("default_type", "generic"),
    )
    return {"success": True, "template": name}


@router.post("/templates/{template_name}/send")
async def send_template(
    request: Request,
    template_name: str,
    body: dict[str, Any] = Body(...),
):
    """Render and send a notification using a template.

    Body: {variables: {...}, level?: str, source?: str, notification_type?: str}
    """
    engine = request.app.state.notifications
    variables = body.get("variables", {})
    success = await engine.send_template(
        template_name=template_name,
        variables=variables,
        level=body.get("level"),
        source=body.get("source", "root"),
        notification_type=body.get("notification_type"),
    )
    return {"success": success, "template": template_name}


# ── Channel Preferences ───────────────────────────────────────────────────────


@router.get("/channels/preferences")
async def list_channel_preferences(request: Request):
    """List per-notification-type channel routing preferences."""
    engine = request.app.state.notifications
    return {
        "preferences": engine.list_channel_preferences(),
        "available_channels": engine._determine_channels(),
    }


@router.post("/channels/preferences")
async def set_channel_preference(
    request: Request,
    body: dict[str, Any] = Body(...),
):
    """Set channel routing preference for a notification type.

    Body: {notification_type, channels: [...], min_level?}
    Example: {"notification_type": "trade", "channels": ["telegram"], "min_level": "low"}
    """
    engine = request.app.state.notifications
    ntype = body.get("notification_type", "").strip()
    if not ntype:
        raise HTTPException(status_code=400, detail="notification_type is required")
    channels = body.get("channels", [])
    if not channels:
        raise HTTPException(status_code=400, detail="At least one channel is required")
    engine.set_channel_preference(
        notification_type=ntype,
        channels=channels,
        min_level=body.get("min_level", "low"),
    )
    return {"success": True, "notification_type": ntype, "channels": channels}


# ── Scheduling / Quiet Hours ──────────────────────────────────────────────────


@router.get("/schedule/quiet-hours")
async def get_quiet_hours(request: Request):
    """Get current quiet hours configuration."""
    engine = request.app.state.notifications
    return {
        "enabled": engine._respect_quiet_hours,
        "start": engine._quiet_hours_start,
        "end": engine._quiet_hours_end,
        "currently_active": engine._is_quiet_hours(),
        "deferred_count": len(engine._deferred_queue),
    }


@router.post("/schedule/quiet-hours")
async def configure_quiet_hours(
    request: Request,
    body: dict[str, Any] = Body(...),
):
    """Configure quiet hours window (UTC).

    Body: {start: int, end: int, enabled?: bool}
    Example: {"start": 22, "end": 8, "enabled": true}
    """
    engine = request.app.state.notifications
    start = body.get("start", 22)
    end = body.get("end", 8)
    enabled = body.get("enabled", True)
    if not (0 <= start <= 23 and 0 <= end <= 23):
        raise HTTPException(status_code=400, detail="start and end must be 0-23 UTC hours")
    engine.configure_quiet_hours(start=start, end=end, enabled=enabled)
    return {
        "success": True,
        "start": start,
        "end": end,
        "enabled": enabled,
    }


@router.post("/schedule/flush-deferred")
async def flush_deferred(request: Request):
    """Immediately flush notifications deferred during quiet hours."""
    engine = request.app.state.notifications
    count = len(engine._deferred_queue)
    await engine._flush_deferred()
    return {"success": True, "flushed": count}
