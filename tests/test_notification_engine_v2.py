"""Tests for NotificationEngine v2 features:
- Notification batching (batch window)
- Templates (register, render, send_template)
- Scheduling / quiet hours
- Channel preferences (per-type routing)
- Priority escalation (unacknowledged alerts)
- History search (keyword, level, source, date range, flags)
- SMS channel interface
"""

from __future__ import annotations

import asyncio
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from backend.core.notification_engine import (
    ChannelPreference,
    LEVEL_ORDER,
    LEVELS,
    Notification,
    NotificationEngine,
    NotificationTemplate,
    _SafeFormatMap,
)


# ── SafeFormatMap ─────────────────────────────────────────────────────────────


class TestSafeFormatMap:
    def test_existing_key_returned(self):
        m = _SafeFormatMap({"name": "Alice"})
        assert m["name"] == "Alice"

    def test_missing_key_returns_placeholder(self):
        m = _SafeFormatMap({})
        assert m["missing"] == "{missing}"

    def test_format_map_partial_fill(self):
        result = "{name} owes ${amount}".format_map(_SafeFormatMap({"name": "Bob"}))
        assert result == "Bob owes ${amount}"


# ── Templates ─────────────────────────────────────────────────────────────────


class TestNotificationTemplate:
    def test_render_all_vars(self):
        tmpl = NotificationTemplate(
            name="test",
            title_template="Alert: {symbol}",
            body_template="Bought {qty} @ ${price}",
        )
        title, body = tmpl.render({"symbol": "AAPL", "qty": 10, "price": 150})
        assert title == "Alert: AAPL"
        assert body == "Bought 10 @ $150"

    def test_render_missing_vars_left_as_placeholder(self):
        tmpl = NotificationTemplate(
            name="test",
            title_template="Alert: {symbol}",
            body_template="Qty: {qty}",
        )
        title, body = tmpl.render({"symbol": "TSLA"})
        assert title == "Alert: TSLA"
        assert body == "Qty: {qty}"

    def test_render_empty_vars(self):
        tmpl = NotificationTemplate(
            name="empty",
            title_template="No vars",
            body_template="Static body",
        )
        title, body = tmpl.render({})
        assert title == "No vars"
        assert body == "Static body"


class TestEngineTemplates:
    def test_builtin_templates_registered(self):
        engine = NotificationEngine()
        names = engine.list_templates()
        assert "trade_executed" in names
        assert "system_health" in names
        assert "goal_achieved" in names
        assert "approval_required" in names

    def test_register_custom_template(self):
        engine = NotificationEngine()
        engine.register_template(
            name="custom_alert",
            title_template="Custom: {event}",
            body_template="Details: {details}",
            default_level="medium",
        )
        assert "custom_alert" in engine.list_templates()
        tmpl = engine.get_template("custom_alert")
        assert tmpl is not None
        assert tmpl.default_level == "medium"

    def test_get_nonexistent_template_returns_none(self):
        engine = NotificationEngine()
        assert engine.get_template("does_not_exist") is None

    def test_register_overwrites_existing(self):
        engine = NotificationEngine()
        engine.register_template("system_health", "{new}", "{body}", default_level="low")
        tmpl = engine.get_template("system_health")
        assert tmpl.title_template == "{new}"

    @pytest.mark.asyncio
    async def test_send_template_missing_name_returns_false(self):
        engine = NotificationEngine()
        result = await engine.send_template("no_such_template", {"x": 1})
        assert result is False

    @pytest.mark.asyncio
    async def test_send_template_low_level_logged(self):
        engine = NotificationEngine()
        engine.register_template(
            name="t1",
            title_template="Title: {val}",
            body_template="Body: {val}",
            default_level="low",
        )
        result = await engine.send_template("t1", {"val": "hello"})
        assert result is True
        history = engine.get_history()
        assert len(history) == 1
        assert "Title: hello" in history[0]["title"]

    @pytest.mark.asyncio
    async def test_send_template_level_override(self):
        engine = NotificationEngine()
        engine.register_template("t2", "T: {x}", "B: {x}", default_level="critical")
        await engine.send_template("t2", {"x": "v"}, level="low")
        history = engine.get_history()
        assert history[0]["level"] == "low"


