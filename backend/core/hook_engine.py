"""
Hook Engine — event-driven automations from ECC patterns.

Hooks fire on events: pre_action, post_action, on_reflect, on_learn,
on_startup, on_shutdown. Each hook is a Python callable with conditions.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.hooks")

HOOKS_DIR = ROOT_DIR / "data" / "hooks"


class HookEvent(str, Enum):
    PRE_ACTION = "pre_action"       # Before any agent action
    POST_ACTION = "post_action"     # After any agent action
    ON_CHAT = "on_chat"             # After user message received
    ON_RESPONSE = "on_response"     # After ROOT responds
    ON_REFLECT = "on_reflect"       # After self-reflection
    ON_LEARN = "on_learn"           # After storing a new memory
    ON_SKILL_CREATE = "on_skill_create"  # After creating a skill
    ON_ERROR = "on_error"           # When an error occurs
    ON_STARTUP = "on_startup"       # Server startup
    ON_SHUTDOWN = "on_shutdown"     # Server shutdown


@dataclass(frozen=True)
class HookResult:
    """Immutable result from a hook execution."""
    hook_name: str
    event: HookEvent
    success: bool
    output: str = ""
    blocked: bool = False          # If True, action should be cancelled
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class Hook:
    """Immutable hook definition."""
    name: str
    event: HookEvent
    handler: Callable
    description: str = ""
    enabled: bool = True
    priority: int = 50             # Lower = runs first (0-100)
    condition: Optional[Callable] = None  # Optional filter


class HookEngine:
    """Manages and executes event-driven hooks."""

    def __init__(self) -> None:
        self._hooks: dict[HookEvent, list[Hook]] = {e: [] for e in HookEvent}
        self._log: list[HookResult] = []

    def register(self, hook: Hook) -> None:
        """Register a hook for an event."""
        self._hooks[hook.event].append(hook)
        # Keep sorted by priority
        self._hooks[hook.event].sort(key=lambda h: h.priority)
        logger.info("Hook registered: %s on %s", hook.name, hook.event.value)

    def unregister(self, name: str) -> None:
        """Remove a hook by name."""
        for event in HookEvent:
            self._hooks[event] = [h for h in self._hooks[event] if h.name != name]

    async def fire(self, event: HookEvent, context: Optional[dict[str, Any]] = None) -> list[HookResult]:
        """Fire all hooks for an event. Returns results."""
        results = []
        for hook in self._hooks[event]:
            if not hook.enabled:
                continue
            if hook.condition and not hook.condition(context or {}):
                continue
            try:
                output = hook.handler(context or {})
                if hasattr(output, "__await__"):
                    output = await output
                result = HookResult(
                    hook_name=hook.name,
                    event=event,
                    success=True,
                    output=str(output) if output else "",
                )
            except Exception as e:
                logger.error("Hook %s failed: %s", hook.name, e)
                result = HookResult(
                    hook_name=hook.name,
                    event=event,
                    success=False,
                    output=str(e),
                )
            results.append(result)
            self._log.append(result)

            # If hook blocks, stop processing
            if result.blocked:
                break

        return results

    def get_hooks(self, event: Optional[HookEvent] = None) -> list[Hook]:
        """List registered hooks."""
        if event:
            return list(self._hooks[event])
        return [h for hooks in self._hooks.values() for h in hooks]

    def get_log(self, limit: int = 50) -> list[HookResult]:
        """Get recent hook execution log."""
        return list(reversed(self._log[-limit:]))

    def stats(self) -> dict:
        """Hook statistics."""
        return {
            "total_hooks": sum(len(hooks) for hooks in self._hooks.values()),
            "by_event": {e.value: len(hooks) for e, hooks in self._hooks.items() if hooks},
            "executions": len(self._log),
            "failures": sum(1 for r in self._log if not r.success),
        }


def build_default_hooks(memory_engine=None, skill_engine=None, learning_engine=None) -> HookEngine:
    """Create hook engine with ROOT's built-in hooks."""
    engine = HookEngine()

    # ── Startup hook: log boot ──
    def on_startup(ctx):
        logger.info("ROOT startup hook fired")
        return "ROOT initialized"

    engine.register(Hook(
        name="boot_logger",
        event=HookEvent.ON_STARTUP,
        handler=on_startup,
        description="Log ROOT startup",
        priority=10,
    ))

    # ── On-chat hook: track interaction count ──
    interaction_count = {"n": 0}

    def on_chat(ctx):
        interaction_count["n"] += 1
        if interaction_count["n"] % 10 == 0:
            logger.info("Milestone: %d interactions", interaction_count["n"])
        return f"interaction #{interaction_count['n']}"

    engine.register(Hook(
        name="interaction_counter",
        event=HookEvent.ON_CHAT,
        handler=on_chat,
        description="Count interactions for reflection triggers",
        priority=10,
    ))

    # ── On-learn hook: log new memories ──
    def on_learn(ctx):
        content = ctx.get("content", "")[:100]
        mem_type = ctx.get("memory_type", "unknown")
        logger.info("New memory [%s]: %s", mem_type, content)
        return f"logged {mem_type}"

    engine.register(Hook(
        name="memory_logger",
        event=HookEvent.ON_LEARN,
        handler=on_learn,
        description="Log new memory creation",
        priority=20,
    ))

    # ── On-error hook: store error in memory ──
    def on_error(ctx):
        error = ctx.get("error", "unknown error")
        if memory_engine:
            from backend.models.memory import MemoryEntry, MemoryType
            memory_engine.store(MemoryEntry(
                content=f"Error encountered: {str(error)[:300]}",
                memory_type=MemoryType.ERROR,
                tags=["error", "auto-captured"],
                source="hook_engine",
                confidence=0.7,
            ))
        return f"error logged: {str(error)[:50]}"

    engine.register(Hook(
        name="error_capture",
        event=HookEvent.ON_ERROR,
        handler=on_error,
        description="Capture errors in memory for learning",
        priority=10,
    ))

    # ── On-skill-create hook: update index ──
    def on_skill_create(ctx):
        if skill_engine:
            skill_engine.load_all()
        name = ctx.get("name", "unknown")
        logger.info("Skill created: %s — index reloaded", name)
        return f"reindexed after {name}"

    engine.register(Hook(
        name="skill_reindex",
        event=HookEvent.ON_SKILL_CREATE,
        handler=on_skill_create,
        description="Reload skill index after new skill creation",
        priority=10,
    ))

    # ── On-error hook: record error patterns in learning engine ──
    def auto_learn_from_error(ctx):
        if not learning_engine:
            return "no learning engine"
        error = ctx.get("error", "unknown")
        source = ctx.get("source", "unknown")
        learning_engine.record_agent_outcome(
            agent_id=source,
            task_description=f"error: {str(error)[:200]}",
            status="failed",
            result_quality=0.0,
            task_category="error",
            error_message=str(error)[:500],
        )
        return f"error pattern recorded for {source}"

    engine.register(Hook(
        name="auto_learn_from_error",
        event=HookEvent.ON_ERROR,
        handler=auto_learn_from_error,
        description="Record error patterns in learning engine for adaptive routing",
        priority=15,
    ))

    # ── On-response hook: auto-record routing quality ──
    def routing_feedback(ctx):
        if not learning_engine:
            return "no learning engine"
        agent_id = ctx.get("agent_id", "")
        category = ctx.get("category", "general")
        quality = ctx.get("quality", 0.5)
        if agent_id and quality > 0:
            learning_engine.record_agent_outcome(
                agent_id=agent_id,
                task_description=f"routed response ({category})",
                status="completed",
                result_quality=quality,
                task_category=category,
            )
            return f"routing feedback: {agent_id} quality={quality}"
        return "no agent to track"

    engine.register(Hook(
        name="routing_feedback",
        event=HookEvent.ON_RESPONSE,
        handler=routing_feedback,
        description="Auto-record routing quality into learning engine after every response",
        priority=50,
    ))

    return engine
