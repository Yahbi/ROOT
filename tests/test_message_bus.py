"""Tests for the Message Bus — pub/sub, history, wildcards."""

from __future__ import annotations

import asyncio

import pytest

from backend.core.message_bus import BusMessage, MessageBus, MessagePriority


@pytest.fixture
def bus():
    return MessageBus()


class TestMessageBusPublish:
    @pytest.mark.asyncio
    async def test_publish_and_subscribe(self, bus):
        received = []

        async def handler(msg):
            received.append(msg)

        bus.subscribe("test.topic", "test_sub", handler)
        msg = bus.create_message("test.topic", "sender", {"data": 1})
        await bus.publish(msg)
        assert len(received) == 1
        assert received[0].payload == {"data": 1}

    @pytest.mark.asyncio
    async def test_wildcard_subscribe(self, bus):
        received = []

        async def handler(msg):
            received.append(msg)

        bus.subscribe("agent.*", "test_sub", handler)
        msg = bus.create_message("agent.hermes.task", "sender", {})
        await bus.publish(msg)
        assert len(received) == 1

    @pytest.mark.asyncio
    async def test_no_match(self, bus):
        received = []

        async def handler(msg):
            received.append(msg)

        bus.subscribe("other.topic", "test_sub", handler)
        msg = bus.create_message("test.topic", "sender", {})
        await bus.publish(msg)
        assert len(received) == 0


class TestMessageBusHistory:
    @pytest.mark.asyncio
    async def test_history_bounded(self, bus):
        for i in range(600):
            msg = bus.create_message("test", "sender", {"i": i})
            await bus.publish(msg)
        assert len(bus._history) <= bus.MAX_HISTORY

    @pytest.mark.asyncio
    async def test_get_history_filtered(self, bus):
        await bus.publish(bus.create_message("a.topic", "sender1", {}))
        await bus.publish(bus.create_message("b.topic", "sender2", {}))
        history = bus.get_history(topic_filter="a.topic")
        assert len(history) == 1
        assert history[0].topic == "a.topic"


class TestMessageBusStats:
    @pytest.mark.asyncio
    async def test_stats(self, bus):
        bus.subscribe("test", "sub1", lambda m: None)
        stats = bus.stats()
        assert stats["active_subscriptions"] == 1
        assert stats["total_messages"] == 0
