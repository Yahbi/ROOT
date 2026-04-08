"""Tests for the Notification Engine — push alerts via Telegram/Discord."""

from __future__ import annotations

import pytest

from backend.core.notification_engine import NotificationEngine, Notification


class TestNotification:
    def test_mutable_for_read_tracking(self):
        n = Notification(title="Test", body="Body", level="high")
        assert n.read is False
        n.read = True
        assert n.read is True

    def test_defaults(self):
        n = Notification(title="T", body="B", level="low")
        assert n.source == "root"
        assert n.sent is False
        assert n.channel == ""
        assert n.read is False
        assert n.id  # Auto-generated
        assert len(n.id) == 12
        assert n.created_at  # Not empty


class TestNotificationEngine:
    def test_not_configured_without_tokens(self):
        engine = NotificationEngine()
        assert not engine.is_configured

    def test_configured_with_telegram(self):
        engine = NotificationEngine(
            telegram_bot_token="fake_token",
            telegram_chat_id="12345",
        )
        assert engine.is_configured

    def test_configured_with_discord(self):
        engine = NotificationEngine(discord_webhook_url="https://discord.com/webhook/123")
        assert engine.is_configured

    @pytest.mark.asyncio
    async def test_low_level_logged_only(self):
        engine = NotificationEngine()
        result = await engine.send("Test", "Body", level="low")
        assert result is True
        history = engine.get_history()
        assert len(history) == 1
        assert history[0]["level"] == "low"
        assert history[0]["sent"] is False

    @pytest.mark.asyncio
    async def test_medium_queued(self):
        engine = NotificationEngine()
        result = await engine.send("Test", "Body", level="medium")
        assert result is True
        stats = engine.stats()
        assert stats["pending_medium"] == 1

    @pytest.mark.asyncio
    async def test_high_without_channels(self):
        engine = NotificationEngine()
        result = await engine.send("Alert", "Something", level="high")
        # No channels configured, so send fails
        assert result is False

    def test_history_bounded(self):
        engine = NotificationEngine()
        # Manually fill history — maxlen is 500
        for i in range(600):
            engine._history.append(
                Notification(title=f"T{i}", body="B", level="low")
            )
        assert len(engine._history) <= 500

    def test_stats(self):
        engine = NotificationEngine(
            telegram_bot_token="tok",
            telegram_chat_id="123",
        )
        stats = engine.stats()
        assert stats["configured"] is True
        assert stats["telegram"] is True
        assert stats["discord"] is False
        assert stats["total_notifications"] == 0

    def test_get_history_limit(self):
        engine = NotificationEngine()
        for i in range(10):
            engine._history.append(
                Notification(title=f"T{i}", body="B", level="low")
            )
        history = engine.get_history(limit=3)
        assert len(history) == 3
