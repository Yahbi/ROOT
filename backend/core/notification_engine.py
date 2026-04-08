"""
Notification Engine — push alerts to Yohan via Telegram, Discord, Email, Slack, and webhooks.

Levels:
- CRITICAL / HIGH: send immediately
- MEDIUM: batch into digest (30 min)
- LOW: log only (no push)

Features:
- Notification batching: group multiple notifications within a configurable time window
- Notification templates: reusable templates with variable substitution
- Notification scheduling: quiet hours support (defer during configured window)
- Notification channels: email, webhook, SMS interface stubs + per-channel routing
- Priority escalation: unacknowledged HIGH/CRITICAL alerts re-sent at louder level
- History with search: search by keyword, level, source, and date range
- Per-type preferences: route notification types to specific channels
"""

from __future__ import annotations

import asyncio
import logging
import re
import smtplib
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Callable, Optional

logger = logging.getLogger("root.notifications")

# ── Constants ────────────────────────────────────────────────────────────────

LEVELS = ("low", "medium", "high", "critical")
LEVEL_ORDER = {level: i for i, level in enumerate(LEVELS)}

# Built-in templates: name -> (title_template, body_template)
_BUILTIN_TEMPLATES: dict[str, tuple[str, str]] = {
    "trade_executed": (
        "Trade Executed: {symbol}",
        "Action: {action}\nQty: {qty} @ ${price}\nPortfolio impact: {impact}",
    ),
    "trade_failed": (
        "Trade Failed: {symbol}",
        "Reason: {reason}\nAttempted: {action} {qty} shares",
    ),
    "system_health": (
        "System Health: {status}",
        "Component: {component}\nDetails: {details}",
    ),
    "goal_achieved": (
        "Goal Achieved: {goal_name}",
        "Completed in {duration}\nOutcome: {outcome}",
    ),
    "goal_stalled": (
        "Goal Stalled: {goal_name}",
        "Last progress: {last_progress}\nSuggested action: {action}",
    ),
    "revenue_update": (
        "Revenue Update: {stream}",
        "Amount: ${amount}\nTotal this month: ${monthly_total}\nTarget: ${target}",
    ),
    "approval_required": (
        "Approval Required: {action}",
        "Source: {source}\nReason: {reason}\nRisk: {risk}",
    ),
    "experiment_result": (
        "Experiment {status}: {name}",
        "Hypothesis: {hypothesis}\nResult: {result}\nAction: {next_action}",
    ),
    "alert_generic": (
        "Alert: {title}",
        "{message}",
    ),
    "digest_summary": (
        "ROOT Digest ({count} items)",
        "{items}",
    ),
}


# ── Dataclasses ──────────────────────────────────────────────────────────────


@dataclass
class Notification:
    """Notification record with read tracking and escalation state."""
    title: str
    body: str
    level: str  # "critical", "high", "medium", "low"
    source: str = "root"
    notification_type: str = "generic"  # Used for per-type channel routing
    sent: bool = False
    channel: str = ""
    read: bool = False
    acknowledged: bool = False  # Explicit ack (for escalation)
    escalation_count: int = 0   # How many times escalated
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class NotificationTemplate:
    """Reusable notification template with variable placeholders."""
    name: str
    title_template: str
    body_template: str
    default_level: str = "high"
    default_type: str = "generic"

    def render(self, variables: dict[str, Any]) -> tuple[str, str]:
        """Render title and body with variable substitution."""
        title = self.title_template.format_map(_SafeFormatMap(variables))
        body = self.body_template.format_map(_SafeFormatMap(variables))
        return title, body


class _SafeFormatMap(dict):
    """dict subclass that returns '{key}' for missing keys instead of raising KeyError."""
    def __missing__(self, key: str) -> str:
        return f"{{{key}}}"


@dataclass
class ChannelPreference:
    """Per-notification-type channel routing preference."""
    notification_type: str
    channels: list[str]  # e.g. ["telegram"], ["discord"], ["telegram", "email"]
    min_level: str = "low"  # Minimum level to apply this preference


