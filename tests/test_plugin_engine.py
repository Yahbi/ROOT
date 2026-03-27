"""Tests for the Plugin Engine — tool invocation, enable/disable."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from backend.core.plugin_engine import (
    PluginEngine, Plugin, PluginTool, PluginStatus, build_default_plugins,
)


def _make_plugin(pid="test", tools=None):
    """Helper to create a Plugin with minimal args."""
    if tools is None:
        tools = [
            PluginTool(
                name="echo",
                description="Echo input",
                handler=lambda args: {"echo": args.get("text", "")},
            ),
        ]
    return Plugin(id=pid, name=pid.title(), description=f"{pid} plugin", version="1.0", tools=tools)


class TestPluginEngine:
    def test_create_engine(self):
        engine = PluginEngine()
        stats = engine.stats()
        assert stats["total_plugins"] == 0
        assert stats["total_tools"] == 0

    def test_register_plugin(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        stats = engine.stats()
        assert stats["total_plugins"] == 1
        assert stats["total_tools"] == 1

    def test_list_tools(self):
        engine = PluginEngine()
        engine.register(_make_plugin(tools=[
            PluginTool(name="tool_a", description="A", handler=lambda a: None),
            PluginTool(name="tool_b", description="B", handler=lambda a: None),
        ]))
        tools = engine.list_tools()
        assert len(tools) == 2

    @pytest.mark.asyncio
    async def test_invoke_tool(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        result = await engine.invoke("echo", {"text": "hello"})
        assert result.success
        assert result.output["echo"] == "hello"

    @pytest.mark.asyncio
    async def test_invoke_nonexistent_tool(self):
        engine = PluginEngine()
        result = await engine.invoke("nonexistent")
        assert not result.success
        assert result.error is not None

    def test_enable_disable_plugin(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        plugin = engine.get_plugin("test")
        assert plugin.status == PluginStatus.ACTIVE

        engine.disable("test")
        plugin = engine.get_plugin("test")
        assert plugin.status == PluginStatus.DISABLED

        engine.enable("test")
        plugin = engine.get_plugin("test")
        assert plugin.status == PluginStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_invoke_disabled_plugin_tool(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        engine.disable("test")
        result = await engine.invoke("echo")
        assert not result.success

    def test_unregister(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        assert engine.stats()["total_plugins"] == 1
        engine.unregister("test")
        assert engine.stats()["total_plugins"] == 0

    @pytest.mark.asyncio
    async def test_invocation_log(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        await engine.invoke("echo", {"text": "hi"})
        log = engine.get_log()
        assert len(log) == 1
        assert log[0].success


class TestBuildDefaults:
    def test_build_default_plugins_creates_tools(self):
        mem = MagicMock()
        skills = MagicMock()
        engine = build_default_plugins(memory_engine=mem, skill_engine=skills)
        stats = engine.stats()
        assert stats["total_plugins"] > 0
        assert stats["total_tools"] > 0
