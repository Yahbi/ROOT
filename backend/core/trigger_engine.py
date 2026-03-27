"""
Trigger Engine — event-driven automation for ROOT.

Reacts to real-world events instead of just polling on timers:
- File system changes (new files in watched directories)
- Scheduled triggers (cron-like time-based execution)
- Webhook triggers (external services calling ROOT)
- Condition triggers (memory/metric thresholds)

Each trigger maps to an action: delegate to agent, enqueue task, fire proactive action.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

logger = logging.getLogger("root.triggers")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class TriggerRule:
    """Immutable trigger definition."""
    id: str
    name: str
    trigger_type: str  # file_watch | schedule | webhook | condition
    config: dict[str, Any]  # type-specific config
    action_type: str  # delegate | enqueue | proactive | custom
    action_config: dict[str, Any]  # action-specific config
    enabled: bool = True
    fire_count: int = 0
    last_fired: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)


class TriggerEngine:
    """Manages event-driven triggers that fire actions autonomously."""

    SCAN_INTERVAL = 30  # File scan interval in seconds

    def __init__(
        self,
        task_queue=None,
        collab=None,
        proactive=None,
        bus=None,
        memory=None,
    ) -> None:
        self._task_queue = task_queue
        self._collab = collab
        self._proactive = proactive
        self._bus = bus
        self._memory = memory

        self._rules: dict[str, TriggerRule] = {}
        self._file_states: dict[str, float] = {}  # path → last mtime
        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._custom_handlers: dict[str, Callable[..., Coroutine]] = {}
        self._failure_count: int = 0

        self._register_defaults()

    def _register_defaults(self) -> None:
        """Register built-in trigger rules."""
        home = Path.home()

        # Watch Downloads for new files
        downloads = home / "Downloads"
        if downloads.exists():
            self.add_rule(TriggerRule(
                id="trigger_downloads",
                name="New Downloads",
                trigger_type="file_watch",
                config={"path": str(downloads), "extensions": [".pdf", ".csv", ".json", ".xlsx"]},
                action_type="enqueue",
                action_config={
                    "goal": "Process and summarize new file: {filename}",
                    "priority": 7,
                    "source": "trigger",
                },
            ))

        # Watch Desktop for new files
        desktop = home / "Desktop"
        if desktop.exists():
            self.add_rule(TriggerRule(
                id="trigger_desktop",
                name="New Desktop Files",
                trigger_type="file_watch",
                config={"path": str(desktop), "extensions": [".pdf", ".csv", ".json", ".txt"]},
                action_type="enqueue",
                action_config={
                    "goal": "Process and organize new desktop file: {filename}",
                    "priority": 7,
                    "source": "trigger",
                },
            ))

        # Schedule: morning briefing at 8am
        self.add_rule(TriggerRule(
            id="trigger_morning_brief",
            name="Morning Briefing",
            trigger_type="schedule",
            config={"hour": 8, "minute": 0},
            action_type="enqueue",
            action_config={
                "goal": "Generate morning briefing: overnight activity summary, market conditions, pending tasks, goal progress",
                "priority": 3,
                "source": "trigger",
            },
        ))

        # Schedule: evening summary at 20:00
        self.add_rule(TriggerRule(
            id="trigger_evening_summary",
            name="Evening Summary",
            trigger_type="schedule",
            config={"hour": 20, "minute": 0},
            action_type="enqueue",
            action_config={
                "goal": "Generate daily summary: what was accomplished today, key learnings, tomorrow's priorities",
                "priority": 5,
                "source": "trigger",
            },
        ))

        # Condition: memory count drops below threshold
        self.add_rule(TriggerRule(
            id="trigger_memory_low",
            name="Low Memory Alert",
            trigger_type="condition",
            config={"check": "memory_health", "threshold": 100},
            action_type="proactive",
            action_config={"action_name": "knowledge_consolidation"},
        ))

    # ── Rule Management ──────────────────────────────────────────

    def add_rule(self, rule: TriggerRule) -> None:
        self._rules[rule.id] = rule

    def remove_rule(self, rule_id: str) -> bool:
        return self._rules.pop(rule_id, None) is not None

    def enable_rule(self, rule_id: str) -> bool:
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        from dataclasses import replace
        self._rules[rule_id] = replace(rule, enabled=True)
        return True

    def disable_rule(self, rule_id: str) -> bool:
        rule = self._rules.get(rule_id)
        if not rule:
            return False
        from dataclasses import replace
        self._rules[rule_id] = replace(rule, enabled=False)
        return True

    def get_rules(self) -> list[dict[str, Any]]:
        return [
            {
                "id": r.id, "name": r.name, "trigger_type": r.trigger_type,
                "action_type": r.action_type, "enabled": r.enabled,
                "fire_count": r.fire_count, "last_fired": r.last_fired,
            }
            for r in self._rules.values()
        ]

    # ── Lifecycle ────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        logger.info("TriggerEngine starting with %d rules", len(self._rules))

        # Initialize file states for watchers
        for rule in self._rules.values():
            if rule.trigger_type == "file_watch" and rule.enabled:
                self._init_file_state(rule)

        # Start background loops
        self._tasks.append(asyncio.create_task(self._file_watch_loop()))
        self._tasks.append(asyncio.create_task(self._schedule_loop()))
        self._tasks.append(asyncio.create_task(self._condition_loop()))

    def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("TriggerEngine stopped")

    # ── File Watching ────────────────────────────────────────────

    def _init_file_state(self, rule: TriggerRule) -> None:
        """Snapshot current files so we only trigger on NEW files."""
        watch_path = Path(rule.config.get("path", ""))
        if not watch_path.exists():
            return
        extensions = set(rule.config.get("extensions", []))
        for f in watch_path.iterdir():
            if f.is_file() and (not extensions or f.suffix.lower() in extensions):
                self._file_states[str(f)] = f.stat().st_mtime

    async def _file_watch_loop(self) -> None:
        """Periodically scan watched directories for new files."""
        await asyncio.sleep(10)  # Initial delay

        while self._running:
            try:
                for rule in list(self._rules.values()):
                    if rule.trigger_type != "file_watch" or not rule.enabled:
                        continue
                    await self._check_file_trigger(rule)
                self._failure_count = 0
            except asyncio.CancelledError:
                return
            except Exception as e:
                self._failure_count = self._failure_count + 1
                logger.error("File watch error: %s", e)
                if self._failure_count >= 5:
                    logger.critical(
                        "Trigger engine (file watch): %d consecutive failures — backing off 300s",
                        self._failure_count,
                    )
                    self._failure_count = 0
                    await asyncio.sleep(300)
                    continue
            await asyncio.sleep(self.SCAN_INTERVAL)

    async def _check_file_trigger(self, rule: TriggerRule) -> None:
        watch_path = Path(rule.config.get("path", ""))
        if not watch_path.exists():
            return

        extensions = set(rule.config.get("extensions", []))
        for f in watch_path.iterdir():
            if not f.is_file():
                continue
            if extensions and f.suffix.lower() not in extensions:
                continue

            file_key = str(f)
            current_mtime = f.stat().st_mtime
            if file_key not in self._file_states:
                # New file detected
                self._file_states[file_key] = current_mtime
                logger.info("Trigger '%s': new file detected — %s", rule.name, f.name)
                await self._fire_action(rule, {"filename": f.name, "path": str(f)})
            elif current_mtime > self._file_states[file_key]:
                self._file_states[file_key] = current_mtime

    # ── Schedule Triggers ────────────────────────────────────────

    async def _schedule_loop(self) -> None:
        """Check scheduled triggers every minute."""
        await asyncio.sleep(30)

        last_fired_minute: dict[str, int] = {}

        while self._running:
            try:
                now = datetime.now(timezone.utc)
                for rule in list(self._rules.values()):
                    if rule.trigger_type != "schedule" or not rule.enabled:
                        continue

                    target_hour = rule.config.get("hour", -1)
                    target_minute = rule.config.get("minute", 0)

                    if now.hour == target_hour and now.minute == target_minute:
                        minute_key = f"{rule.id}:{now.date()}:{now.hour}:{now.minute}"
                        if minute_key not in last_fired_minute:
                            last_fired_minute[minute_key] = 1
                            logger.info("Trigger '%s': schedule fired", rule.name)
                            await self._fire_action(rule, {"time": now.isoformat()})
                self._failure_count = 0
            except asyncio.CancelledError:
                return
            except Exception as e:
                self._failure_count = self._failure_count + 1
                logger.error("Schedule trigger error: %s", e)
                if self._failure_count >= 5:
                    logger.critical(
                        "Trigger engine (schedule): %d consecutive failures — backing off 300s",
                        self._failure_count,
                    )
                    self._failure_count = 0
                    await asyncio.sleep(300)
                    continue
            await asyncio.sleep(60)

    # ── Condition Triggers ───────────────────────────────────────

    async def _condition_loop(self) -> None:
        """Check condition triggers every 5 minutes."""
        await asyncio.sleep(60)

        while self._running:
            try:
                for rule in list(self._rules.values()):
                    if rule.trigger_type != "condition" or not rule.enabled:
                        continue
                    await self._check_condition(rule)
                self._failure_count = 0
            except asyncio.CancelledError:
                return
            except Exception as e:
                self._failure_count = self._failure_count + 1
                logger.error("Condition trigger error: %s", e)
                if self._failure_count >= 5:
                    logger.critical(
                        "Trigger engine (condition): %d consecutive failures — backing off 300s",
                        self._failure_count,
                    )
                    self._failure_count = 0
                    await asyncio.sleep(300)
                    continue
            await asyncio.sleep(300)

    async def _check_condition(self, rule: TriggerRule) -> None:
        check = rule.config.get("check", "")
        threshold = rule.config.get("threshold", 0)

        if check == "memory_health" and self._memory:
            count = self._memory.count()
            if count < threshold:
                logger.info("Trigger '%s': memory count %d < %d", rule.name, count, threshold)
                await self._fire_action(rule, {"memory_count": count, "threshold": threshold})

    # ── Webhook Triggers ─────────────────────────────────────────

    async def fire_webhook(self, trigger_id: str, payload: dict[str, Any]) -> bool:
        """Called by webhook endpoint to fire a trigger."""
        rule = self._rules.get(trigger_id)
        if not rule or rule.trigger_type != "webhook" or not rule.enabled:
            return False
        await self._fire_action(rule, payload)
        return True

    # ── Action Execution ─────────────────────────────────────────

    async def _fire_action(self, rule: TriggerRule, context: dict[str, Any]) -> None:
        """Execute the action associated with a trigger."""
        from dataclasses import replace
        updated = replace(rule, fire_count=rule.fire_count + 1, last_fired=_now_iso())
        self._rules[rule.id] = updated

        action_type = rule.action_type
        action_config = dict(rule.action_config)

        # Template substitution
        for key, val in action_config.items():
            if isinstance(val, str):
                for ctx_key, ctx_val in context.items():
                    action_config[key] = action_config[key].replace(
                        f"{{{ctx_key}}}", str(ctx_val)
                    )

        try:
            if action_type == "enqueue" and self._task_queue:
                self._task_queue.enqueue(
                    goal=action_config.get("goal", "Triggered task"),
                    priority=int(action_config.get("priority", 5)),
                    source=action_config.get("source", "trigger"),
                    metadata={"trigger_id": rule.id, "context": context},
                )

            elif action_type == "delegate" and self._collab:
                await self._collab.delegate(
                    from_agent="trigger_engine",
                    to_agent=action_config.get("agent_id", "researcher"),
                    task=action_config.get("task", "Process triggered event"),
                )

            elif action_type == "proactive" and self._proactive:
                action_name = action_config.get("action_name", "")
                if action_name:
                    await self._proactive.trigger(action_name)

            elif action_type == "custom":
                handler = self._custom_handlers.get(rule.id)
                if handler:
                    await handler(context)

            # Publish to bus
            if self._bus:
                msg = self._bus.create_message(
                    topic="system.trigger",
                    sender="trigger_engine",
                    payload={
                        "trigger_id": rule.id,
                        "trigger_name": rule.name,
                        "action_type": action_type,
                        "context": {k: str(v)[:200] for k, v in context.items()},
                    },
                )
                await self._bus.publish(msg)

        except Exception as e:
            logger.error("Trigger action failed for '%s': %s", rule.name, e)

    # ── Stats ────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "total_rules": len(self._rules),
            "enabled": sum(1 for r in self._rules.values() if r.enabled),
            "total_fires": sum(r.fire_count for r in self._rules.values()),
            "by_type": {
                t: sum(1 for r in self._rules.values() if r.trigger_type == t)
                for t in ("file_watch", "schedule", "webhook", "condition")
            },
        }
