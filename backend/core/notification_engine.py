"""
Notification Engine — push alerts to Yohan via Telegram, Discord, Email, Slack, and webhooks.

Levels:
- CRITICAL / HIGH: send immediately
- MEDIUM: batch into digest (30 min)
- LOW: log only (no push)
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Callable, Optional

logger = logging.getLogger("root.notifications")


@dataclass
class Notification:
    """Notification record with read tracking."""
    title: str
    body: str
    level: str  # "critical", "high", "medium", "low"
    source: str = "root"
    sent: bool = False
    channel: str = ""
    read: bool = False
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class NotificationEngine:
    """Push notifications to Yohan via configured channels."""

    BATCH_INTERVAL = 1800  # 30 minutes for medium-priority digest

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
        self._history: deque[Notification] = deque(maxlen=200)
        self._medium_queue: list[Notification] = []
        self._running = False
        self._task: Optional[asyncio.Task] = None
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
        }

    @property
    def is_configured(self) -> bool:
        return (
            bool(self._telegram_token and self._telegram_chat_id)
            or bool(self._discord_webhook)
            or bool(self._smtp_host and self._notification_email)
            or bool(self._slack_webhook_url)
            or bool(self._webhook_urls)
        )

    def start(self) -> None:
        if self._running or not self.is_configured:
            return
        self._running = True
        self._task = asyncio.ensure_future(self._batch_loop())
        self._task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
        logger.info("Notification engine: started (telegram=%s, discord=%s, email=%s, slack=%s, webhooks=%d)",
                     bool(self._telegram_token), bool(self._discord_webhook),
                     bool(self._smtp_host), bool(self._slack_webhook_url),
                     len(self._webhook_urls))

    def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()

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
        self, title: str, body: str,
        level: str = "high", source: str = "root",
    ) -> bool:
        """Send a notification. Returns True if delivered."""
        if not self._should_deliver(source, level):
            return False

        notif = Notification(title=title, body=body, level=level, source=source)

        if level in ("critical", "high"):
            success = await self._send_immediate(notif)
            channels_used = self._determine_channels()
            sent_notif = Notification(
                title=title, body=body, level=level, source=source,
                sent=success, channel=",".join(channels_used),
            )
            self._history.append(sent_notif)
            return success

        if level == "medium":
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
        """Return list of configured channel names."""
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
        return channels

    async def _send_immediate(self, notif: Notification) -> bool:
        """Send immediately via all configured channels.

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

        success = False

        if self._telegram_token and self._telegram_chat_id:
            result = await self._retry_send(self._send_telegram, notif)
            if result:
                self._delivery_counts["telegram_sent"] += 1
            else:
                self._delivery_counts["telegram_failed"] += 1
            success = result or success

        if self._discord_webhook:
            result = await self._retry_send(self._send_discord, notif)
            if result:
                self._delivery_counts["discord_sent"] += 1
            else:
                self._delivery_counts["discord_failed"] += 1
            success = result or success

        if self._smtp_host and self._notification_email:
            result = await self._retry_send(
                self._send_email, notif.title, notif.body, notif.level,
            )
            if result:
                self._delivery_counts["email_sent"] += 1
            else:
                self._delivery_counts["email_failed"] += 1
            success = result or success

        if self._slack_webhook_url:
            result = await self._retry_send(
                self._send_slack, notif.title, notif.body, notif.level,
            )
            if result:
                self._delivery_counts["slack_sent"] += 1
            else:
                self._delivery_counts["slack_failed"] += 1
            success = result or success

        for url in self._webhook_urls:
            result = await self._retry_send(
                self._send_webhook, notif.title, notif.body, notif.level, url,
            )
            if result:
                self._delivery_counts["webhook_sent"] += 1
            else:
                self._delivery_counts["webhook_failed"] += 1
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
