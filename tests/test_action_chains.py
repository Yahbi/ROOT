"""Tests for ActionChainEngine — reactive pipeline linking proactive actions."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.core.action_chains import (
    ActionChain,
    ActionChainEngine,
    ChainExecution,
    build_default_chains,
)


# ── Fixtures ──────────────────────────────────────────────────────


def _make_chain(
    chain_id: str = "test_chain",
    trigger: str = "scan_action",
    follow_up: str = "trade_action",
    condition=None,
    enabled: bool = True,
    priority: int = 0,
    cooldown: int = 0,
) -> ActionChain:
    if condition is None:
        condition = lambda r: True
    return ActionChain(
        id=chain_id,
        trigger_action=trigger,
        trigger_condition=condition,
        follow_up_action=follow_up,
        follow_up_args={},
        description=f"Test chain {chain_id}",
        enabled=enabled,
        priority=priority,
        cooldown_minutes=cooldown,
    )


@pytest.fixture
def engine() -> ActionChainEngine:
    return ActionChainEngine()


@pytest.fixture
def engine_with_proactive() -> ActionChainEngine:
    proactive = AsyncMock()
    proactive.trigger = AsyncMock(return_value="follow-up executed")
    return ActionChainEngine(proactive_engine=proactive)


# ── register_chain ────────────────────────────────────────────────


class TestRegisterChain:
    def test_register_adds_chain(self, engine: ActionChainEngine) -> None:
        chain = _make_chain()
        engine.register_chain(chain)

        chains = engine.get_chains()
        assert len(chains) == 1
        assert chains[0]["id"] == "test_chain"

    def test_register_multiple_chains(self, engine: ActionChainEngine) -> None:
        engine.register_chain(_make_chain("a"))
        engine.register_chain(_make_chain("b"))
        engine.register_chain(_make_chain("c"))
        assert len(engine.get_chains()) == 3

    def test_register_empty_id_raises(self, engine: ActionChainEngine) -> None:
        with pytest.raises(ValueError, match="must have an id"):
            engine.register_chain(_make_chain(chain_id=""))

    def test_register_overwrites_same_id(self, engine: ActionChainEngine) -> None:
        engine.register_chain(_make_chain("dup", follow_up="action_a"))
        engine.register_chain(_make_chain("dup", follow_up="action_b"))
        chains = engine.get_chains()
        assert len(chains) == 1
        assert chains[0]["follow_up_action"] == "action_b"


# ── evaluate_trigger ──────────────────────────────────────────────


class TestEvaluateTrigger:
    @pytest.mark.asyncio
    async def test_condition_met_fires_follow_up(
        self, engine_with_proactive: ActionChainEngine,
    ) -> None:
        chain = _make_chain(condition=lambda r: r.get("signal_count", 0) > 0)
        engine_with_proactive.register_chain(chain)

        execs = await engine_with_proactive.evaluate_trigger(
            "scan_action", {"signal_count": 3},
        )
        assert len(execs) == 1
        assert execs[0].success is True
        assert execs[0].chain_id == "test_chain"

    @pytest.mark.asyncio
    async def test_condition_not_met_skips(
        self, engine_with_proactive: ActionChainEngine,
    ) -> None:
        chain = _make_chain(condition=lambda r: r.get("signal_count", 0) > 0)
        engine_with_proactive.register_chain(chain)

        execs = await engine_with_proactive.evaluate_trigger(
            "scan_action", {"signal_count": 0},
        )
        assert len(execs) == 0

    @pytest.mark.asyncio
    async def test_wrong_action_name_skips(
        self, engine_with_proactive: ActionChainEngine,
    ) -> None:
        chain = _make_chain(trigger="other_action")
        engine_with_proactive.register_chain(chain)

        execs = await engine_with_proactive.evaluate_trigger(
            "scan_action", {"signal_count": 5},
        )
        assert len(execs) == 0

    @pytest.mark.asyncio
    async def test_disabled_chain_skips(
        self, engine_with_proactive: ActionChainEngine,
    ) -> None:
        chain = _make_chain(enabled=False)
        engine_with_proactive.register_chain(chain)

        execs = await engine_with_proactive.evaluate_trigger(
            "scan_action", {},
        )
        assert len(execs) == 0

    @pytest.mark.asyncio
    async def test_condition_exception_skips(
        self, engine_with_proactive: ActionChainEngine,
    ) -> None:
        def bad_condition(r):
            raise RuntimeError("boom")

        chain = _make_chain(condition=bad_condition)
        engine_with_proactive.register_chain(chain)

        execs = await engine_with_proactive.evaluate_trigger(
            "scan_action", {},
        )
        assert len(execs) == 0

    @pytest.mark.asyncio
    async def test_no_proactive_engine_still_records(
        self, engine: ActionChainEngine,
    ) -> None:
        chain = _make_chain()
        engine.register_chain(chain)

        execs = await engine.evaluate_trigger("scan_action", {})
        assert len(execs) == 1
        assert execs[0].success is False
        assert "no proactive engine" in execs[0].follow_up_result

    @pytest.mark.asyncio
    async def test_priority_ordering(
        self, engine_with_proactive: ActionChainEngine,
    ) -> None:
        """Higher priority chains fire first."""
        fired_order: list[str] = []
        original_trigger = engine_with_proactive._proactive_engine.trigger

        async def track_trigger(action_name):
            fired_order.append(action_name)
            return "ok"

        engine_with_proactive._proactive_engine.trigger = track_trigger

        engine_with_proactive.register_chain(
            _make_chain("low", follow_up="low_action", priority=1),
        )
        engine_with_proactive.register_chain(
            _make_chain("high", follow_up="high_action", priority=10),
        )

        await engine_with_proactive.evaluate_trigger("scan_action", {})
        assert fired_order == ["high_action", "low_action"]


# ── Chain execution tracking ─────────────────────────────────────


class TestExecutionTracking:
    @pytest.mark.asyncio
    async def test_executions_recorded(
        self, engine_with_proactive: ActionChainEngine,
    ) -> None:
        engine_with_proactive.register_chain(_make_chain())

        await engine_with_proactive.evaluate_trigger("scan_action", {"key": "val"})

        execs = engine_with_proactive.get_executions(limit=10)
        assert len(execs) == 1
        assert execs[0]["chain_id"] == "test_chain"
        assert execs[0]["success"] is True
        assert execs[0]["triggered_at"] is not None
        assert execs[0]["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_executions_limit(
        self, engine_with_proactive: ActionChainEngine,
    ) -> None:
        engine_with_proactive.register_chain(_make_chain(cooldown=0))

        for _ in range(5):
            await engine_with_proactive.evaluate_trigger("scan_action", {})

        assert len(engine_with_proactive.get_executions(limit=3)) == 3
        assert len(engine_with_proactive.get_executions(limit=10)) == 5

    @pytest.mark.asyncio
    async def test_executions_most_recent_first(
        self, engine_with_proactive: ActionChainEngine,
    ) -> None:
        engine_with_proactive.register_chain(_make_chain(cooldown=0))

        await engine_with_proactive.evaluate_trigger("scan_action", {"i": 1})
        await engine_with_proactive.evaluate_trigger("scan_action", {"i": 2})

        execs = engine_with_proactive.get_executions()
        assert execs[0]["triggered_at"] >= execs[1]["triggered_at"]


# ── build_default_chains ──────────────────────────────────────────


class TestBuildDefaultChains:
    def test_creates_fourteen_chains(self) -> None:
        engine = build_default_chains()
        chains = engine.get_chains()
        assert len(chains) == 14

    def test_expected_chain_ids(self) -> None:
        engine = build_default_chains()
        ids = {c["id"] for c in engine.get_chains()}
        assert ids == {
            "scan_markets_to_trade",
            "business_to_directive",
            "miro_to_scan",
            "health_to_notification",
            "goals_to_assess",
            "ecosystem_to_directive",
            "experiment_to_revenue",
            "learning_to_improvement",
            "code_scanner_to_rewrite",
            "revenue_tracker_to_directive",
            "experiment_runner_to_discovery",
            "goal_stalled_to_recovery",
            "survival_to_revenue_remediation",
            "health_to_goal_assessment",
        }

    def test_chains_have_descriptions(self) -> None:
        engine = build_default_chains()
        for chain in engine.get_chains():
            assert chain["description"], f"Chain {chain['id']} missing description"

    def test_all_enabled_by_default(self) -> None:
        engine = build_default_chains()
        for chain in engine.get_chains():
            assert chain["enabled"] is True

    @pytest.mark.asyncio
    async def test_scan_markets_condition_with_signal(self) -> None:
        proactive = AsyncMock()
        proactive.trigger = AsyncMock(return_value="trade executed")
        engine = build_default_chains(proactive_engine=proactive)

        execs = await engine.evaluate_trigger(
            "market_scanner", {"result": "found 3 signals", "signal_count": 2},
        )
        assert len(execs) == 1

    @pytest.mark.asyncio
    async def test_scan_markets_condition_no_signal(self) -> None:
        proactive = AsyncMock()
        proactive.trigger = AsyncMock(return_value="ok")
        engine = build_default_chains(proactive_engine=proactive)

        execs = await engine.evaluate_trigger(
            "market_scanner", {"result": "markets quiet"},
        )
        assert len(execs) == 0

    @pytest.mark.asyncio
    async def test_health_condition_with_error(self) -> None:
        proactive = AsyncMock()
        proactive.trigger = AsyncMock(return_value="notified")
        engine = build_default_chains(proactive_engine=proactive)

        execs = await engine.evaluate_trigger(
            "health_monitor", {"result": "agent X is unhealthy"},
        )
        # health_to_notification + health_to_goal_assessment both trigger
        assert len(execs) == 2

    @pytest.mark.asyncio
    async def test_miro_high_confidence_triggers(self) -> None:
        proactive = AsyncMock()
        proactive.trigger = AsyncMock(return_value="scanned")
        engine = build_default_chains(proactive_engine=proactive)

        execs = await engine.evaluate_trigger(
            "miro_prediction", {"confidence": 85, "result": "BTC bullish"},
        )
        assert len(execs) == 1


# ── stats ─────────────────────────────────────────────────────────


class TestStats:
    def test_stats_empty(self, engine: ActionChainEngine) -> None:
        s = engine.stats()
        assert s["total_chains"] == 0
        assert s["total_executions"] == 0
        assert s["success_rate"] == 0.0

    def test_stats_with_chains(self, engine: ActionChainEngine) -> None:
        engine.register_chain(_make_chain("a"))
        engine.register_chain(_make_chain("b", enabled=False))
        s = engine.stats()
        assert s["total_chains"] == 2
        assert s["enabled_chains"] == 1

    @pytest.mark.asyncio
    async def test_stats_after_executions(
        self, engine_with_proactive: ActionChainEngine,
    ) -> None:
        engine_with_proactive.register_chain(_make_chain(cooldown=0))

        await engine_with_proactive.evaluate_trigger("scan_action", {})
        await engine_with_proactive.evaluate_trigger("scan_action", {})

        s = engine_with_proactive.stats()
        assert s["total_executions"] == 2
        assert s["successful_executions"] == 2
        assert s["failed_executions"] == 0
        assert s["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_stats_with_failures(
        self, engine: ActionChainEngine,
    ) -> None:
        """No proactive engine means follow-ups record as failures."""
        engine.register_chain(_make_chain(cooldown=0))

        await engine.evaluate_trigger("scan_action", {})

        s = engine.stats()
        assert s["total_executions"] == 1
        assert s["failed_executions"] == 1
        assert s["success_rate"] == 0.0


# ── Frozen dataclass immutability ─────────────────────────────────


class TestImmutability:
    def test_action_chain_is_frozen(self) -> None:
        chain = _make_chain()
        with pytest.raises(AttributeError):
            chain.enabled = False  # type: ignore[misc]

    def test_chain_execution_is_frozen(self) -> None:
        execution = ChainExecution(
            id="x", chain_id="y", trigger_result="t",
            follow_up_result="f", triggered_at="now",
            completed_at="later", success=True,
        )
        with pytest.raises(AttributeError):
            execution.success = False  # type: ignore[misc]
