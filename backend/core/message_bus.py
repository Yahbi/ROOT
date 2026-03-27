"""
Message Bus — Inter-agent pub/sub communication system.

Inspired by HERMES delegation + YOHAN-Command-Center orchestration.
Agents can publish messages, subscribe to topics, and communicate
with each other without direct coupling.

Topics:
- agent.{id}.task       — task assigned to agent
- agent.{id}.result     — agent completed a task
- agent.{id}.request    — agent requesting help from another
- system.alert          — system-wide alerts
- system.learning       — new knowledge discovered
- system.approval       — tasks needing Yohan's approval
- collab.{workflow_id}  — collaboration workflow messages
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger("root.message_bus")


class MessagePriority(int, Enum):
    CRITICAL = 1
    HIGH = 3
    NORMAL = 5
    LOW = 7
    BACKGROUND = 9


@dataclass(frozen=True)
class BusMessage:
    """Immutable message on the bus."""
    id: str
    topic: str
    sender: str
    payload: dict[str, Any]
    priority: MessagePriority = MessagePriority.NORMAL
    reply_to: Optional[str] = None  # message id this replies to
    correlation_id: Optional[str] = None  # groups related messages
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# Type alias for async handlers
Handler = Callable[[BusMessage], Coroutine[Any, Any, None]]


class MessageBus:
    """Async pub/sub message bus for inter-agent communication.

    Pattern: agents subscribe to topic patterns, publish messages.
    Supports exact topics and wildcard prefixes (agent.* matches agent.coder.task).
    """

    MAX_HISTORY = 500  # Keep last N messages for replay

    def __init__(self) -> None:
        self._subscribers: dict[str, list[tuple[str, Handler]]] = defaultdict(list)
        self._history: deque[BusMessage] = deque(maxlen=self.MAX_HISTORY)
        self._pending_replies: dict[str, asyncio.Future[BusMessage]] = {}
        self._message_count = 0

    def subscribe(self, topic_pattern: str, subscriber_id: str, handler: Handler) -> None:
        """Subscribe to a topic pattern. Supports wildcards: 'agent.*' matches 'agent.coder.task'."""
        self._subscribers[topic_pattern].append((subscriber_id, handler))
        logger.debug("Subscribed %s to %s", subscriber_id, topic_pattern)

    def unsubscribe(self, topic_pattern: str, subscriber_id: str) -> None:
        """Remove a subscriber from a topic."""
        if topic_pattern in self._subscribers:
            self._subscribers[topic_pattern] = [
                (sid, h) for sid, h in self._subscribers[topic_pattern]
                if sid != subscriber_id
            ]

    async def publish(self, message: BusMessage) -> None:
        """Publish a message to all matching subscribers."""
        self._message_count += 1

        # Store in history (bounded by deque maxlen)
        self._history.append(message)

        # Resolve pending reply futures
        if message.reply_to and message.reply_to in self._pending_replies:
            future = self._pending_replies.pop(message.reply_to)
            if not future.done():
                try:
                    future.set_result(message)
                except asyncio.InvalidStateError:
                    logger.warning("Future already resolved for reply %s", message.reply_to)

        # Find matching subscribers
        handlers = self._get_matching_handlers(message.topic)

        if not handlers:
            logger.debug("No subscribers for topic: %s", message.topic)
            return

        # Fire all handlers concurrently
        tasks = [handler(message) for _, handler in handlers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                sub_id = handlers[i][0]
                logger.error("Handler %s failed on %s: %s", sub_id, message.topic, result)

    async def request(
        self,
        topic: str,
        sender: str,
        payload: dict[str, Any],
        timeout: float = 30.0,
    ) -> Optional[BusMessage]:
        """Publish a message and wait for a reply (request/response pattern)."""
        msg_id = f"msg_{uuid.uuid4().hex[:12]}"
        future: asyncio.Future[BusMessage] = asyncio.get_event_loop().create_future()
        self._pending_replies[msg_id] = future

        message = BusMessage(
            id=msg_id,
            topic=topic,
            sender=sender,
            payload=payload,
        )
        await self.publish(message)

        try:
            return await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._pending_replies.pop(msg_id, None)
            logger.warning("Request timeout on %s from %s", topic, sender)
            return None

    def create_message(
        self,
        topic: str,
        sender: str,
        payload: dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        reply_to: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> BusMessage:
        """Factory for creating a new message."""
        return BusMessage(
            id=f"msg_{uuid.uuid4().hex[:12]}",
            topic=topic,
            sender=sender,
            payload=payload,
            priority=priority,
            reply_to=reply_to,
            correlation_id=correlation_id,
        )

    def get_history(
        self,
        topic_filter: Optional[str] = None,
        sender_filter: Optional[str] = None,
        limit: int = 50,
    ) -> list[BusMessage]:
        """Get recent messages, optionally filtered."""
        all_msgs: list[BusMessage] = list(self._history)
        if topic_filter:
            all_msgs = [m for m in all_msgs if self._topic_matches(topic_filter, m.topic)]
        if sender_filter:
            all_msgs = [m for m in all_msgs if m.sender == sender_filter]
        result: list[BusMessage] = []
        for msg in reversed(all_msgs):
            if len(result) >= limit:
                break
            result.append(msg)
        return result

    def stats(self) -> dict[str, Any]:
        """Bus statistics."""
        return {
            "total_messages": self._message_count,
            "history_size": len(self._history),
            "active_subscriptions": sum(len(subs) for subs in self._subscribers.values()),
            "topics_with_subscribers": len(self._subscribers),
            "pending_replies": len(self._pending_replies),
        }

    # ── Internal ─────────────────────────────────────────────────

    def _get_matching_handlers(self, topic: str) -> list[tuple[str, Handler]]:
        """Find all handlers whose pattern matches the topic."""
        matched: list[tuple[str, Handler]] = []
        for pattern, handlers in self._subscribers.items():
            if self._topic_matches(pattern, topic):
                matched.extend(handlers)
        return matched

    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        """Check if a topic matches a pattern. Supports '*' wildcard at end."""
        if pattern == topic:
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return topic.startswith(prefix + ".")
        if pattern == "*":
            return True
        return False
