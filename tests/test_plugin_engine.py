"""Tests for the Plugin Engine — tool invocation, enable/disable, and extended features."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from backend.core.plugin_engine import (
    PluginEngine, Plugin, PluginTool, PluginStatus, PluginSandbox,
    PluginMarketplace, PluginConfigSchema, PluginConfigField, PluginHealth,
    build_default_plugins,
)


def _make_plugin(pid="test", tools=None, **kwargs):
    """Helper to create a Plugin with minimal args."""
    if tools is None:
        tools = [
            PluginTool(
                name="echo",
                description="Echo input",
                handler=lambda args: {"echo": args.get("text", "")},
            ),
        ]
    return Plugin(id=pid, name=pid.title(), description=f"{pid} plugin", version="1.0", tools=tools, **kwargs)


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


# ── Dependency Management ──────────────────────────────────────


class TestDependencyManagement:
    def test_register_with_no_deps(self):
        engine = PluginEngine()
        engine.register(_make_plugin("base"))
        assert engine.get_plugin("base") is not None

    def test_register_satisfied_dependency(self):
        engine = PluginEngine()
        engine.register(_make_plugin("base"))
        engine.register(_make_plugin("child", dependencies=("base",)))
        assert engine.get_plugin("child") is not None

    def test_register_missing_dependency_raises(self):
        engine = PluginEngine()
        with pytest.raises(ValueError, match="depends on unregistered plugins"):
            engine.register(_make_plugin("child", dependencies=("missing_dep",)))

    def test_dependency_graph(self):
        engine = PluginEngine()
        engine.register(_make_plugin("base"))
        engine.register(_make_plugin("child", dependencies=("base",)))
        graph = engine.dependency_graph()
        assert graph["base"] == []
        assert graph["child"] == ["base"]

    def test_stats_plugins_with_deps(self):
        engine = PluginEngine()
        engine.register(_make_plugin("base"))
        engine.register(_make_plugin("child", dependencies=("base",)))
        stats = engine.stats()
        assert stats["plugins_with_deps"] == 1


# ── Version History ────────────────────────────────────────────


class TestVersionHistory:
    def test_first_registration_creates_history(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        history = engine.version_history("test")
        assert len(history) == 1
        assert history[0]["version"] == "1.0"

    def test_version_note_stored(self):
        engine = PluginEngine()
        engine.register(_make_plugin(), version_note="Initial release")
        history = engine.version_history("test")
        assert history[0]["note"] == "Initial release"

    def test_re_register_appends_history(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        p2 = Plugin(
            id="test", name="Test", description="test plugin", version="2.0",
            tools=_make_plugin().tools,
        )
        engine.register(p2, version_note="Upgraded to 2.0")
        history = engine.version_history("test")
        assert len(history) == 2
        assert history[-1]["version"] == "2.0"

    def test_empty_history_for_unknown_plugin(self):
        engine = PluginEngine()
        assert engine.version_history("unknown") == []


# ── Hot-Reload ─────────────────────────────────────────────────


class TestHotReload:
    def test_reload_replaces_handler(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        # Replace with updated handler
        new_tool = PluginTool(
            name="echo",
            description="Updated echo",
            handler=lambda args: {"echo": "updated"},
        )
        new_plugin = Plugin(
            id="test", name="Test", description="test plugin", version="1.1",
            tools=[new_tool],
        )
        engine.reload(new_plugin, version_note="Updated echo handler")
        assert engine.get_plugin("test").version == "1.1"

    @pytest.mark.asyncio
    async def test_reload_new_handler_is_called(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        new_tool = PluginTool(
            name="echo",
            description="Updated echo",
            handler=lambda args: {"echo": "reloaded"},
        )
        new_plugin = Plugin(
            id="test", name="Test", description="test plugin", version="1.1",
            tools=[new_tool],
        )
        engine.reload(new_plugin)
        result = await engine.invoke("echo", {"text": "x"})
        assert result.success
        assert result.output["echo"] == "reloaded"

    def test_reload_preserves_health_counters(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        # Seed some health data directly
        engine._health["test"].total_invocations = 10
        new_plugin = Plugin(
            id="test", name="Test", description="test plugin", version="1.1",
            tools=_make_plugin().tools,
        )
        engine.reload(new_plugin)
        # Health must not be reset
        assert engine._health["test"].total_invocations == 10

    def test_reload_appends_version_history(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        new_plugin = Plugin(
            id="test", name="Test", description="test plugin", version="1.1",
            tools=_make_plugin().tools,
        )
        engine.reload(new_plugin, version_note="Hot-reloaded")
        history = engine.version_history("test")
        assert len(history) == 2
        assert history[-1]["note"] == "Hot-reloaded"


# ── Sandboxing ─────────────────────────────────────────────────


class TestSandboxing:
    @pytest.mark.asyncio
    async def test_output_within_limit_passes(self):
        sandbox = PluginSandbox(max_output_bytes=1_048_576)
        plugin = _make_plugin(sandbox=sandbox)
        engine = PluginEngine()
        engine.register(plugin)
        result = await engine.invoke("echo", {"text": "hello"})
        assert result.success
        assert "truncated" not in (result.output or {})

    @pytest.mark.asyncio
    async def test_output_exceeding_limit_is_truncated(self):
        # Set a very small limit (10 bytes) so any output exceeds it
        sandbox = PluginSandbox(max_output_bytes=10)
        plugin = _make_plugin(sandbox=sandbox)
        engine = PluginEngine()
        engine.register(plugin)
        result = await engine.invoke("echo", {"text": "hello"})
        assert result.success
        assert result.output.get("truncated") is True

    def test_read_only_fs_warns_on_write_tool(self, caplog):
        sandbox = PluginSandbox(read_only_fs=True)
        plugin = Plugin(
            id="ro_test", name="RO Test", description="read-only test", version="1.0",
            tools=[
                PluginTool(name="write_file", description="Write file", handler=lambda a: None),
            ],
            sandbox=sandbox,
        )
        engine = PluginEngine()
        import logging
        with caplog.at_level(logging.WARNING, logger="root.plugins"):
            engine.register(plugin)
        assert any("read_only_fs" in rec.message or "write_file" in rec.message for rec in caplog.records)

    def test_dependency_missing_raises_not_registers(self):
        """Sandboxing dependency check prevents unsafe plugin from registering."""
        engine = PluginEngine()
        with pytest.raises(ValueError):
            engine.register(_make_plugin("unsafe", dependencies=("nonexistent",)))
        assert engine.get_plugin("unsafe") is None


# ── Marketplace Metadata ───────────────────────────────────────


class TestMarketplaceMetadata:
    def test_default_marketplace_values(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        listing = engine.marketplace_listing("test")
        assert listing is not None
        assert listing["rating"] == 0.0
        assert listing["downloads"] == 0
        assert listing["verified"] is False
        assert listing["license"] == "MIT"

    def test_custom_marketplace_values(self):
        mp = PluginMarketplace(rating=4.8, downloads=1500, verified=True, homepage="https://example.com")
        engine = PluginEngine()
        engine.register(_make_plugin(marketplace=mp))
        listing = engine.marketplace_listing("test")
        assert listing["rating"] == 4.8
        assert listing["downloads"] == 1500
        assert listing["verified"] is True
        assert listing["homepage"] == "https://example.com"

    def test_marketplace_all_returns_all_plugins(self):
        engine = PluginEngine()
        engine.register(_make_plugin("a"))
        engine.register(_make_plugin("b"))
        listings = engine.marketplace_all()
        assert len(listings) == 2

    def test_marketplace_listing_unknown_returns_none(self):
        engine = PluginEngine()
        assert engine.marketplace_listing("ghost") is None

    def test_marketplace_listing_includes_tool_count(self):
        engine = PluginEngine()
        engine.register(_make_plugin(tools=[
            PluginTool(name="t1", description="d", handler=lambda a: None),
            PluginTool(name="t2", description="d", handler=lambda a: None),
        ]))
        listing = engine.marketplace_listing("test")
        assert listing["tool_count"] == 2


# ── Health Monitoring ──────────────────────────────────────────


class TestHealthMonitoring:
    def test_health_initialized_on_register(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        health = engine.get_health("test")
        assert health is not None
        assert health.total_invocations == 0

    @pytest.mark.asyncio
    async def test_health_updated_on_success(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        await engine.invoke("echo", {"text": "hi"})
        health = engine.get_health("test")
        assert health.total_invocations == 1
        assert health.total_errors == 0
        assert health.error_rate == 0.0

    @pytest.mark.asyncio
    async def test_health_updated_on_failure(self):
        def boom(args):
            raise RuntimeError("simulated error")

        engine = PluginEngine()
        engine.register(Plugin(
            id="err", name="Err", description="d", version="1.0",
            tools=[PluginTool(name="fail", description="fails", handler=boom)],
        ))
        result = await engine.invoke("fail")
        assert not result.success
        health = engine.get_health("err")
        assert health.total_errors == 1
        assert health.error_rate == 1.0
        assert health.last_error is not None

    @pytest.mark.asyncio
    async def test_unhealthy_plugin_detection(self):
        def boom(args):
            raise RuntimeError("fail")

        engine = PluginEngine()
        engine.register(Plugin(
            id="sick", name="Sick", description="d", version="1.0",
            tools=[PluginTool(name="fail", description="fails", handler=boom)],
        ))
        for _ in range(10):
            await engine.invoke("fail")
        unhealthy = engine.unhealthy_plugins(min_error_rate=0.5, min_invocations=5)
        assert "sick" in unhealthy

    @pytest.mark.asyncio
    async def test_auto_error_status_after_5_consecutive_failures(self):
        def boom(args):
            raise RuntimeError("fail")

        engine = PluginEngine()
        engine.register(Plugin(
            id="crash", name="Crash", description="d", version="1.0",
            tools=[PluginTool(name="fail", description="fails", handler=boom)],
        ))
        for _ in range(5):
            await engine.invoke("fail")
        plugin = engine.get_plugin("crash")
        assert plugin.status == PluginStatus.ERROR

    def test_all_health_returns_list(self):
        engine = PluginEngine()
        engine.register(_make_plugin("a"))
        engine.register(_make_plugin("b"))
        all_h = engine.all_health()
        assert len(all_h) == 2

    def test_health_error_rate_property(self):
        h = PluginHealth(plugin_id="x")
        assert h.error_rate == 0.0
        h.total_invocations = 4
        h.total_errors = 1
        assert h.error_rate == 0.25

    def test_health_avg_duration(self):
        h = PluginHealth(plugin_id="x")
        h.total_invocations = 2
        h.total_duration_ms = 100.0
        assert h.avg_duration_ms == 50.0


# ── Config UI Schema ───────────────────────────────────────────


class TestConfigSchema:
    def test_empty_schema_returns_empty_list(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        schema = engine.config_schema("test")
        assert schema == []

    def test_schema_with_fields(self):
        fields = (
            PluginConfigField(
                key="api_key", label="API Key", field_type="password",
                required=True, env_var="MY_API_KEY",
            ),
            PluginConfigField(
                key="mode", label="Mode", field_type="select",
                options=("fast", "slow"), default="fast",
            ),
        )
        schema_obj = PluginConfigSchema(fields=fields)
        engine = PluginEngine()
        engine.register(_make_plugin(config_schema=schema_obj))
        schema = engine.config_schema("test")
        assert len(schema) == 2
        assert schema[0]["key"] == "api_key"
        assert schema[0]["type"] == "password"
        assert schema[0]["required"] is True
        assert schema[0]["env_var"] == "MY_API_KEY"
        assert schema[1]["options"] == ["fast", "slow"]

    def test_config_schema_unknown_plugin_returns_none(self):
        engine = PluginEngine()
        assert engine.config_schema("ghost") is None


# ── Stats extended ─────────────────────────────────────────────


class TestStatsExtended:
    def test_stats_includes_error_status_count(self):
        engine = PluginEngine()
        engine.register(_make_plugin())
        engine._swap_status("test", PluginStatus.ERROR)
        stats = engine.stats()
        assert stats["error"] == 1
        assert stats["active"] == 0

    def test_stats_includes_unhealthy_list(self):
        engine = PluginEngine()
        stats = engine.stats()
        assert "unhealthy_plugins" in stats
        assert isinstance(stats["unhealthy_plugins"], list)


class TestBuildDefaults:
    def test_build_default_plugins_creates_tools(self):
        mem = MagicMock()
        skills = MagicMock()
        engine = build_default_plugins(memory_engine=mem, skill_engine=skills)
        stats = engine.stats()
        assert stats["total_plugins"] > 0
        assert stats["total_tools"] > 0

    def test_build_default_plugins_version_history_populated(self):
        mem = MagicMock()
        skills = MagicMock()
        engine = build_default_plugins(memory_engine=mem, skill_engine=skills)
        # Every plugin should have at least one version history entry
        for plugin in engine.list_plugins():
            history = engine.version_history(plugin.id)
            assert len(history) >= 1, f"No version history for plugin '{plugin.id}'"

    def test_build_default_plugins_health_initialized(self):
        mem = MagicMock()
        skills = MagicMock()
        engine = build_default_plugins(memory_engine=mem, skill_engine=skills)
        all_h = engine.all_health()
        assert len(all_h) == len(engine.list_plugins())
