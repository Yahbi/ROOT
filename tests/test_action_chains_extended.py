"""Extended tests for ActionChainEngine — cooldown, multi-chain, error handling."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.action_chains import (
    ActionChain,
    ActionChainEngine,
    ChainExecution,
    build_default_chains,
)


# ── Helpers ───────────────────────────────────────────────────────────


def _chain(
    chain_id: str = "c1",
    trigger: str = "scan_action",
    follow_up: str = "trade_action",
    condition=None,
    enabled: bool = True,
    priority: int = 5,
    cooldown: int = 0,
) -> ActionChain:
    cond = condition if condition is not None else (lambda r: True)
    return ActionChain(
        id=chain_id,
        trigger_action=trigger,
        trigger_condition=cond,
        follow_up_action=follow_up,
        follow_up_args={},
        description=f"Test chain {chain_id}",
        enabled=enabled,
        priority=priority,
        cooldown_minutes=cooldown,
    )


@pytest.fixture
def proactive():
    p = AsyncMock()
    p.trigger = AsyncMock(return_value="executed")
    return p


@pytest.fixture
def engine(proactive):
    return ActionChainEngine(proactive_engine=proactive)


# ── Cooldown Logic ─────────────────────────────────────────────────────


class TestCooldown:
    @pytest.mark.asyncio
    async def test_cooldown_prevents_immediate_refire(self, engine: ActionChainEngine):
        chain = _chain(cooldown=60)  # 60 minute cooldown
        engine.register_chain(chain)
        execs1 = await engine.evaluate_trigger("scan_action", {})
        execs2 = await engine.evaluate_trigger("scan_action", {})
        assert len(execs1) == 1
        assert len(execs2) == 0  # Blocked by cooldown

    @pytest.mark.asyncio
    async def test_zero_cooldown_fires_every_time(self, engine: ActionChainEngine):
        chain = _chain(cooldown=0)
        engine.register_chain(chain)
        for _ in range(3):
            execs = await engine.evaluate_trigger("scan_action", {})
            assert len(execs) == 1

    @pytest.mark.asyncio
    async def test_different_triggers_unaffected_by_cooldown(self, engine: ActionChainEngine):
        c1 = _chain("c1", trigger="trigger_a", cooldown=60)
        c2 = _chain("c2", trigger="trigger_b", cooldown=0)
        engine.register_chain(c1)
        engine.register_chain(c2)
        await engine.evaluate_trigger("trigger_a", {})
        await engine.evaluate_trigger("trigger_a", {})  # Blocked
        execs_b = await engine.evaluate_trigger("trigger_b", {})
        assert len(execs_b) == 1  # trigger_b unaffected


# ── Multiple Chains Same Trigger ──────────────────────────────────────


class TestMultipleChains:
    @pytest.mark.asyncio
    async def test_multiple_chains_same_trigger(self, engine: ActionChainEngine):
        c1 = _chain("c1", trigger="scan_action", follow_up="action_a", priority=1)
        c2 = _chain("c2", trigger="scan_action", follow_up="action_b", priority=2)
        c3 = _chain("c3", trigger="scan_action", follow_up="action_c", priority=3)
        for c in (c1, c2, c3):
            engine.register_chain(c)
        execs = await engine.evaluate_trigger("scan_action", {})
        assert len(execs) == 3

    @pytest.mark.asyncio
    async def test_chains_sorted_by_priority_descending(self, engine: ActionChainEngine):
        fired: list[str] = []

        async def track(action_name):
            fired.append(action_name)
            return "ok"

        engine._proactive_engine.trigger = track
        c_low = _chain("low", follow_up="low_action", priority=1)
        c_mid = _chain("mid", follow_up="mid_action", priority=5)
        c_high = _chain("high", follow_up="high_action", priority=10)
        engine.register_chain(c_low)
        engine.register_chain(c_high)
        engine.register_chain(c_mid)
        await engine.evaluate_trigger("scan_action", {})
        assert fired == ["high_action", "mid_action", "low_action"]

    @pytest.mark.asyncio
    async def test_partial_condition_match(self, engine: ActionChainEngine):
        c_match = _chain("match", condition=lambda r: r.get("ok") is True)
        c_no_match = _chain("no_match", condition=lambda r: r.get("ok") is False)
        engine.register_chain(c_match)
        engine.register_chain(c_no_match)
        execs = await engine.evaluate_trigger("scan_action", {"ok": True})
        assert len(execs) == 1
        assert execs[0].chain_id == "match"


# ── Error Handling ────────────────────────────────────────────────────


class TestErrorHandling:
    @pytest.mark.asyncio
    async def test_proactive_trigger_exception_captured(self, proactive: AsyncMock):
        proactive.trigger.side_effect = RuntimeError("trigger crashed")
        engine = ActionChainEngine(proactive_engine=proactive)
        engine.register_chain(_chain())
        execs = await engine.evaluate_trigger("scan_action", {})
        assert len(execs) == 1
        assert execs[0].success is False
        assert "trigger crashed" in execs[0].follow_up_result

    @pytest.mark.asyncio
    async def test_condition_exception_skips_chain(self, engine: ActionChainEngine):
        def bad(r):
            raise RuntimeError("boom")
        chain = _chain(condition=bad)
        engine.register_chain(chain)
        execs = await engine.evaluate_trigger("scan_action", {})
        assert len(execs) == 0

    @pytest.mark.asyncio
    async def test_disabled_chain_never_fires(self, engine: ActionChainEngine):
        chain = _chain(enabled=False)
        engine.register_chain(chain)
        execs = await engine.evaluate_trigger("scan_action", {})
        assert len(execs) == 0


# ── Execution Tracking ────────────────────────────────────────────────


class TestExecutionTracking:
    @pytest.mark.asyncio
    async def test_execution_records_chain_id(self, engine: ActionChainEngine):
        engine.register_chain(_chain("tracked_chain"))
        await engine.evaluate_trigger("scan_action", {})
        execs = engine.get_executions()
        assert execs[0]["chain_id"] == "tracked_chain"

    @pytest.mark.asyncio
    async def test_execution_records_timestamps(self, engine: ActionChainEngine):
        engine.register_chain(_chain())
        await engine.evaluate_trigger("scan_action", {})
        execs = engine.get_executions()
        assert execs[0]["triggered_at"]
        assert execs[0]["completed_at"]

    @pytest.mark.asyncio
    async def test_execution_records_trigger_result(self, engine: ActionChainEngine):
        engine.register_chain(_chain())
        await engine.evaluate_trigger("scan_action", {"signal_count": 5})
        execs = engine.get_executions()
        # trigger_result is the input dict representation
        assert execs[0]["trigger_result"] is not None

    @pytest.mark.asyncio
    async def test_executions_cap_at_limit(self, engine: ActionChainEngine):
        engine.register_chain(_chain(cooldown=0))
        for _ in range(100):
            await engine.evaluate_trigger("scan_action", {})
        execs = engine.get_executions(limit=10)
        assert len(execs) == 10

    @pytest.mark.asyncio
    async def test_most_recent_execution_first(self, engine: ActionChainEngine):
        engine.register_chain(_chain(cooldown=0))
        await engine.evaluate_trigger("scan_action", {"i": 1})
        await engine.evaluate_trigger("scan_action", {"i": 2})
        execs = engine.get_executions(limit=2)
        assert execs[0]["triggered_at"] >= execs[1]["triggered_at"]


# ── Build Default Chains ──────────────────────────────────────────────


class TestDefaultChains:
    def test_default_chains_count(self):
        engine = build_default_chains()
        assert len(engine.get_chains()) == 14

    def test_all_default_chains_enabled(self):
        engine = build_default_chains()
        for chain in engine.get_chains():
            assert chain["enabled"] is True, f"Chain {chain['id']} should be enabled"

    def test_all_default_chains_have_descriptions(self):
        engine = build_default_chains()
        for chain in engine.get_chains():
            assert chain["description"], f"Chain {chain['id']} missing description"

    @pytest.mark.asyncio
    async def test_goals_stalled_triggers(self):
        p = AsyncMock()
        p.trigger = AsyncMock(return_value="assessed")
        engine = build_default_chains(proactive_engine=p)
        execs = await engine.evaluate_trigger("goal_assessment", {"result": "stalled goal"})
        matching = [e for e in execs if e.chain_id == "goal_stalled_to_recovery"]
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_survival_triggers_remediation(self):
        p = AsyncMock()
        p.trigger = AsyncMock(return_value="remediated")
        engine = build_default_chains(proactive_engine=p)
        execs = await engine.evaluate_trigger(
            "financial_survival", {"result": "emergency mode active"},
        )
        matching = [e for e in execs if e.chain_id == "survival_to_revenue_remediation"]
        assert len(matching) == 1

    @pytest.mark.asyncio
    async def test_learning_triggers_improvement(self):
        p = AsyncMock()
        p.trigger = AsyncMock(return_value="improved")
        engine = build_default_chains(proactive_engine=p)
        execs = await engine.evaluate_trigger(
            "learning_cycle", {"result": "completed learning with improvements"},
        )
        matching = [e for e in execs if e.chain_id == "learning_to_improvement"]
        assert len(matching) == 1


# ── ChainExecution Immutability ───────────────────────────────────────


class TestChainExecutionImmutability:
    def test_frozen_dataclass(self):
        exec_ = ChainExecution(
            id="e1", chain_id="c1", trigger_result="tr",
            follow_up_result="fr", triggered_at="t1",
            completed_at="t2", success=True,
        )
        with pytest.raises(AttributeError):
            exec_.success = False

    def test_all_fields_accessible(self):
        exec_ = ChainExecution(
            id="e1", chain_id="c1", trigger_result="tr",
            follow_up_result="fr", triggered_at="t1",
            completed_at="t2", success=True,
        )
        assert exec_.id == "e1"
        assert exec_.chain_id == "c1"
        assert exec_.success is True


# ── Register/Overwrite ─────────────────────────────────────────────────


class TestRegisterChain:
    def test_register_overwrites_same_id(self):
        engine = ActionChainEngine()
        engine.register_chain(_chain("dup", follow_up="a1"))
        engine.register_chain(_chain("dup", follow_up="a2"))
        chains = engine.get_chains()
        assert len(chains) == 1
        assert chains[0]["follow_up_action"] == "a2"

    def test_empty_id_raises_value_error(self):
        engine = ActionChainEngine()
        with pytest.raises(ValueError, match="must have an id"):
            engine.register_chain(_chain(chain_id=""))