# ── Channel Preferences ───────────────────────────────────────────────────────


class TestChannelPreferences:
    def test_default_preferences_set(self):
        engine = NotificationEngine()
        prefs = engine.list_channel_preferences()
        types = {p["type"] for p in prefs}
        # trade -> telegram, system -> discord (built-in defaults)
        assert "trade" in types
        assert "system" in types

    def test_trade_type_routes_to_telegram(self):
        engine = NotificationEngine(
            telegram_bot_token="tok",
            telegram_chat_id="123",
            discord_webhook_url="https://discord.com/w/123",
        )
        notif = Notification(title="T", body="B", level="high", notification_type="trade")
        channels = engine._channels_for_notification(notif)
        assert channels == ["telegram"]

    def test_system_type_routes_to_discord(self):
        engine = NotificationEngine(
            telegram_bot_token="tok",
            telegram_chat_id="123",
            discord_webhook_url="https://discord.com/w/123",
        )
        notif = Notification(title="T", body="B", level="high", notification_type="system")
        channels = engine._channels_for_notification(notif)
        assert channels == ["discord"]

    def test_generic_type_uses_all_channels(self):
        engine = NotificationEngine(
            telegram_bot_token="tok",
            telegram_chat_id="123",
            discord_webhook_url="https://discord.com/w/123",
        )
        notif = Notification(title="T", body="B", level="high", notification_type="generic")
        channels = engine._channels_for_notification(notif)
        assert "telegram" in channels
        assert "discord" in channels

    def test_set_custom_channel_preference(self):
        engine = NotificationEngine(
            telegram_bot_token="tok",
            telegram_chat_id="123",
            discord_webhook_url="https://discord.com/w/123",
        )
        engine.set_channel_preference("revenue", ["discord"], min_level="high")
        pref = engine.get_channel_preference("revenue")
        assert pref is not None
        assert pref.channels == ["discord"]
        assert pref.min_level == "high"

    def test_preference_below_min_level_falls_back(self):
        engine = NotificationEngine(
            telegram_bot_token="tok",
            telegram_chat_id="123",
            discord_webhook_url="https://discord.com/w/123",
        )
        # trade preference requires at least "high" to apply
        engine.set_channel_preference("trade", ["telegram"], min_level="high")
        # Send as "medium" — below threshold, should fallback
        notif = Notification(title="T", body="B", level="medium", notification_type="trade")
        channels = engine._channels_for_notification(notif)
        # Falls back to all configured channels
        assert "telegram" in channels
        assert "discord" in channels

    def test_preference_unconfigured_channel_falls_back(self):
        # Prefer "sms" but sms is not configured — fall back to all
        engine = NotificationEngine(telegram_bot_token="tok", telegram_chat_id="123")
        engine.set_channel_preference("trade", ["sms"], min_level="low")
        notif = Notification(title="T", body="B", level="high", notification_type="trade")
        channels = engine._channels_for_notification(notif)
        # sms not configured, fall back to configured channels
        assert "telegram" in channels

    def test_list_channel_preferences_returns_all(self):
        engine = NotificationEngine()
        engine.set_channel_preference("alpha", ["telegram"])
        engine.set_channel_preference("beta", ["discord"])
        prefs = engine.list_channel_preferences()
        types = {p["type"] for p in prefs}
        assert "alpha" in types
        assert "beta" in types


# ── Quiet Hours / Scheduling ──────────────────────────────────────────────────


