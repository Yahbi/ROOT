"""
Plugin Engine — extensible capability system for ROOT.

Plugins are self-contained modules that add new capabilities:
- Web search, code execution, file management, scheduling, etc.
- Each plugin registers tools that ROOT can invoke during chat.
- Plugins can be enabled/disabled at runtime.
"""

from __future__ import annotations

import logging
import os
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger("root.plugins")


class PluginStatus(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass(frozen=True)
class PluginTool:
    """A callable tool provided by a plugin."""
    name: str
    description: str
    handler: Callable
    parameters: dict[str, Any] = field(default_factory=dict)
    requires_llm: bool = False


@dataclass(frozen=True)
class Plugin:
    """Immutable plugin definition."""
    id: str
    name: str
    description: str
    version: str
    author: str = "ROOT"
    tools: list[PluginTool] = field(default_factory=list)
    status: PluginStatus = PluginStatus.ACTIVE
    category: str = "general"
    tags: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass(frozen=True)
class PluginResult:
    """Immutable result from a plugin tool invocation."""
    plugin_id: str
    tool_name: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PluginEngine:
    """Manages ROOT's plugin ecosystem."""

    # Tool names that map to "trading" system for sandbox gating
    _TRADING_TOOLS: frozenset[str] = frozenset({
        "alpaca_place_order", "alpaca_account", "alpaca_positions",
        "alpaca_market_data", "alpaca_order_history",
        "polymarket_place_order", "polymarket_market_order",
        "polymarket_cancel_order", "polymarket_cancel_all",
        "polymarket_balance", "polymarket_positions",
        "polymarket_orderbook", "polymarket_price",
        "polymarket_open_orders",
    })

    # Subset of trading tools that place/cancel orders (write operations → CRITICAL risk)
    _TRADING_WRITE_TOOLS: frozenset[str] = frozenset({
        "alpaca_place_order", "alpaca_cancel_order",
        "polymarket_place_order", "polymarket_market_order",
        "polymarket_cancel_order", "polymarket_cancel_all",
    })

    def __init__(self, state_store=None) -> None:
        self._plugins: dict[str, Plugin] = {}
        self._tools: dict[str, tuple[str, PluginTool]] = {}  # tool_name -> (plugin_id, tool)
        self._invocation_log: deque[PluginResult] = deque(maxlen=500)
        self._state_store = state_store
        self._sandbox_gate = None  # Set via main.py

    def register(self, plugin: Plugin) -> None:
        """Register a plugin and index its tools."""
        self._plugins[plugin.id] = plugin
        for tool in plugin.tools:
            qualified = f"{plugin.id}.{tool.name}"
            self._tools[qualified] = (plugin.id, tool)
            self._tools[tool.name] = (plugin.id, tool)
        logger.info("Plugin registered: %s (%d tools)", plugin.name, len(plugin.tools))

    def unregister(self, plugin_id: str) -> None:
        plugin = self._plugins.pop(plugin_id, None)
        if plugin:
            for tool in plugin.tools:
                self._tools.pop(f"{plugin_id}.{tool.name}", None)
                self._tools.pop(tool.name, None)

    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        return self._plugins.get(plugin_id)

    def list_plugins(self) -> list[Plugin]:
        return list(self._plugins.values())

    def list_tools(self) -> list[dict[str, Any]]:
        """List all available tools in Anthropic tool format.

        Tool names use underscores (not dots) to satisfy OpenAI's
        ^[a-zA-Z0-9_-]+$ pattern requirement.
        """
        seen = set()
        tools = []
        for name, (pid, tool) in self._tools.items():
            if "." not in name:
                continue  # Skip short aliases to avoid duplicates
            if name in seen:
                continue
            seen.add(name)
            plugin = self._plugins.get(pid)
            if plugin and plugin.status != PluginStatus.ACTIVE:
                continue
            # Replace dots with underscores for OpenAI compatibility
            safe_name = name.replace(".", "_")
            tools.append({
                "name": safe_name,
                "description": f"[{plugin.name if plugin else pid}] {tool.description}",
                "input_schema": tool.parameters,
            })
        return tools

    def get_tool(self, name: str) -> Optional[tuple[str, PluginTool]]:
        """Find a tool by name (qualified, short, or underscore-separated)."""
        return self._tools.get(name) or self._tools.get(name.replace("_", ".", 1))

    async def invoke(self, tool_name: str, args: Optional[dict[str, Any]] = None) -> PluginResult:
        """Invoke a plugin tool by name (supports both dot and underscore formats)."""
        import time
        start = time.monotonic()

        entry = self._tools.get(tool_name) or self._tools.get(tool_name.replace("_", ".", 1))
        if not entry:
            return PluginResult(
                plugin_id="unknown", tool_name=tool_name,
                success=False, error=f"Tool '{tool_name}' not found",
            )

        plugin_id, tool = entry
        plugin = self._plugins.get(plugin_id)
        if plugin and plugin.status != PluginStatus.ACTIVE:
            return PluginResult(
                plugin_id=plugin_id, tool_name=tool_name,
                success=False, error=f"Plugin '{plugin_id}' is {plugin.status.value}",
            )

        # ── Sandbox gate check ──────────────────────────────────
        if self._sandbox_gate is not None:
            # Map alpaca_* tools to "trading", everything else to "plugins"
            tool_base = tool_name.replace(".", "_").split("_")[0] if "_" in tool_name else tool_name
            normalized_name = tool_name.replace(".", "_")
            is_trading = normalized_name in self._TRADING_TOOLS
            is_write = normalized_name in self._TRADING_WRITE_TOOLS
            gate_system = "trading" if is_trading else "plugins"
            risk = "critical" if is_write else ("medium" if is_trading else "low")
            decision = self._sandbox_gate.check(
                system_id=gate_system,
                action=f"plugin_invoke:{tool_name}",
                description=f"Invoke plugin tool {tool_name}",
                context={"plugin_id": plugin_id, "args_keys": list((args or {}).keys())},
                risk_level=risk,
            )
            if not decision.was_executed:
                elapsed = (time.monotonic() - start) * 1000
                simulated_output = {
                    "sandboxed": True,
                    "tool": tool_name,
                    "message": f"Tool '{tool_name}' blocked by sandbox gate (system={gate_system}, mode=sandbox)",
                }
                pr = PluginResult(
                    plugin_id=plugin_id, tool_name=tool_name,
                    success=True, output=simulated_output, duration_ms=round(elapsed, 1),
                )
                self._invocation_log.append(pr)
                return pr

        try:
            result = tool.handler(args or {})
            if hasattr(result, "__await__"):
                result = await result
            elapsed = (time.monotonic() - start) * 1000
            pr = PluginResult(
                plugin_id=plugin_id, tool_name=tool_name,
                success=True, output=result, duration_ms=round(elapsed, 1),
            )
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            logger.error("Plugin tool %s failed: %s", tool_name, e)
            pr = PluginResult(
                plugin_id=plugin_id, tool_name=tool_name,
                success=False, error=str(e), duration_ms=round(elapsed, 1),
            )

        self._invocation_log.append(pr)

        # Persist to state store for audit trail
        if self._state_store:
            try:
                self._state_store.log_plugin_invocation(
                    plugin_name=pr.plugin_id,
                    tool_name=pr.tool_name,
                    success=pr.success,
                    duration_ms=pr.duration_ms,
                    error_message=pr.error or "",
                )
            except Exception as e:
                logger.debug("Plugin audit log failed: %s", e)

        return pr

    def enable(self, plugin_id: str) -> bool:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        self._plugins[plugin_id] = Plugin(
            id=plugin.id, name=plugin.name, description=plugin.description,
            version=plugin.version, author=plugin.author, tools=plugin.tools,
            status=PluginStatus.ACTIVE, category=plugin.category,
            tags=plugin.tags, created_at=plugin.created_at,
        )
        return True

    def disable(self, plugin_id: str) -> bool:
        plugin = self._plugins.get(plugin_id)
        if not plugin:
            return False
        self._plugins[plugin_id] = Plugin(
            id=plugin.id, name=plugin.name, description=plugin.description,
            version=plugin.version, author=plugin.author, tools=plugin.tools,
            status=PluginStatus.DISABLED, category=plugin.category,
            tags=plugin.tags, created_at=plugin.created_at,
        )
        return True

    def get_log(self, limit: int = 50) -> list[PluginResult]:
        items = list(self._invocation_log)
        start = max(0, len(items) - limit)
        result = [items[i] for i in range(start, len(items))]
        result.reverse()
        return result

    def stats(self) -> dict[str, Any]:
        active = sum(1 for p in self._plugins.values() if p.status == PluginStatus.ACTIVE)
        return {
            "total_plugins": len(self._plugins),
            "active": active,
            "disabled": len(self._plugins) - active,
            "total_tools": len([n for n in self._tools if "." in n]),
            "total_invocations": len(self._invocation_log),
            "failures": sum(1 for r in self._invocation_log if not r.success),
        }


# ── Built-in Plugins ────────────────────────────────────────────


def build_default_plugins(
    memory_engine=None,
    skill_engine=None,
    llm=None,
    state_store=None,
    notification_engine=None,
    message_bus=None,
    experience_memory=None,
) -> PluginEngine:
    """Create plugin engine with ROOT's built-in plugins.

    Plugin definitions are split into separate modules under backend.core.plugins/:
      - system_plugins: system info, web, files, notes, shell, reminders
      - trading_plugins: Alpaca paper trading
      - utility_plugins: calculator, code analysis, financial, decisions
      - agent_tools_plugins: file writer, charts, reports, proposals, agent comms
    """
    from backend.core.plugins import (
        register_system_plugins,
        register_trading_plugins,
        register_utility_plugins,
        register_agent_tools_plugins,
        register_polymarket_plugins,
    )

    engine = PluginEngine(state_store=state_store)

    register_system_plugins(engine, memory_engine=memory_engine, skill_engine=skill_engine)
    register_utility_plugins(engine, memory_engine=memory_engine, skill_engine=skill_engine)
    register_trading_plugins(engine, memory_engine=memory_engine, skill_engine=skill_engine)
    register_polymarket_plugins(engine)
    register_agent_tools_plugins(
        engine,
        notification_engine=notification_engine,
        message_bus=message_bus,
        experience_memory=experience_memory,
    )

    return engine
