"""SSE events route — Server-Sent Events fallback for real-time updates.

For clients that can't use WebSocket (e.g., some mobile browsers),
this endpoint provides a streaming SSE connection.

Usage:
    GET /api/events?topics=system.*,agent.*
    -> Server-Sent Events stream
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

logger = logging.getLogger("root.routes.events")

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def sse_stream(request: Request, topics: str = "system.*"):
    """Stream server-sent events for the given topic patterns.

    Query params:
        topics: Comma-separated topic patterns (default: system.*)
    """
    topic_list = [t.strip() for t in topics.split(",") if t.strip()]
    bus = getattr(request.app.state, "bus", None)

    async def event_generator():
        """Generate SSE events from the message bus."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=100)

        async def _on_message(msg: Any) -> None:
            """Buffer bus messages into the queue."""
            event = {
                "topic": msg.topic,
                "id": msg.id,
                "sender": msg.sender,
                "payload": msg.payload,
                "timestamp": msg.timestamp,
            }
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass  # Drop oldest if queue is full

        # Subscribe to requested topics
        sub_id = f"sse_{id(queue)}"
        if bus:
            for pattern in topic_list:
                bus.subscribe(pattern, sub_id, _on_message)

        try:
            # Send initial connection event
            yield _format_sse("connected", {"topics": topic_list})

            # Heartbeat + event loop
            while True:
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield _format_sse("message", event)
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield _format_sse("heartbeat", {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
        finally:
            # Unsubscribe when client disconnects
            if bus:
                for pattern in topic_list:
                    bus.unsubscribe(pattern, sub_id)
            logger.debug("SSE client disconnected (sub_id=%s)", sub_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


def _format_sse(event_type: str, data: dict[str, Any]) -> str:
    """Format a server-sent event."""
    json_data = json.dumps(data, default=str)
    return f"event: {event_type}\ndata: {json_data}\n\n"