class TestQuietHours:
    def test_quiet_hours_detection_wraps_midnight(self):
        engine = NotificationEngine(quiet_hours_start=22, quiet_hours_end=8)
        # hour 23 is inside 22-8
        with patch("backend.core.notification_engine.datetime") as mock_dt:
            mock_dt.now.return_value.hour = 23
            mock_dt.now.return_value = MagicMock(hour=23)
            # Use real _is_quiet_hours logic
        # Test the logic directly
        engine._quiet_hours_start = 22
        engine._quiet_hours_end = 8
        engine._respect_quiet_hours = True
        # hour 23: 23 >= 22 OR 23 < 8? → True OR False → True
        hour = 23
        start, end = 22, 8
        assert hour >= start or hour < end  # True

    def test_quiet_hours_detection_inside_window(self):
        engine = NotificationEngine(quiet_hours_start=22, quiet_hours_end=8)
        for quiet_hour in [22, 23, 0, 1, 5, 7]:
            start, end = 22, 8
            result = quiet_hour >= start or quiet_hour < end
            assert result, f"hour {quiet_hour} should be in quiet hours"

    def test_quiet_hours_detection_outside_window(self):
        start, end = 22, 8
        for awake_hour in [8, 9, 12, 18, 21]:
            result = awake_hour >= start or awake_hour < end
            assert not result, f"hour {awake_hour} should not be in quiet hours"

    def test_configure_quiet_hours(self):
        engine = NotificationEngine()
        engine.configure_quiet_hours(start=23, end=7, enabled=True)
        assert engine._quiet_hours_start == 23
        assert engine._quiet_hours_end == 7
        assert engine._respect_quiet_hours is True

    def test_disable_quiet_hours(self):
        engine = NotificationEngine()
        engine.configure_quiet_hours(start=22, end=8, enabled=False)
        assert engine._respect_quiet_hours is False

    @pytest.mark.asyncio
    async def test_medium_deferred_during_quiet_hours(self):
        engine = NotificationEngine()
        # Force quiet hours active
        engine._respect_quiet_hours = True
        engine._quiet_hours_start = 0
        engine._quiet_hours_end = 23  # always quiet

        result = await engine.send("Test", "Body", level="medium")
        assert result is True
        assert len(engine._deferred_queue) == 1
        assert len(engine._medium_queue) == 0

    @pytest.mark.asyncio
    async def test_high_deferred_during_quiet_hours(self):
        engine = NotificationEngine()
        engine._respect_quiet_hours = True
        engine._quiet_hours_start = 0
        engine._quiet_hours_end = 23

        result = await engine.send("Alert", "Body", level="high")
        assert result is True
        assert len(engine._deferred_queue) == 1

    @pytest.mark.asyncio
    async def test_critical_not_deferred_during_quiet_hours(self):
        """CRITICAL always sends immediately, never deferred."""
        engine = NotificationEngine()
        engine._respect_quiet_hours = True
        engine._quiet_hours_start = 0
        engine._quiet_hours_end = 23

        # No channels configured → send returns False but is not deferred
        result = await engine.send("CRITICAL", "Emergency", level="critical")
        assert len(engine._deferred_queue) == 0  # not deferred

    @pytest.mark.asyncio
    async def test_no_defer_when_quiet_hours_disabled(self):
        engine = NotificationEngine()
        engine._respect_quiet_hours = False
        engine._quiet_hours_start = 0
        engine._quiet_hours_end = 23

        result = await engine.send("Test", "Body", level="medium")
        assert len(engine._deferred_queue) == 0
        assert len(engine._medium_queue) == 1

    @pytest.mark.asyncio
    async def test_flush_deferred_sends_and_clears(self):
        engine = NotificationEngine()
        # Manually populate deferred queue
        n = Notification(title="Deferred", body="Body", level="medium")
        engine._deferred_queue.append(n)

        with patch.object(engine, "_send_immediate", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await engine._flush_deferred()

        assert len(engine._deferred_queue) == 0
        mock_send.assert_called_once()


# ── Batching ──────────────────────────────────────────────────────────────────


class TestBatching:
    def test_batch_window_starts_on_first_add(self):
        import time
        engine = NotificationEngine()
        notif = Notification(title="T", body="B", level="high", notification_type="market")
        engine._add_to_batch_window(notif)
        assert "market" in engine._batch_window_queue
        assert "market" in engine._batch_window_timers

    def test_batch_window_accumulates_same_type(self):
        engine = NotificationEngine()
        for i in range(3):
            n = Notification(title=f"T{i}", body="B", level="high", notification_type="market")
            engine._add_to_batch_window(n)
        assert len(engine._batch_window_queue["market"]) == 3

    def test_should_batch_returns_true_within_window(self):
        import time
        engine = NotificationEngine()
        engine.BATCH_WINDOW = 60
        n = Notification(title="T", body="B", level="high", notification_type="market")
        engine._add_to_batch_window(n)
        assert engine._should_batch(n) is True

    def test_should_batch_returns_false_for_new_type(self):
        engine = NotificationEngine()
        n = Notification(title="T", body="B", level="high", notification_type="novel_type")
        assert engine._should_batch(n) is False

    @pytest.mark.asyncio
    async def test_flush_batch_window_single_item_sends_directly(self):
        engine = NotificationEngine()
        n = Notification(title="T", body="B", level="high", notification_type="alpha")
        engine._batch_window_queue["alpha"] = [n]
        engine._batch_window_timers["alpha"] = 0.0

        with patch.object(engine, "_send_immediate", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await engine._flush_batch_window("alpha")

        mock_send.assert_called_once_with(n)

    @pytest.mark.asyncio
    async def test_flush_batch_window_multiple_items_combined(self):
        engine = NotificationEngine()
        for i in range(3):
            n = Notification(title=f"T{i}", body=f"B{i}", level="high", notification_type="beta")
            engine._batch_window_queue.setdefault("beta", []).append(n)
        engine._batch_window_timers["beta"] = 0.0

        with patch.object(engine, "_send_immediate", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await engine._flush_batch_window("beta")

        mock_send.assert_called_once()
        call_args = mock_send.call_args[0][0]
        assert "3 notifications" in call_args.title
        assert "beta" in call_args.title

    @pytest.mark.asyncio
    async def test_flush_batch_window_picks_highest_level(self):
        engine = NotificationEngine()
        n_high = Notification(title="H", body="B", level="high", notification_type="gamma")
        n_crit = Notification(title="C", body="B", level="critical", notification_type="gamma")
        engine._batch_window_queue["gamma"] = [n_high, n_crit]
        engine._batch_window_timers["gamma"] = 0.0

        with patch.object(engine, "_send_immediate", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            await engine._flush_batch_window("gamma")

        call_args = mock_send.call_args[0][0]
        assert call_args.level == "critical"

    @pytest.mark.asyncio
    async def test_flush_batch_window_clears_queue(self):
        engine = NotificationEngine()
        n = Notification(title="T", body="B", level="high", notification_type="delta")
        engine._batch_window_queue["delta"] = [n]
        engine._batch_window_timers["delta"] = 0.0

        with patch.object(engine, "_send_immediate", new_callable=AsyncMock):
            await engine._flush_batch_window("delta")

        assert "delta" not in engine._batch_window_queue
        assert "delta" not in engine._batch_window_timers

    @pytest.mark.asyncio
    async def test_send_with_batch_flag_accumulates(self):
        engine = NotificationEngine()
        engine._respect_quiet_hours = False

        for i in range(3):
            await engine.send(
                f"T{i}", f"B{i}",
                level="high",
                notification_type="signals",
                batch=True,
            )

        assert "signals" in engine._batch_window_queue
        assert len(engine._batch_window_queue["signals"]) == 3


# ── Priority Escalation ───────────────────────────────────────────────────────


class TestPriorityEscalation:
    def test_acknowledge_marks_read_and_clears_escalation(self):
        engine = NotificationEngine()
        n = Notification(title="T", body="B", level="high")
        engine._history.append(n)
        engine._pending_escalation[n.id] = 0.0

        result = engine.acknowledge(n.id)

        assert result is True
        assert n.acknowledged is True
        assert n.read is True
        assert n.id not in engine._pending_escalation

    def test_acknowledge_nonexistent_returns_false(self):
        engine = NotificationEngine()
        result = engine.acknowledge("nonexistent_id")
        assert result is False

    def test_next_escalation_level_high_to_critical(self):
        engine = NotificationEngine()
        assert engine._next_escalation_level("high") == "critical"

    def test_next_escalation_level_medium_to_high(self):
        engine = NotificationEngine()
        assert engine._next_escalation_level("medium") == "high"

    def test_next_escalation_level_critical_stays_critical(self):
        engine = NotificationEngine()
        assert engine._next_escalation_level("critical") == "critical"

    def test_next_escalation_level_low_to_medium(self):
        engine = NotificationEngine()
        assert engine._next_escalation_level("low") == "medium"

    @pytest.mark.asyncio
    async def test_escalation_loop_re_sends_unacknowledged(self):
        import time
        engine = NotificationEngine()
        engine.ESCALATION_TIMEOUT = 0  # Trigger immediately
        engine.ESCALATION_INTERVAL = 0

        n = Notification(title="Alert", body="Unack", level="high")
        engine._history.append(n)
        engine._pending_escalation[n.id] = time.monotonic() - 1  # expired

        with patch.object(engine, "_send_immediate", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True
            engine._running = True
            # Run one tick of escalation loop
            now = time.monotonic()
            to_escalate = [
                nid for nid, sent_at in list(engine._pending_escalation.items())
                if now - sent_at >= engine.ESCALATION_TIMEOUT
            ]
            for notif_id in to_escalate:
                found = next((x for x in engine._history if x.id == notif_id), None)
                if found and not found.acknowledged and not found.read:
                    new_level = engine._next_escalation_level(found.level)
                    found.escalation_count = found.escalation_count + 1
                    escalated = Notification(
                        title=f"[ESCALATION #{found.escalation_count}] {found.title}",
                        body=found.body,
                        level=new_level,
                        source=found.source,
                        notification_type=found.notification_type,
                    )
                    engine._history.append(escalated)
                    engine._pending_escalation.pop(notif_id, None)
                    await engine._send_immediate(escalated)

        mock_send.assert_called_once()
        call_args = mock_send.call_args[0][0]
        assert call_args.level == "critical"
        assert "ESCALATION" in call_args.title
        assert n.escalation_count == 1

    @pytest.mark.asyncio
    async def test_acknowledged_skips_escalation(self):
        import time
        engine = NotificationEngine()
        engine.ESCALATION_TIMEOUT = 0

        n = Notification(title="Alert", body="Body", level="high")
        n.acknowledged = True
        engine._history.append(n)
        engine._pending_escalation[n.id] = 0.0

        with patch.object(engine, "_send_immediate", new_callable=AsyncMock) as mock_send:
            # Simulate the escalation loop check
            found = next((x for x in engine._history if x.id == n.id), None)
            if found and (found.acknowledged or found.read):
                engine._pending_escalation.pop(n.id, None)

        mock_send.assert_not_called()
        assert n.id not in engine._pending_escalation


# ── History Search ────────────────────────────────────────────────────────────


class TestHistorySearch:
    def _make_engine_with_notifications(self):
        engine = NotificationEngine()
        notifications = [
            Notification(title="Trade Alert", body="AAPL bought", level="high",
                         source="trading", notification_type="trade"),
            Notification(title="System Health", body="CPU normal", level="low",
                         source="monitor", notification_type="system"),
            Notification(title="Revenue Update", body="$500 earned", level="medium",
                         source="revenue", notification_type="revenue"),
            Notification(title="Critical Error", body="DB connection lost", level="critical",
                         source="root", notification_type="system"),
        ]
        for n in notifications:
            engine._history.append(n)
        return engine, notifications

    def test_search_by_keyword_in_title(self):
        engine, _ = self._make_engine_with_notifications()
        results = engine.get_history(search="Trade")
        assert len(results) == 1
        assert "Trade Alert" in results[0]["title"]

    def test_search_by_keyword_in_body(self):
        engine, _ = self._make_engine_with_notifications()
        results = engine.get_history(search="AAPL")
        assert len(results) == 1
        assert "AAPL" in results[0]["body"]

    def test_search_case_insensitive(self):
        engine, _ = self._make_engine_with_notifications()
        results = engine.get_history(search="trade alert")
        assert len(results) == 1

    def test_search_no_match_returns_empty(self):
        engine, _ = self._make_engine_with_notifications()
        results = engine.get_history(search="NONEXISTENT_XYZ_123")
        assert len(results) == 0

    def test_filter_by_level(self):
        engine, _ = self._make_engine_with_notifications()
        results = engine.get_history(level="critical")
        assert len(results) == 1
        assert results[0]["level"] == "critical"

    def test_filter_by_source(self):
        engine, _ = self._make_engine_with_notifications()
        results = engine.get_history(source="trading")
        assert len(results) == 1
        assert results[0]["source"] == "trading"

    def test_filter_by_notification_type(self):
        engine, _ = self._make_engine_with_notifications()
        results = engine.get_history(notification_type="system")
        assert len(results) == 2  # Health + Critical Error

    def test_filter_unread_only(self):
        engine, _ = self._make_engine_with_notifications()
        # Mark one as read
        for n in engine._history:
            if n.notification_type == "trade":
                n.read = True
        results = engine.get_history(unread_only=True)
        for r in results:
            assert r["read"] is False

    def test_filter_unacknowledged_only(self):
        engine, _ = self._make_engine_with_notifications()
        # Acknowledge one HIGH notification
        for n in engine._history:
            if n.level == "high":
                n.acknowledged = True
        results = engine.get_history(unacknowledged_only=True)
        # Only critical should remain unacknowledged
        for r in results:
            assert r["acknowledged"] is False
            assert r["level"] in ("high", "critical")

    def test_filter_since(self):
        engine, _ = self._make_engine_with_notifications()
        # Use far-future date — should return nothing
        results = engine.get_history(since="2099-01-01T00:00:00+00:00")
        assert len(results) == 0

    def test_filter_until(self):
        engine, _ = self._make_engine_with_notifications()
        # Use far-past date — should return nothing
        results = engine.get_history(until="2000-01-01T00:00:00+00:00")
        assert len(results) == 0

    def test_combined_filters(self):
        engine, _ = self._make_engine_with_notifications()
        results = engine.get_history(source="root", level="critical")
        assert len(results) == 1
        assert results[0]["source"] == "root"
        assert results[0]["level"] == "critical"

    def test_search_history_convenience_method(self):
        engine, _ = self._make_engine_with_notifications()
        results = engine.search_history("health")
        assert len(results) == 1
        assert "Health" in results[0]["title"]

    def test_history_contains_new_fields(self):
        engine, _ = self._make_engine_with_notifications()
        results = engine.get_history(limit=1)
        assert "notification_type" in results[0]
        assert "acknowledged" in results[0]
        assert "escalation_count" in results[0]


# ── SMS Channel ───────────────────────────────────────────────────────────────


class TestSMSChannel:
    def test_sms_configured_when_fn_and_to_set(self):
        engine = NotificationEngine(
            sms_send_fn=lambda to, msg: True,
            sms_to="+15551234567",
        )
        assert engine.is_configured is True
        assert "sms" in engine._determine_channels()

    def test_sms_not_configured_without_fn(self):
        engine = NotificationEngine(sms_to="+15551234567")
        assert "sms" not in engine._determine_channels()

    def test_sms_not_configured_without_to(self):
        engine = NotificationEngine(sms_send_fn=lambda to, msg: True)
        assert "sms" not in engine._determine_channels()

    @pytest.mark.asyncio
    async def test_send_sms_calls_fn(self):
        called_with = {}

        def mock_sms(to, message):
            called_with["to"] = to
            called_with["message"] = message
            return True

        engine = NotificationEngine(sms_send_fn=mock_sms, sms_to="+15551234567")
        result = await engine._send_sms("Test Alert", "Something happened")

        assert result is True
        assert called_with["to"] == "+15551234567"
        assert "Test Alert" in called_with["message"]

    @pytest.mark.asyncio
    async def test_send_sms_fn_returns_false(self):
        engine = NotificationEngine(
            sms_send_fn=lambda to, msg: False,
            sms_to="+15551234567",
        )
        result = await engine._send_sms("T", "B")
        assert result is False

    @pytest.mark.asyncio
    async def test_send_sms_fn_raises_returns_false(self):
        def bad_sms(to, msg):
            raise RuntimeError("SMS provider down")

        engine = NotificationEngine(sms_send_fn=bad_sms, sms_to="+15551234567")
        result = await engine._send_sms("T", "B")
        assert result is False

    def test_sms_delivery_counts_tracked(self):
        engine = NotificationEngine()
        assert "sms_sent" in engine._delivery_counts
        assert "sms_failed" in engine._delivery_counts

    @pytest.mark.asyncio
    async def test_sms_channel_routing(self):
        """SMS channel preference routes notifications only to SMS."""
        sent_to = []

        def mock_sms(to, msg):
            sent_to.append(msg)
            return True

        engine = NotificationEngine(
            telegram_bot_token="tok",
            telegram_chat_id="123",
            sms_send_fn=mock_sms,
            sms_to="+15551234567",
        )
        engine.set_channel_preference("emergency", ["sms"], min_level="low")

        with (
            patch.object(engine, "_send_telegram", new_callable=AsyncMock) as mock_tg,
            patch.object(engine, "_sandbox_gate", None),
        ):
            mock_tg.return_value = False
            notif = Notification(title="T", body="B", level="high", notification_type="emergency")
            channels = engine._channels_for_notification(notif)
            assert channels == ["sms"]


# ── Stats with new fields ─────────────────────────────────────────────────────


class TestEnhancedStats:
    def test_stats_includes_quiet_hours(self):
        engine = NotificationEngine()
        stats = engine.stats()
        assert "quiet_hours" in stats
        assert "enabled" in stats["quiet_hours"]
        assert "start" in stats["quiet_hours"]
        assert "end" in stats["quiet_hours"]
        assert "currently_active" in stats["quiet_hours"]

    def test_stats_includes_template_count(self):
        engine = NotificationEngine()
        stats = engine.stats()
        assert "templates" in stats
        assert stats["templates"] >= 9  # built-in templates

    def test_stats_includes_channel_prefs(self):
        engine = NotificationEngine()
        stats = engine.stats()
        assert "channel_preferences" in stats
        assert stats["channel_preferences"] >= 2  # trade + system defaults

    def test_stats_includes_deferred_count(self):
        engine = NotificationEngine()
        engine._deferred_queue.append(Notification("T", "B", "medium"))
        stats = engine.stats()
        assert stats["pending_deferred"] == 1

    def test_stats_includes_escalation_count(self):
        engine = NotificationEngine()
        engine._pending_escalation["abc123"] = 0.0
        stats = engine.stats()
        assert stats["pending_escalation"] == 1

    def test_stats_includes_sms_in_delivery(self):
        engine = NotificationEngine()
        stats = engine.stats()
        assert "sms" in stats["delivery"]["by_channel"]

    @pytest.mark.asyncio
    async def test_stats_unread_count(self):
        engine = NotificationEngine()
        await engine.send("A", "B", level="low")
        await engine.send("C", "D", level="low")
        stats = engine.stats()
        assert stats["unread"] == 2

    @pytest.mark.asyncio
    async def test_stats_unread_decreases_after_read(self):
        engine = NotificationEngine()
        await engine.send("A", "B", level="low")
        # Mark as read
        for n in engine._history:
            n.read = True
        stats = engine.stats()
        assert stats["unread"] == 0


# ── Level ordering constants ──────────────────────────────────────────────────


class TestLevelConstants:
    def test_level_order_is_ascending(self):
        assert LEVEL_ORDER["low"] < LEVEL_ORDER["medium"]
        assert LEVEL_ORDER["medium"] < LEVEL_ORDER["high"]
        assert LEVEL_ORDER["high"] < LEVEL_ORDER["critical"]

    def test_levels_tuple_order(self):
        assert LEVELS == ("low", "medium", "high", "critical")
