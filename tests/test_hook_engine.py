"""Tests for HookEngine — registration, firing, error handling, default hooks."""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock

from backend.core.hook_engine import (
    Hook,
    HookEngine,
    HookEvent,
    HookResult,
    build_default_hooks,
)


@pytest.fixture
def engine() -> HookEngine:
    return HookEngine()


def _make_hook(
    name: str = "test_hook",
    event: HookEvent = HookEvent.ON_CHAT,
    handler=None,
    priority: int = 50,
    enabled: bool = True,
    condition=None,
) -> Hook:
    return Hook(
        name=name,
        event=event,
        handler=handler or (lambda ctx: f"handled by {name}"),
        priority=priority,
        enabled=enabled,
        condition=condition,
    )


class TestHookResultDataclass:
    def test_frozen(self):
        result = HookResult(hook_name="h", event=HookEvent.ON_CHAT, success=True)
        with pytest.raises(AttributeError):
            result.success = False  # type: ignore[misc]

    def test_defaults(self):
        result = HookResult(hook_name="h", event=HookEvent.ON_CHAT, success=True)
        assert result.output == ""
        assert result.blocked is False
        assert result.timestamp  # auto-populated


class TestHookDataclass:
    def test_frozen(self):
        hook = _make_hook()
        with pytest.raises(AttributeError):
            hook.name = "other"  # type: ignore[misc]

    def test_defaults(self):
        hook = _make_hook()
        assert hook.enabled is True
        assert hook.priority == 50
        assert hook.condition is None


class TestRegister:
    def test_register_hook(self, engine: HookEngine):
        hook = _make_hook()
        engine.register(hook)
        assert len(engine.get_hooks(HookEvent.ON_CHAT)) == 1

    def test_register_multiple_events(self, engine: HookEngine):
        engine.register(_make_hook(name="a", event=HookEvent.ON_CHAT))
        engine.register(_make_hook(name="b", event=HookEvent.ON_ERROR))
        assert len(engine.get_hooks(HookEvent.ON_CHAT)) == 1
        assert len(engine.get_hooks(HookEvent.ON_ERROR)) == 1

    def test_priority_ordering(self, engine: HookEngine):
        engine.register(_make_hook(name="low", priority=90))
        engine.register(_make_hook(name="high", priority=10))
        engine.register(_make_hook(name="mid", priority=50))
        hooks = engine.get_hooks(HookEvent.ON_CHAT)
        assert [h.name for h in hooks] == ["high", "mid", "low"]


class TestUnregister:
    def test_unregister_existing(self, engine: HookEngine):
        engine.register(_make_hook(name="removable"))
        engine.unregister("removable")
        assert len(engine.get_hooks(HookEvent.ON_CHAT)) == 0

    def test_unregister_nonexistent(self, engine: HookEngine):
        # Should not raise
        engine.unregister("nonexistent")

    def test_unregister_only_named(self, engine: HookEngine):
        engine.register(_make_hook(name="keep"))
        engine.register(_make_hook(name="remove"))
        engine.unregister("remove")
        hooks = engine.get_hooks(HookEvent.ON_CHAT)
        assert len(hooks) == 1
        assert hooks[0].name == "keep"


class TestFire:
    @pytest.mark.asyncio
    async def test_fire_sync_handler(self, engine: HookEngine):
        engine.register(_make_hook(handler=lambda ctx: "ok"))
        results = await engine.fire(HookEvent.ON_CHAT)
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].output == "ok"

    @pytest.mark.asyncio
    async def test_fire_async_handler(self, engine: HookEngine):
        async def async_handler(ctx):
            return "async ok"

        engine.register(_make_hook(handler=async_handler))
        results = await engine.fire(HookEvent.ON_CHAT)
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].output == "async ok"

    @pytest.mark.asyncio
    async def test_fire_with_context(self, engine: HookEngine):
        engine.register(_make_hook(handler=lambda ctx: ctx.get("msg", "")))
        results = await engine.fire(HookEvent.ON_CHAT, context={"msg": "hello"})
        assert results[0].output == "hello"

    @pytest.mark.asyncio
    async def test_fire_no_context(self, engine: HookEngine):
        engine.register(_make_hook(handler=lambda ctx: str(ctx)))
        results = await engine.fire(HookEvent.ON_CHAT)
        assert results[0].success is True

    @pytest.mark.asyncio
    async def test_fire_skips_disabled(self, engine: HookEngine):
        engine.register(_make_hook(name="disabled", enabled=False))
        results = await engine.fire(HookEvent.ON_CHAT)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_fire_skips_failing_condition(self, engine: HookEngine):
        engine.register(_make_hook(condition=lambda ctx: False))
        results = await engine.fire(HookEvent.ON_CHAT)
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_fire_passes_condition(self, engine: HookEngine):
        engine.register(_make_hook(condition=lambda ctx: True))
        results = await engine.fire(HookEvent.ON_CHAT)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_fire_error_handling(self, engine: HookEngine):
        def bad_handler(ctx):
            raise ValueError("boom")

        engine.register(_make_hook(handler=bad_handler))
        results = await engine.fire(HookEvent.ON_CHAT)
        assert len(results) == 1
        assert results[0].success is False
        assert "boom" in results[0].output

    @pytest.mark.asyncio
    async def test_fire_preserves_order(self, engine: HookEngine):
        engine.register(_make_hook(name="first", priority=10, handler=lambda ctx: "1"))
        engine.register(_make_hook(name="second", priority=20, handler=lambda ctx: "2"))
        results = await engine.fire(HookEvent.ON_CHAT)
        assert [r.output for r in results] == ["1", "2"]

    @pytest.mark.asyncio
    async def test_fire_wrong_event_empty(self, engine: HookEngine):
        engine.register(_make_hook(event=HookEvent.ON_CHAT))
        results = await engine.fire(HookEvent.ON_ERROR)
        assert results == []

    @pytest.mark.asyncio
    async def test_fire_handler_returning_none(self, engine: HookEngine):
        engine.register(_make_hook(handler=lambda ctx: None))
        results = await engine.fire(HookEvent.ON_CHAT)
        assert results[0].success is True
        assert results[0].output == ""