class NotificationEngine:
    """Push notifications to Yohan via configured channels.

    New capabilities:
    - Batching: group multiple notifications within a time window before sending
    - Templates: reusable title/body templates with variable substitution
    - Scheduling: defer notifications during quiet hours
    - Channel routing: per-notification-type channel preferences
    - Priority escalation: re-alert on unacknowledged HIGH/CRITICAL after timeout
    - History search: filter by keyword, level, source, date range
    - SMS interface: stub for future SMS integration
    """

    BATCH_INTERVAL = 1800  # 30 minutes for medium-priority digest
    BATCH_WINDOW = 60       # seconds to accumulate same-type notifications before sending
    ESCALATION_INTERVAL = 300  # 5 minutes between escalation checks
    ESCALATION_TIMEOUT = 900   # 15 minutes unacknowledged → escalate

    def __init__(
        self,
        telegram_bot_token: str = "",
        telegram_chat_id: str = "",
        discord_webhook_url: str = "",
        smtp_host: Optional[str] = None,
        smtp_port: Optional[int] = None,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_from: Optional[str] = None,
        notification_email: Optional[str] = None,
        slack_webhook_url: Optional[str] = None,
        webhook_urls: Optional[list[str]] = None,
        # Scheduling
        quiet_hours_start: int = 22,  # 24h UTC hour (inclusive)
        quiet_hours_end: int = 8,     # 24h UTC hour (exclusive)
        respect_quiet_hours: bool = True,
        # SMS (interface only — set sms_send_fn to a callable)
        sms_send_fn: Optional[Callable[[str, str], bool]] = None,
        sms_to: str = "",
    ) -> None:
        self._telegram_token = telegram_bot_token
        self._telegram_chat_id = telegram_chat_id
        self._discord_webhook = discord_webhook_url
        self._smtp_host = smtp_host or ""
        self._smtp_port = smtp_port or 587
        self._smtp_user = smtp_user or ""
        self._smtp_password = smtp_password or ""
        self._smtp_from = smtp_from or ""
        self._notification_email = notification_email or ""
        self._slack_webhook_url = slack_webhook_url or ""
        self._webhook_urls: tuple[str, ...] = tuple(webhook_urls) if webhook_urls else ()
        # SMS
        self._sms_send_fn = sms_send_fn
        self._sms_to = sms_to
        # Scheduling
        self._quiet_hours_start = quiet_hours_start
        self._quiet_hours_end = quiet_hours_end
        self._respect_quiet_hours = respect_quiet_hours
        self._deferred_queue: list[Notification] = []  # Held during quiet hours
        # History (enlarged for search)
        self._history: deque[Notification] = deque(maxlen=500)
        self._medium_queue: list[Notification] = []
        # Batching: notification_type -> list of pending notifications
        self._batch_window_queue: dict[str, list[Notification]] = {}
        self._batch_window_timers: dict[str, float] = {}  # type -> epoch when batch started
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._escalation_task: Optional[asyncio.Task] = None
        self._deferred_task: Optional[asyncio.Task] = None
        self._batch_failure_count: int = 0
        self._sandbox_gate = None  # Set via main.py
        self._muted_sources: set[str] = set()
        self._delivery_counts: dict[str, int] = {
            "telegram_sent": 0,
            "telegram_failed": 0,
            "discord_sent": 0,
            "discord_failed": 0,
            "email_sent": 0,
            "email_failed": 0,
            "slack_sent": 0,
            "slack_failed": 0,
            "webhook_sent": 0,
            "webhook_failed": 0,
            "sms_sent": 0,
            "sms_failed": 0,
        }
        # Templates registry
        self._templates: dict[str, NotificationTemplate] = {
            name: NotificationTemplate(
                name=name,
                title_template=title_tmpl,
                body_template=body_tmpl,
            )
            for name, (title_tmpl, body_tmpl) in _BUILTIN_TEMPLATES.items()
        }
        # Per-type channel preferences: type -> ChannelPreference
        self._channel_prefs: dict[str, ChannelPreference] = {
            # Defaults matching requirement: trade alerts -> Telegram, system -> Discord
            "trade": ChannelPreference(
                notification_type="trade",
                channels=["telegram"],
                min_level="low",
            ),
            "system": ChannelPreference(
                notification_type="system",
                channels=["discord"],
                min_level="low",
            ),
        }
        # Escalation tracking: notification id -> sent timestamp (epoch)
        self._pending_escalation: dict[str, float] = {}

    @property
    def is_configured(self) -> bool:
        return (
            bool(self._telegram_token and self._telegram_chat_id)
            or bool(self._discord_webhook)
            or bool(self._smtp_host and self._notification_email)
            or bool(self._slack_webhook_url)
            or bool(self._webhook_urls)
            or bool(self._sms_send_fn and self._sms_to)
        )

    def start(self) -> None:
        if self._running or not self.is_configured:
            return
        self._running = True
        self._task = asyncio.ensure_future(self._batch_loop())
        self._task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        self._escalation_task = asyncio.ensure_future(self._escalation_loop())
        self._escalation_task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        self._deferred_task = asyncio.ensure_future(self._deferred_loop())
        self._deferred_task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        logger.info(
            "Notification engine: started (telegram=%s, discord=%s, email=%s, slack=%s, webhooks=%d, sms=%s)",
            bool(self._telegram_token), bool(self._discord_webhook),
            bool(self._smtp_host), bool(self._slack_webhook_url),
            len(self._webhook_urls), bool(self._sms_send_fn),
        )

    def stop(self) -> None:
        self._running = False
        for task in (self._task, self._escalation_task, self._deferred_task):
            if task:
                task.cancel()

    # ── Muting ──────────────────────────────────────────────

    def mute_source(self, source: str) -> None:
        """Add a source to the mute set (notifications from it will be suppressed)."""
        self._muted_sources = self._muted_sources | {source}
        logger.info("Muted notification source: %s", source)

    def unmute_source(self, source: str) -> None:
        """Remove a source from the mute set."""
        self._muted_sources = self._muted_sources - {source}
        logger.info("Unmuted notification source: %s", source)

    def _should_deliver(self, source: str, level: str) -> bool:
        """Check whether a notification should be delivered (not muted)."""
        if source in self._muted_sources:
            logger.debug("Notification suppressed (muted source=%s, level=%s)", source, level)
            return False
        return True

    # ── Quiet Hours / Scheduling ─────────────────────────────

    def _is_quiet_hours(self) -> bool:
        """Return True if the current UTC time falls within quiet hours."""
        if not self._respect_quiet_hours:
            return False
        hour = datetime.now(timezone.utc).hour
        start = self._quiet_hours_start
        end = self._quiet_hours_end
        if start > end:
            # Wraps midnight: e.g. 22:00–08:00
            return hour >= start or hour < end
        # Same-day window: e.g. 00:00–06:00
        return start <= hour < end

    def configure_quiet_hours(
        self,
        start: int,
        end: int,
        enabled: bool = True,
    ) -> None:
        """Set quiet hours window (UTC). start/end are 24h hours."""
        self._quiet_hours_start = start
        self._quiet_hours_end = end
        self._respect_quiet_hours = enabled
        logger.info(
            "Quiet hours configured: %02d:00-%02d:00 UTC (enabled=%s)",
            start, end, enabled,
        )

    async def _flush_deferred(self) -> None:
        """Send all notifications held in deferred queue."""
        if not self._deferred_queue:
            return
        batch = list(self._deferred_queue)
        self._deferred_queue.clear()
        logger.info("Flushing %d deferred notifications (quiet hours ended)", len(batch))
        for notif in batch:
            await self._send_immediate(notif)

    async def _deferred_loop(self) -> None:
        """Poll every minute; flush deferred queue when quiet hours end."""
        while self._running:
            await asyncio.sleep(60)
            if not self._is_quiet_hours() and self._deferred_queue:
                try:
                    await self._flush_deferred()
                except Exception as exc:
                    logger.error("Deferred flush error: %s", exc)

    # ── Templates ────────────────────────────────────────────

    def register_template(
        self,
        name: str,
        title_template: str,
        body_template: str,
        default_level: str = "high",
        default_type: str = "generic",
    ) -> None:
        """Register or overwrite a notification template."""
        self._templates[name] = NotificationTemplate(
            name=name,
            title_template=title_template,
            body_template=body_template,
            default_level=default_level,
            default_type=default_type,
        )
        logger.debug("Notification template registered: %s", name)

    def get_template(self, name: str) -> Optional[NotificationTemplate]:
        """Return a template by name, or None if not found."""
        return self._templates.get(name)

    def list_templates(self) -> list[str]:
        """List all registered template names."""
        return sorted(self._templates)

    async def send_template(
        self,
        template_name: str,
        variables: dict[str, Any],
        level: Optional[str] = None,
        source: str = "root",
        notification_type: Optional[str] = None,
    ) -> bool:
        """Render a template and send it. Returns True if delivered."""
        template = self._templates.get(template_name)
        if not template:
            logger.warning("Notification template not found: %s", template_name)
            return False
        title, body = template.render(variables)
        effective_level = level or template.default_level
        effective_type = notification_type or template.default_type
        return await self.send(
            title=title,
            body=body,
            level=effective_level,
            source=source,
            notification_type=effective_type,
        )

    # ── Channel Preferences ──────────────────────────────────

    def set_channel_preference(
        self,
        notification_type: str,
        channels: list[str],
        min_level: str = "low",
    ) -> None:
        """Set which channels to use for a notification type.

        Example:
            engine.set_channel_preference("trade", ["telegram"], min_level="low")
            engine.set_channel_preference("system", ["discord", "email"], min_level="high")
        """
        self._channel_prefs[notification_type] = ChannelPreference(
            notification_type=notification_type,
            channels=channels,
            min_level=min_level,
        )
        logger.info(
            "Channel preference set: type=%s -> channels=%s (min_level=%s)",
            notification_type, channels, min_level,
        )

    def get_channel_preference(self, notification_type: str) -> Optional[ChannelPreference]:
        """Return channel preference for a notification type."""
        return self._channel_prefs.get(notification_type)

    def list_channel_preferences(self) -> list[dict[str, Any]]:
        """List all channel preferences."""
        return [
            {
                "type": pref.notification_type,
                "channels": pref.channels,
                "min_level": pref.min_level,
            }
            for pref in self._channel_prefs.values()
        ]

    def _channels_for_notification(self, notif: Notification) -> list[str]:
        """Return the list of channels to use for a specific notification.

        Applies per-type preferences if available and level threshold met;
        otherwise falls back to all configured channels.
        """
        pref = self._channel_prefs.get(notif.notification_type)
        if pref:
            if LEVEL_ORDER.get(notif.level, 0) >= LEVEL_ORDER.get(pref.min_level, 0):
                # Only include channels that are actually configured
                available = self._determine_channels()
                preferred = [ch for ch in pref.channels if ch in available]
                if preferred:
                    return preferred
        return self._determine_channels()

    # ── Batching ─────────────────────────────────────────────

    def _should_batch(self, notif: Notification) -> bool:
        """Return True if this notification type is currently accumulating a batch."""
        ntype = notif.notification_type
        if ntype not in self._batch_window_queue:
            return False
        import time
        age = time.monotonic() - self._batch_window_timers.get(ntype, 0)
        return age < self.BATCH_WINDOW

    def _add_to_batch_window(self, notif: Notification) -> None:
        """Add a notification to the batch window accumulator."""
        import time
        ntype = notif.notification_type
        if ntype not in self._batch_window_queue:
            self._batch_window_queue[ntype] = []
            self._batch_window_timers[ntype] = time.monotonic()
        self._batch_window_queue[ntype].append(notif)

    async def _flush_batch_window(self, notification_type: str) -> None:
        """Flush a batch window for a given type and send as combined notification."""
        batch = self._batch_window_queue.pop(notification_type, [])
        self._batch_window_timers.pop(notification_type, None)
        if not batch:
            return
        if len(batch) == 1:
            await self._send_immediate(batch[0])
            return
        # Combine into single batched notification
        highest_level = max(batch, key=lambda n: LEVEL_ORDER.get(n.level, 0)).level
        source = batch[0].source
        lines = [f"• [{n.level.upper()}] {n.title}: {n.body[:80]}" for n in batch]
        combined = Notification(
            title=f"Batched Alert ({len(batch)} notifications) — {notification_type}",
            body="\n".join(lines),
            level=highest_level,
            source=source,
            notification_type=notification_type,
        )
        self._history.append(combined)
        await self._send_immediate(combined)
        logger.info(
            "Batch window flushed: type=%s count=%d level=%s",
            notification_type, len(batch), highest_level,
        )

    async def _batch_window_loop(self) -> None:
        """Check batch windows every second and flush expired ones."""
        import time
        while self._running:
            await asyncio.sleep(1)
            expired = [
                ntype
                for ntype, start_time in list(self._batch_window_timers.items())
                if time.monotonic() - start_time >= self.BATCH_WINDOW
            ]
            for ntype in expired:
                try:
                    await self._flush_batch_window(ntype)
                except Exception as exc:
                    logger.error("Batch window flush error (type=%s): %s", ntype, exc)

    # ── Priority Escalation ──────────────────────────────────

    def acknowledge(self, notification_id: str) -> bool:
        """Acknowledge a notification to stop escalation."""
        for notif in self._history:
            if notif.id == notification_id:
                notif.acknowledged = True
                notif.read = True
                self._pending_escalation.pop(notification_id, None)
                logger.info("Notification acknowledged: %s", notification_id)
                return True
        return False

    def _next_escalation_level(self, level: str) -> str:
        """Return the next higher alert level (caps at critical)."""
        idx = LEVEL_ORDER.get(level, 0)
        next_idx = min(idx + 1, len(LEVELS) - 1)
        return LEVELS[next_idx]

    async def _escalation_loop(self) -> None:
        """Check for unacknowledged HIGH/CRITICAL notifications and re-send at higher level."""
        import time
        while self._running:
            await asyncio.sleep(self.ESCALATION_INTERVAL)
            now = time.monotonic()
            to_escalate = []
            for notif_id, sent_at in list(self._pending_escalation.items()):
                if now - sent_at >= self.ESCALATION_TIMEOUT:
                    to_escalate.append(notif_id)
            for notif_id in to_escalate:
                # Find the notification in history
                found = next(
                    (n for n in self._history if n.id == notif_id),
                    None,
                )
                if found is None or found.acknowledged or found.read:
                    self._pending_escalation.pop(notif_id, None)
                    continue
                # Escalate
                new_level = self._next_escalation_level(found.level)
                found.escalation_count = found.escalation_count + 1
                escalated = Notification(
                    title=f"[ESCALATION #{found.escalation_count}] {found.title}",
                    body=(
                        f"UNACKNOWLEDGED after {self.ESCALATION_TIMEOUT // 60} minutes.\n\n"
                        f"{found.body}"
                    ),
                    level=new_level,
                    source=found.source,
                    notification_type=found.notification_type,
                )
                self._history.append(escalated)
                self._pending_escalation[escalated.id] = now
                self._pending_escalation.pop(notif_id, None)
                logger.warning(
                    "Escalating notification: %s -> %s (count=%d)",
                    notif_id, new_level, found.escalation_count,
                )
                try:
                    await self._send_immediate(escalated)
                except Exception as exc:
                    logger.error("Escalation send error: %s", exc)

    # ── Retry wrapper ───────────────────────────────────────

    async def _retry_send(
        self,
        send_fn: Callable[..., Any],
        *args: Any,
        max_retries: int = 3,
    ) -> bool:
        """Retry a send function with exponential backoff (1s, 2s, 4s)."""
        for attempt in range(max_retries):
            try:
                result = send_fn(*args)
                # Support both sync and async callables
                if asyncio.iscoroutine(result):
                    result = await result
                if result:
                    return True
            except Exception as e:
                logger.warning("Send attempt %d/%d failed: %s", attempt + 1, max_retries, e)

            if attempt < max_retries - 1:
                delay = 2 ** attempt  # 1s, 2s, 4s
                await asyncio.sleep(delay)

        return False

    # ── Main send ───────────────────────────────────────────

    async def send(
        self,
        title: str,
        body: str,
        level: str = "high",
        source: str = "root",
        notification_type: str = "generic",
        batch: bool = False,
    ) -> bool:
        """Send a notification. Returns True if delivered.

        Args:
            title: Notification title.
            body: Notification body.
            level: Severity — "low", "medium", "high", or "critical".
            source: Originating system/agent.
            notification_type: Semantic type used for channel routing and batching.
            batch: If True, accumulate in a batch window (BATCH_WINDOW seconds)
                   before sending as a combined notification.
        """
        import time

        if not self._should_deliver(source, level):
            return False

        notif = Notification(
            title=title,
            body=body,
            level=level,
            source=source,
            notification_type=notification_type,
        )

        if level in ("critical", "high"):
            # Respect quiet hours only for non-critical
            if level != "critical" and self._is_quiet_hours():
                self._deferred_queue.append(notif)
                self._history.append(notif)
                logger.info(
                    "Notification deferred (quiet hours): [%s] %s",
                    level, title,
                )
                return True

            # Batch window accumulation
            if batch and notification_type != "generic":
                self._add_to_batch_window(notif)
                self._history.append(notif)
                return True

            success = await self._send_immediate(notif)
            channels_used = self._channels_for_notification(notif)
            sent_notif = Notification(
                title=title, body=body, level=level, source=source,
                notification_type=notification_type,
                sent=success, channel=",".join(channels_used),
            )
            self._history.append(sent_notif)

            # Register for escalation tracking
            if success and level in ("critical", "high"):
                self._pending_escalation[sent_notif.id] = time.monotonic()

            return success

        if level == "medium":
            # Quiet hours: defer medium notifications
            if self._is_quiet_hours():
                self._deferred_queue.append(notif)
                self._history.append(notif)
                return True
            self._medium_queue.append(notif)
            self._history.append(notif)
            return True  # Queued for batch

        # LOW — log only
        self._history.append(notif)
        logger.info("Notification (low, log only): %s — %s", title, body[:100])
        return True

    async def audit_external_action(
        self,
        action: str,
        target: str,
        source: str = "root",
        level: str = "low",
        details: str = "",
    ) -> bool:
        """Log and notify about any external action (HTTP call, trade, etc.).

        Provides a consistent audit trail for ALL external interactions.
        level: 'critical' for trades/financial, 'high' for comms/deploy, 'low' for data fetches.
        """
        title = f"External: {action}"
        body = f"Target: {target}"
        if details:
            body = f"{body}\n{details}"
        return await self.send(title=title, body=body, level=level, source=source)

    def _determine_channels(self) -> list[str]:
        """Return list of all configured channel names."""
        channels: list[str] = []
        if self._telegram_token and self._telegram_chat_id:
            channels.append("telegram")
        if self._discord_webhook:
            channels.append("discord")
        if self._smtp_host and self._notification_email:
            channels.append("email")
        if self._slack_webhook_url:
            channels.append("slack")
        if self._webhook_urls:
            channels.append("webhook")
        if self._sms_send_fn and self._sms_to:
            channels.append("sms")
        return channels

    async def _send_immediate(self, notif: Notification) -> bool:
        """Send immediately via channels determined by per-type preferences.

        Sandbox gate check: if notifications system is sandboxed, skip external
        sends but still log. IMPORTANT: sandbox_gate's own notifications
        (source='sandbox_gate') always bypass the gate to prevent deadlock.
        """
        # Sandbox gate check — bypass for sandbox_gate's own notifications
        if (
            self._sandbox_gate is not None
            and notif.source != "sandbox_gate"
            and notif.source != "notification_digest"
        ):
            decision = self._sandbox_gate.check(
                system_id="notifications",
                action=f"send_notification:{notif.level}",
                description=f"[{notif.level}] {notif.title}: {notif.body[:100]}",
                context={"source": notif.source, "level": notif.level},
                risk_level="low",
            )
            if not decision.was_executed:
                logger.info(
                    "Notification sandboxed: [%s] %s (source=%s)",
                    notif.level, notif.title, notif.source,
                )
                return False

        # Determine which channels to use (respects per-type preferences)
        active_channels = self._channels_for_notification(notif)
        success = False

        if "telegram" in active_channels and self._telegram_token and self._telegram_chat_id:
            result = await self._retry_send(self._send_telegram, notif)
            if result:
                self._delivery_counts["telegram_sent"] += 1
            else:
                self._delivery_counts["telegram_failed"] += 1
            success = result or success

        if "discord" in active_channels and self._discord_webhook:
            result = await self._retry_send(self._send_discord, notif)
            if result:
                self._delivery_counts["discord_sent"] += 1
            else:
                self._delivery_counts["discord_failed"] += 1
            success = result or success

        if "email" in active_channels and self._smtp_host and self._notification_email:
            result = await self._retry_send(
                self._send_email, notif.title, notif.body, notif.level,
            )
            if result:
                self._delivery_counts["email_sent"] += 1
            else:
                self._delivery_counts["email_failed"] += 1
            success = result or success

        if "slack" in active_channels and self._slack_webhook_url:
            result = await self._retry_send(
                self._send_slack, notif.title, notif.body, notif.level,
            )
            if result:
                self._delivery_counts["slack_sent"] += 1
            else:
                self._delivery_counts["slack_failed"] += 1
            success = result or success

        if "webhook" in active_channels:
            for url in self._webhook_urls:
                result = await self._retry_send(
                    self._send_webhook, notif.title, notif.body, notif.level, url,
                )
                if result:
                    self._delivery_counts["webhook_sent"] += 1
                else:
                    self._delivery_counts["webhook_failed"] += 1
                success = result or success

        if "sms" in active_channels and self._sms_send_fn and self._sms_to:
            result = await self._retry_send(
                self._send_sms, notif.title, notif.body,
            )
            if result:
                self._delivery_counts["sms_sent"] += 1
            else:
                self._delivery_counts["sms_failed"] += 1
            success = result or success

        if not self.is_configured:
            logger.warning("Notification not sent (no channels configured): %s", notif.title)

        return success

    # ── Channel implementations ─────────────────────────────

    async def _send_telegram(self, notif: Notification) -> bool:
        """Send notification via Telegram Bot API."""
        try:
            import httpx
            level_emoji = {"critical": "🚨", "high": "⚠️", "medium": "📋", "low": "ℹ️"}
            emoji = level_emoji.get(notif.level, "📢")
            text = f"{emoji} *{notif.title}*\n\n{notif.body}\n\n_Source: {notif.source}_"

            url = f"https://api.telegram.org/bot{self._telegram_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json={
                    "chat_id": self._telegram_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                })
                if resp.status_code == 200:
                    logger.info("Telegram notification sent: %s", notif.title)
                    return True
                logger.error("Telegram send failed (%d): %s", resp.status_code, resp.text[:200])
                return False
        except Exception as e:
            logger.error("Telegram notification error: %s", e)
            return False

    async def _send_discord(self, notif: Notification) -> bool:
        """Send notification via Discord webhook."""
        try:
            import httpx
            level_color = {"critical": 0xFF0000, "high": 0xFF8C00, "medium": 0x3498DB, "low": 0x95A5A6}
            color = level_color.get(notif.level, 0x3498DB)

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._discord_webhook, json={
                    "embeds": [{
                        "title": notif.title,
                        "description": notif.body,
                        "color": color,
                        "footer": {"text": f"ROOT • {notif.source}"},
                        "timestamp": notif.created_at,
                    }],
                })
                if resp.status_code in (200, 204):
                    logger.info("Discord notification sent: %s", notif.title)
                    return True
                logger.error("Discord send failed (%d): %s", resp.status_code, resp.text[:200])
                return False
        except Exception as e:
            logger.error("Discord notification error: %s", e)
            return False

    async def _send_email(self, title: str, body: str, level: str) -> bool:
        """Send notification via SMTP email."""
        try:
            level_prefix = {"critical": "[CRITICAL]", "high": "[HIGH]", "medium": "[MEDIUM]", "low": "[LOW]"}
            prefix = level_prefix.get(level, "[INFO]")

            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"{prefix} ROOT: {title}"
            msg["From"] = self._smtp_from or self._smtp_user
            msg["To"] = self._notification_email

            text_content = f"{prefix} {title}\n\n{body}\n\n— ROOT Notification Engine"
            html_content = (
                f"<h2>{prefix} {title}</h2>"
                f"<p>{body.replace(chr(10), '<br>')}</p>"
                f"<hr><small>ROOT Notification Engine</small>"
            )
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            # Run SMTP in executor to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._smtp_send_sync, msg)

            logger.info("Email notification sent: %s -> %s", title, self._notification_email)
            return True
        except Exception as e:
            logger.error("Email notification error: %s", e)
            return False

    def _smtp_send_sync(self, msg: MIMEMultipart) -> bool:
        """Synchronous SMTP send (called in executor)."""
        with smtplib.SMTP(self._smtp_host, self._smtp_port) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            if self._smtp_user and self._smtp_password:
                server.login(self._smtp_user, self._smtp_password)
            server.sendmail(
                msg["From"],
                [self._notification_email],
                msg.as_string(),
            )
        return True

    async def _send_slack(self, title: str, body: str, level: str) -> bool:
        """Send notification via Slack webhook URL."""
        try:
            import httpx
            level_emoji = {"critical": ":rotating_light:", "high": ":warning:", "medium": ":memo:", "low": ":information_source:"}
            emoji = level_emoji.get(level, ":bell:")

            payload = {
                "text": f"{emoji} *{title}*",
                "blocks": [
                    {
                        "type": "header",
                        "text": {"type": "plain_text", "text": f"{title}"},
                    },
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": body},
                    },
                    {
                        "type": "context",
                        "elements": [
                            {"type": "mrkdwn", "text": f"Level: *{level}* | ROOT Notification Engine"},
                        ],
                    },
                ],
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._slack_webhook_url, json=payload)
                if resp.status_code == 200:
                    logger.info("Slack notification sent: %s", title)
                    return True
                logger.error("Slack send failed (%d): %s", resp.status_code, resp.text[:200])
                return False
        except Exception as e:
            logger.error("Slack notification error: %s", e)
            return False

    async def _send_webhook(self, title: str, body: str, level: str, url: str) -> bool:
        """POST JSON notification to a user-defined webhook endpoint."""
        try:
            import httpx
            payload = {
                "title": title,
                "body": body,
                "level": level,
                "source": "root",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                if resp.status_code in range(200, 300):
                    logger.info("Webhook notification sent to %s: %s", url, title)
                    return True
                logger.error("Webhook send failed (%d) to %s: %s", resp.status_code, url, resp.text[:200])
                return False
        except Exception as e:
            logger.error("Webhook notification error (%s): %s", url, e)
            return False

    async def _send_sms(self, title: str, body: str) -> bool:
        """Send notification via SMS using the injected sms_send_fn.

        The sms_send_fn callable receives (to, message) and returns bool.
        This is an interface stub — plug in Twilio, AWS SNS, or any SMS provider.

        Example integration:
            from twilio.rest import Client
            twilio = Client(account_sid, auth_token)

            def send_twilio_sms(to: str, message: str) -> bool:
                twilio.messages.create(to=to, from_=from_number, body=message)
                return True

            engine = NotificationEngine(sms_send_fn=send_twilio_sms, sms_to="+15551234567")
        """
        if not self._sms_send_fn or not self._sms_to:
            return False
        try:
            message = f"[ROOT] {title}: {body[:140]}"
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, self._sms_send_fn, self._sms_to, message,
            )
            if result:
                logger.info("SMS notification sent to %s: %s", self._sms_to, title)
                return True
            logger.error("SMS send returned False: %s", title)
            return False
        except Exception as e:
            logger.error("SMS notification error: %s", e)
            return False

    # ── Batch loop ──────────────────────────────────────────

    async def _batch_loop(self) -> None:
        """Flush medium-priority notifications as a digest every BATCH_INTERVAL."""
        while self._running:
            await asyncio.sleep(self.BATCH_INTERVAL)
            if not self._medium_queue:
                continue

            try:
                batch = list(self._medium_queue)
                self._medium_queue.clear()

                body_parts = [f"• **{n.title}**: {n.body[:100]}" for n in batch]
                digest = Notification(
                    title=f"ROOT Digest ({len(batch)} items)",
                    body="\n".join(body_parts),
                    level="high",
                    source="notification_digest",
                )
                await self._send_immediate(digest)
                self._batch_failure_count = 0
            except Exception as exc:
                self._batch_failure_count = self._batch_failure_count + 1
                logger.error("Notification batch loop error: %s", exc)
                if self._batch_failure_count >= 5:
                    logger.critical(
                        "Notification engine: %d consecutive batch failures — backing off 300s",
                        self._batch_failure_count,
                    )
                    self._batch_failure_count = 0
                    await asyncio.sleep(300)

    # ── History & stats ─────────────────────────────────────

    def get_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return recent notification history."""
        all_items = list(self._history)
        start = max(len(all_items) - limit, 0) if limit > 0 else 0
        items: list[Notification] = list(all_items[slice(start, None)])
        return [
            {
                "id": n.id,
                "title": n.title,
                "body": n.body[slice(0, 200)],
                "level": n.level,
                "source": n.source,
                "sent": n.sent,
                "channel": n.channel,
                "read": n.read,
                "created_at": n.created_at,
            }
            for n in reversed(items)
        ]

    def delivery_stats(self) -> dict[str, Any]:
        """Delivery statistics by channel."""
        total_sent = sum(v for k, v in self._delivery_counts.items() if k.endswith("_sent"))
        total_failed = sum(v for k, v in self._delivery_counts.items() if k.endswith("_failed"))

        return {
            "total_sent": total_sent,
            "total_failed": total_failed,
            "by_channel": {
                "telegram": self._delivery_counts["telegram_sent"],
                "discord": self._delivery_counts["discord_sent"],
                "email": self._delivery_counts["email_sent"],
                "slack": self._delivery_counts["slack_sent"],
                "webhook": self._delivery_counts["webhook_sent"],
            },
        }

    def stats(self) -> dict[str, Any]:
        """Notification statistics."""
        total = len(self._history)
        sent = sum(1 for n in self._history if n.sent)
        return {
            "configured": self.is_configured,
            "telegram": bool(self._telegram_token),
            "discord": bool(self._discord_webhook),
            "email": bool(self._smtp_host and self._notification_email),
            "slack": bool(self._slack_webhook_url),
            "webhooks": len(self._webhook_urls),
            "muted_sources": sorted(self._muted_sources),
            "total_notifications": total,
            "sent": sent,
            "pending_medium": len(self._medium_queue),
            "delivery": self.delivery_stats(),
        }
