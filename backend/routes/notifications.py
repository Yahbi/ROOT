"""Notification center API — exposes NotificationEngine history."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def get_notifications(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    level: str | None = Query(None, description="Filter by level: low, medium, high, critical"),
):
    """Get notification history with optional level filter."""
    engine = request.app.state.notifications
    history = engine.get_history(limit=limit)
    if level:
        history = [n for n in history if n.get("level") == level]
    unread = sum(1 for n in history if not n.get("read"))
    return {
        "notifications": history,
        "total": len(history),
        "unread": unread,
    }


@router.post("/read/{notification_id}")
async def mark_read(request: Request, notification_id: str):
    """Mark a notification as read."""
    engine = request.app.state.notifications
    # Mark in history (in-memory deque)
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


@router.get("/stats")
async def notification_stats(request: Request):
    """Notification engine statistics."""
    engine = request.app.state.notifications
    stats = engine.stats()
    history = engine.get_history(limit=200)
    unread = sum(1 for n in history if not n.get("read"))
    return {**stats, "unread": unread}