class TestGetHooks:
    def test_get_all_hooks(self, engine: HookEngine):
        engine.register(_make_hook(name="a", event=HookEvent.ON_CHAT))
        engine.register(_make_hook(name="b", event=HookEvent.ON_ERROR))
        all_hooks = engine.get_hooks()
        assert len(all_hooks) == 2

    def test_get_by_event(self, engine: HookEngine):
        engine.register(_make_hook(name="a", event=HookEvent.ON_CHAT))
        engine.register(_make_hook(name="b", event=HookEvent.ON_ERROR))
        assert len(engine.get_hooks(HookEvent.ON_CHAT)) == 1


class TestGetLog:
    @pytest.mark.asyncio
    async def test_log_records_executions(self, engine: HookEngine):
        engine.register(_make_hook())
        await engine.fire(HookEvent.ON_CHAT)
        log = engine.get_log()
        assert len(log) == 1

    @pytest.mark.asyncio
    async def test_log_limit(self, engine: HookEngine):
        engine.register(_make_hook())
        for _ in range(5):
            await engine.fire(HookEvent.ON_CHAT)
        log = engine.get_log(limit=3)
        assert len(log) == 3

    @pytest.mark.asyncio
    async def test_log_reverse_order(self, engine: HookEngine):
        engine.register(_make_hook(handler=lambda ctx: "a"))
        await engine.fire(HookEvent.ON_CHAT)
        engine.unregister("test_hook")
        engine.register(_make_hook(handler=lambda ctx: "b"))
        await engine.fire(HookEvent.ON_CHAT)
        log = engine.get_log()
        assert log[0].output == "b"  # Most recent first


class TestStats:
    def test_empty_stats(self, engine: HookEngine):
        stats = engine.stats()
        assert stats["total_hooks"] == 0
        assert stats["executions"] == 0
        assert stats["failures"] == 0

    @pytest.mark.asyncio
    async def test_stats_after_execution(self, engine: HookEngine):
        engine.register(_make_hook())
        await engine.fire(HookEvent.ON_CHAT)
        stats = engine.stats()
        assert stats["total_hooks"] == 1
        assert stats["executions"] == 1
        assert stats["failures"] == 0

    @pytest.mark.asyncio
    async def test_stats_counts_failures(self, engine: HookEngine):
        engine.register(_make_hook(handler=lambda ctx: (_ for _ in ()).throw(ValueError("x"))))
        # The generator trick won't work; use a proper handler
        engine.unregister("test_hook")

        def bad(ctx):
            raise RuntimeError("fail")

        engine.register(_make_hook(handler=bad))
        await engine.fire(HookEvent.ON_CHAT)
        stats = engine.stats()
        assert stats["failures"] == 1


class TestBuildDefaultHooks:
    def test_creates_engine(self):
        engine = build_default_hooks()
        assert isinstance(engine, HookEngine)

    def test_registers_hooks(self):
        engine = build_default_hooks()
        all_hooks = engine.get_hooks()
        assert len(all_hooks) >= 5

    def test_has_boot_logger(self):
        engine = build_default_hooks()
        startup_hooks = engine.get_hooks(HookEvent.ON_STARTUP)
        names = [h.name for h in startup_hooks]
        assert "boot_logger" in names

    def test_has_interaction_counter(self):
        engine = build_default_hooks()
        chat_hooks = engine.get_hooks(HookEvent.ON_CHAT)
        names = [h.name for h in chat_hooks]
        assert "interaction_counter" in names

    @pytest.mark.asyncio
    async def test_startup_hook_fires(self):
        engine = build_default_hooks()
        results = await engine.fire(HookEvent.ON_STARTUP)
        assert any(r.success for r in results)

    @pytest.mark.asyncio
    async def test_chat_counter_increments(self):
        engine = build_default_hooks()
        await engine.fire(HookEvent.ON_CHAT, {"msg": "hi"})
        results = await engine.fire(HookEvent.ON_CHAT, {"msg": "hi"})
        counter_result = [r for r in results if r.hook_name == "interaction_counter"]
        assert counter_result[0].output == "interaction #2"

    @pytest.mark.asyncio
    async def test_on_learn_hook(self):
        engine = build_default_hooks()
        results = await engine.fire(
            HookEvent.ON_LEARN,
            {"content": "test memory", "memory_type": "fact"},
        )
        assert any(r.success and "fact" in r.output for r in results)

    @pytest.mark.asyncio
    async def test_error_hook_without_memory(self):
        engine = build_default_hooks(memory_engine=None)
        results = await engine.fire(
            HookEvent.ON_ERROR,
            {"error": "test error", "source": "test"},
        )
        assert any(r.success for r in results)

    @pytest.mark.asyncio
    async def test_skill_reindex_without_engine(self):
        engine = build_default_hooks(skill_engine=None)
        results = await engine.fire(
            HookEvent.ON_SKILL_CREATE,
            {"name": "test_skill"},
        )
        assert any(r.success for r in results)

    @pytest.mark.asyncio
    async def test_routing_feedback_without_learning(self):
        engine = build_default_hooks(learning_engine=None)
        results = await engine.fire(
            HookEvent.ON_RESPONSE,
            {"agent_id": "test", "quality": 0.8, "category": "coding"},
        )
        assert any("no learning engine" in r.output for r in results)
