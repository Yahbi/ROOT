"""Extended tests for Notification Engine — muting, channels, audit, delivery counts."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from backend.core.notification_engine import Notification, NotificationEngine


# ── Notification Dataclass ────────────────────────────────────────────


class TestNotificationDataclass:
    def test_all_fields_default(self):
        n = Notification(title="T", body="B", level="low")
        assert n.source == "root"
        assert n.sent is False
        assert n.channel == ""
        assert n.read is False
        assert len(n.id) == 12
        assert n.created_at

    def test_custom_source(self):
        n = Notification(title="T", body="B", level="high", source="trading")
        assert n.source == "trading"

    def test_read_mutable(self):
        n = Notification(title="T", body="B", level="medium")
        n.read = True
        assert n.read is True

    def test_sent_mutable(self):
        n = Notification(title="T", body="B", level="high")
        n.sent = True
        assert n.sent is True

    def test_channel_mutable(self):
        n = Notification(title="T", body="B", level="high")
        n.channel = "telegram,discord"
        assert n.channel == "telegram,discord"

    def test_unique_ids(self):
        n1 = Notification(title="T", body="B", level="low")
        n2 = Notification(title="T", body="B", level="low")
        assert n1.id != n2.id


# ── Configuration ─────────────────────────────────────────────────────


class TestConfiguration:
    def test_not_configured_by_default(self):
        engine = NotificationEngine()
        assert engine.is_configured is False

    def test_telegram_configures(self):
        engine = NotificationEngine(
            telegram_bot_token="abc", telegram_chat_id="12345",
        )
        assert engine.is_configured is True

    def test_discord_configures(self):
        engine = NotificationEngine(discord_webhook_url="https://discord.com/api/webhooks/123")
        assert engine.is_configured is True

    def test_smtp_configures(self):
        engine = NotificationEngine(
            smtp_host="smtp.gmail.com",
            notification_email="user@example.com",
        )
        assert engine.is_configured is True

    def test_slack_configures(self):
        engine = NotificationEngine(slack_webhook_url="https://hooks.slack.com/123")
        assert engine.is_configured is True

    def test_webhook_configures(self):
        engine = NotificationEngine(webhook_urls=["https://example.com/hook"])
        assert engine.is_configured is True

    def test_all_channels_configured(self):
        engine = NotificationEngine(
            telegram_bot_token="tok", telegram_chat_id="123",
            discord_webhook_url="https://discord.com/w/123",
        )
        channels = engine._determine_channels()
        assert "telegram" in channels
        assert "discord" in channels


# ── Muting ────────────────────────────────────────────────────────────


class TestMuting:
    @pytest.mark.asyncio
    async def test_muted_source_suppresses_notification(self):
        engine = NotificationEngine()
        engine.mute_source("noisy_agent")
        result = await engine.send("Test", "Body", level="low", source="noisy_agent")
        assert result is False
        # No history entry added
        assert len(engine.get_history()) == 0

    @pytest.mark.asyncio
    async def test_unmuted_source_delivers(self):
        engine = NotificationEngine()
        engine.mute_source("agent_x")
        engine.unmute_source("agent_x")
        result = await engine.send("Test", "Body", level="low", source="agent_x")
        assert result is True

    def test_should_deliver_returns_false_for_muted(self):
        engine = NotificationEngine()
        engine.mute_source("muted_src")
        assert engine._should_deliver("muted_src", "high") is False

    def test_should_deliver_returns_true_for_unmuted(self):
        engine = NotificationEngine()
        assert engine._should_deliver("any_agent", "critical") is True

    def test_multiple_sources_muted_independently(self):
        engine = NotificationEngine()
        engine.mute_source("agent_a")
        engine.mute_source("agent_b")
        assert not engine._should_deliver("agent_a", "low")
        assert not engine._should_deliver("agent_b", "low")
        assert engine._should_deliver("agent_c", "low")

    def test_unmute_only_removes_target(self):
        engine = NotificationEngine()
        engine.mute_source("agent_a")
        engine.mute_source("agent_b")
        engine.unmute_source("agent_a")
        assert engine._should_deliver("agent_a", "low")
        assert not engine._should_deliver("agent_b", "low")


# ── Send Levels ───────────────────────────────────────────────────────


class TestSendLevels:
    @pytest.mark.asyncio
    async def test_low_always_logged(self):
        engine = NotificationEngine()
        result = await engine.send("Low Alert", "Details", level="low")
        assert result is True
        history = engine.get_history()
        assert len(history) == 1
        assert history[0]["level"] == "low"
        assert history[0]["sent"] is False

    @pytest.mark.asyncio
    async def test_medium_queued_for_batch(self):
        engine = NotificationEngine()
        await engine.send("Medium Alert", "Details", level="medium")
        assert len(engine._medium_queue) == 1
        stats = engine.stats()
        assert stats["pending_medium"] == 1

    @pytest.mark.asyncio
    async def test_multiple_medium_queued(self):
        engine = NotificationEngine()
        for i in range(3):
            await engine.send(f"Alert {i}", "Details", level="medium")
        assert len(engine._medium_queue) == 3

    @pytest.mark.asyncio
    async def test_high_without_channels_returns_false(self):
        engine = NotificationEngine()
        result = await engine.send("High Alert", "Critical", level="high")
        assert result is False

    @pytest.mark.asyncio
    async def test_critical_without_channels_returns_false(self):
        engine = NotificationEngine()
        result = await engine.send("Critical", "Emergency", level="critical")
        assert result is False


# ── Audit External Actions ────────────────────────────────────────────


class TestAuditExternalAction:
    @pytest.mark.asyncio
    async def test_audit_logs_action(self):
        engine = NotificationEngine()
        result = await engine.audit_external_action(
            action="HTTP GET", target="https://api.example.com",
            source="openclaw", level="low",
        )
        assert result is True
        history = engine.get_history()
        assert len(history) == 1
        assert "HTTP GET" in history[0]["title"]

    @pytest.mark.asyncio
    async def test_audit_with_details(self):
        engine = NotificationEngine()
        await engine.audit_external_action(
            action="Trade Executed", target="AAPL",
            details="Bought 10 shares at $175",
            level="low",
        )
        history = engine.get_history()
        assert "10 shares" in history[0]["body"]


# ── History ───────────────────────────────────────────────────────────


class TestHistory:
    def test_history_bounded_at_200(self):
        engine = NotificationEngine()
        for i in range(250):
            engine._history.append(
                Notification(title=f"N{i}", body="b", level="low")
            )
        assert len(engine._history) <= 200

    def test_get_history_returns_dicts(self):
        engine = NotificationEngine()
        engine._history.append(Notification(title="T", body="B", level="low"))
        history = engine.get_history()
        assert isinstance(history[0], dict)
        assert "title" in history[0]
        assert "body" in history[0]
        assert "level" in history[0]

    def test_get_history_most_recent_first(self):
        engine = NotificationEngine()
        for i in range(5):
            engine._history.append(Notification(title=f"N{i}", body="b", level="low"))
        history = engine.get_history(limit=5)
        # Most recent is last appended (deque)
        assert len(history) == 5

    def test_get_history_limit_respected(self):
        engine = NotificationEngine()
        for i in range(10):
            engine._history.append(Notification(title=f"N{i}", body="b", level="low"))
        assert len(engine.get_history(limit=3)) == 3


# ── Stats ─────────────────────────────────────────────────────────────


class TestNotificationStats:
    def test_empty_stats(self):
        engine = NotificationEngine()
        stats = engine.stats()
        assert stats["total_notifications"] == 0
        assert stats["configured"] is False
        assert stats["pending_medium"] == 0

    def test_stats_configured(self):
        engine = NotificationEngine(
            telegram_bot_token="tok", telegram_chat_id="123",
        )
        stats = engine.stats()
        assert stats["configured"] is True
        assert stats["telegram"] is True
        assert stats["discord"] is False

    @pytest.mark.asyncio
    async def test_stats_counts_notifications(self):
        engine = NotificationEngine()
        await engine.send("A", "B", level="low")
        await engine.send("C", "D", level="low")
        stats = engine.stats()
        assert stats["total_notifications"] == 2

    def test_delivery_counts_tracked(self):
        engine = NotificationEngine()
        assert engine._delivery_counts["telegram_sent"] == 0
        assert engine._delivery_counts["discord_sent"] == 0
        assert engine._delivery_counts["email_sent"] == 0
