"""WebSocket route — real-time event streaming for ROOT dashboard.

Bridges the internal MessageBus to connected WebSocket clients.
Clients can subscribe to topic patterns and receive live events.

Protocol:
  Client -> Server: {"subscribe": ["system.*", "agent.*"]}
  Client -> Server: {"unsubscribe": ["system.*"]}
  Client -> Server: {"ping": true}
  Server -> Client: {"type": "event", "topic": "...", "data": {...}, "timestamp": "..."}
  Server -> Client: {"type": "pong"}
  Server -> Client: {"type": "subscribed", "topics": [...]}
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("root.routes.ws")

router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections and topic subscriptions.

    Thread-safe via asyncio (single event loop). Each connection has
    its own set of subscribed topic patterns.
    """

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}  # conn_id -> websocket
        self._subscriptions: dict[str, set[str]] = {}  # conn_id -> topic patterns
        self._bus_subscribed = False

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def connect(self, websocket: WebSocket) -> str:
        """Accept a WebSocket connection and return its ID."""
        await websocket.accept()
        conn_id = uuid.uuid4().hex[:10]
        self._connections[conn_id] = websocket
        self._subscriptions[conn_id] = set()
        logger.info("WebSocket connected: %s (total: %d)", conn_id, len(self._connections))
        return conn_id

    def disconnect(self, conn_id: str) -> None:
        """Remove a connection."""
        self._connections.pop(conn_id, None)
        self._subscriptions.pop(conn_id, None)
        logger.info("WebSocket disconnected: %s (total: %d)", conn_id, len(self._connections))

    def subscribe(self, conn_id: str, topics: list[str]) -> None:
        """Add topic subscriptions for a connection."""
        subs = self._subscriptions.get(conn_id)
        if subs is not None:
            subs.update(topics)

    def unsubscribe(self, conn_id: str, topics: list[str]) -> None:
        """Remove topic subscriptions for a connection."""
        subs = self._subscriptions.get(conn_id)
        if subs is not None:
            subs.difference_update(topics)

    def _topic_matches(self, pattern: str, topic: str) -> bool:
        """Check if a topic matches a subscription pattern.

        Supports exact match and wildcard prefix: 'system.*' matches 'system.alert'.
        """
        if pattern == topic:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return topic.startswith(prefix + ".") or topic == prefix
        return False

    async def broadcast(self, topic: str, data: dict[str, Any]) -> int:
        """Send an event to all connections subscribed to this topic.

        Returns the number of connections that received the message.
        """
        if not self._connections:
            return 0

        event = json.dumps({
            "type": "event",
            "topic": topic,
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        sent = 0
        dead: list[str] = []

        for conn_id, ws in self._connections.items():
            subs = self._subscriptions.get(conn_id, set())
            if not any(self._topic_matches(pat, topic) for pat in subs):
                continue
            try:
                await ws.send_text(event)
                sent += 1
            except Exception as exc:
                logger.warning("WebSocket send failed for connection %s: %s", conn_id, exc)
                dead.append(conn_id)

        for conn_id in dead:
            self.disconnect(conn_id)

        return sent

    async def send_to(self, conn_id: str, message: dict[str, Any]) -> None:
        """Send a message to a specific connection."""
        ws = self._connections.get(conn_id)
        if ws:
            try:
                await ws.send_text(json.dumps(message))
            except Exception as exc:
                logger.warning("WebSocket send_to failed for connection %s: %s", conn_id, exc)
                self.disconnect(conn_id)

    def wire_message_bus(self, bus: Any) -> None:
        """Subscribe to all MessageBus topics and forward to WebSocket clients.

        Uses wildcard '*' to capture all bus messages.
        """
        if self._bus_subscribed:
            return

        async def _on_bus_message(msg: Any) -> None:
            """Forward bus messages to subscribed WebSocket clients."""
            payload = {
                "id": msg.id,
                "sender": msg.sender,
                "payload": msg.payload,
                "priority": msg.priority.value if hasattr(msg.priority, "value") else msg.priority,
            }
            await self.broadcast(msg.topic, payload)

        bus.subscribe("*", "websocket_bridge", _on_bus_message)
        self._bus_subscribed = True
        logger.info("WebSocket bridge: wired to MessageBus (wildcard)")


# Global connection manager (singleton per app)
manager = ConnectionManager()


@router.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    conn_id = await manager.connect(websocket)

    # Wire to message bus on first connection (lazy init)
    bus = getattr(websocket.app.state, "bus", None)
    if bus:
        manager.wire_message_bus(bus)

    # Send welcome message with available topics
    await manager.send_to(conn_id, {
        "type": "connected",
        "connection_id": conn_id,
        "available_topics": [
            "system.*", "agent.*", "collab.*",
            "system.alert", "system.learning", "system.approval",
            "system.proposal", "system.trigger", "system.directive",
            "network.insight.*",
        ],
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_to(conn_id, {
                    "type": "error",
                    "message": "Invalid JSON",
                })
                continue

            # Handle subscribe
            if "subscribe" in msg and isinstance(msg["subscribe"], list):
                manager.subscribe(conn_id, msg["subscribe"])
                await manager.send_to(conn_id, {
                    "type": "subscribed",
                    "topics": list(manager._subscriptions.get(conn_id, set())),
                })

            # Handle unsubscribe
            elif "unsubscribe" in msg and isinstance(msg["unsubscribe"], list):
                manager.unsubscribe(conn_id, msg["unsubscribe"])
                await manager.send_to(conn_id, {
                    "type": "subscribed",
                    "topics": list(manager._subscriptions.get(conn_id, set())),
                })

            # Handle ping
            elif msg.get("ping"):
                await manager.send_to(conn_id, {"type": "pong"})

    except WebSocketDisconnect:
        manager.disconnect(conn_id)
    except Exception as exc:
        logger.error("WebSocket error for %s: %s", conn_id, exc)
        manager.disconnect(conn_id)
