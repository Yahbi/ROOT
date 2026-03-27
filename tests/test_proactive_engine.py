"""Tests for ProactiveEngine — autonomous background actions for ROOT."""

from __future__ import annotations

import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Mock the proactive_actions module before it gets imported by proactive_engine.
# This avoids needing the real module and its dependencies.
_HANDLER_NAMES = [
    "assess_goals",
    "auto_recover_goals",
    "auto_remediate_revenue",
    "auto_trade_cycle",
    "business_discovery",
    "check_approval_timeouts",
    "check_health",
    "consolidate_knowledge",
    "correlate_projects",
    "data_intelligence",
    "discover_skills",
    "drain_task_queue",
    "evolve_agents",
    "experiment_proposer",
    "miro_continuous_assess",
    "miro_predict",
    "monitor_polymarket_positions",
    "polymarket_trade_cycle",
    "run_experiments",
    "scan_code_improvements",
    "scan_github",
    "scan_markets",
    "scan_opportunities",
    "scan_polymarkets",
    "scan_project_ecosystem",
    "seed_revenue_products",
    "self_rewrite",
    "survival_economics",
    "track_goals",
    "track_revenue_health",
    "validate_strategies",
]

# Pre-populate sys.modules with a fake proactive_actions module
_fake_actions_module = MagicMock()
for _name in _HANDLER_NAMES:
    setattr(_fake_actions_module, _name, MagicMock())
sys.modules.setdefault("backend.core.proactive_actions", _fake_actions_module)

from backend.core.proactive_engine import ProactiveAction, ProactiveEngine  # noqa: E402


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def proactive():
    engine = ProactiveEngine()
    return engine


# ── ProactiveAction creation ─────────────────────────────────────


class TestProactiveAction:
    def test_creation_defaults(self):
        action = ProactiveAction(
            name="test_action",
            description="A test action",
            interval_seconds=60,
            handler=AsyncMock(),
        )
        assert action.name == "test_action"
        assert action.description == "A test action"
        assert action.interval_seconds == 60
        assert action.enabled is True
        assert action.risk_level == "low"
        assert action.last_run is None
        assert action.run_count == 0
        assert action.error_count == 0
        assert action.last_result is None

    def test_creation_custom_values(self):
        handler = AsyncMock()
        action = ProactiveAction(
            name="risky",
            description="Risky action",
            interval_seconds=120,
            handler=handler,
            enabled=False,
            risk_level="critical",
        )
        assert action.name == "risky"
        assert action.enabled is False
        assert action.risk_level == "critical"
        assert action.handler is handler


# ── Registration ─────────────────────────────────────────────────


class TestRegistration:
    def test_register_default_actions_count(self, proactive):
        """_register_default_actions() should register exactly 33 actions."""
        assert len(proactive._actions) == 33

    def test_all_expected_action_names(self, proactive):
        expected = {
            "health_monitor",
            "knowledge_consolidation",
            "goal_tracker",
            "opportunity_scanner",
            "agent_evolution",
            "skill_discovery",
            "market_scanner",
            "github_scanner",
            "self_rewrite",
            "miro_prediction",
            "data_intelligence",
            "task_queue_drainer",
            "auto_trade_cycle",
            "goal_assessment",
            "survival_economics",
            "miro_continuous",
            "miro_world_intelligence",
            "miro_daily_briefing",
            "business_discovery",
            "experiment_proposer",
            "revenue_seeder",
            "ecosystem_scanner",
            "experiment_runner",
            "code_scanner",
            "revenue_tracker",
            "project_correlator",
            "approval_timeout",
            "goal_auto_recovery",
            "revenue_remediation",
            "strategy_validator",
            "polymarket_scanner",
            "polymarket_trade_cycle",
            "polymarket_monitor",
        }
        assert set(proactive._actions.keys()) == expected


# ── get_actions ──────────────────────────────────────────────────


class TestGetActions:
    @pytest.mark.asyncio
    async def test_returns_list_of_dicts(self, proactive):
        actions = await proactive.get_actions()
        assert isinstance(actions, list)
        assert len(actions) == 33

    @pytest.mark.asyncio
    async def test_action_dict_keys(self, proactive):
        actions = await proactive.get_actions()
        expected_keys = {
            "name",
            "description",
            "enabled",
            "interval_seconds",
            "risk_level",
            "last_run",
            "run_count",
            "error_count",
            "last_result",
        }
        for action_dict in actions:
            assert set(action_dict.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_last_result_truncated(self, proactive):
        """last_result should be truncated to 200 chars in get_actions()."""
        action = proactive._actions["health_monitor"]
        action.last_result = "x" * 500
        actions = await proactive.get_actions()
        health = next(a for a in actions if a["name"] == "health_monitor")
        assert len(health["last_result"]) == 200


# ── enable / disable ────────────────────────────────────────────


class TestEnableDisable:
    @pytest.mark.asyncio
    async def test_disable_action(self, proactive):
        assert proactive._actions["health_monitor"].enabled is True
        result = await proactive.disable("health_monitor")
        assert result is True
        assert proactive._actions["health_monitor"].enabled is False

    @pytest.mark.asyncio
    async def test_enable_action(self, proactive):
        await proactive.disable("health_monitor")
        result = await proactive.enable("health_monitor")
        assert result is True
        assert proactive._actions["health_monitor"].enabled is True

    @pytest.mark.asyncio
    async def test_disable_nonexistent(self, proactive):
        result = await proactive.disable("nonexistent_action")
        assert result is False

    @pytest.mark.asyncio
    async def test_enable_nonexistent(self, proactive):
        result = await proactive.enable("nonexistent_action")
        assert result is False

    @pytest.mark.asyncio
    async def test_enable_preserves_action_properties(self, proactive):
        """enable() creates a new ProactiveAction; verify properties are copied."""
        original = proactive._actions["health_monitor"]
        original_desc = original.description
        original_interval = original.interval_seconds
        original_risk = original.risk_level

        await proactive.disable("health_monitor")
        await proactive.enable("health_monitor")

        updated = proactive._actions["health_monitor"]
        assert updated.description == original_desc
        assert updated.interval_seconds == original_interval
        assert updated.risk_level == original_risk


# ── stats ────────────────────────────────────────────────────────


class TestStats:
    @pytest.mark.asyncio
    async def test_stats_initial(self, proactive):
        stats = await proactive.stats()
        assert stats["running"] is False
        assert stats["total_actions"] == 33
        assert stats["enabled"] == 33
        assert stats["total_runs"] == 0
        assert stats["total_errors"] == 0
        assert stats["success_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_after_disable(self, proactive):
        await proactive.disable("health_monitor")
        stats = await proactive.stats()
        assert stats["enabled"] == 32

    @pytest.mark.asyncio
    async def test_stats_with_runs(self, proactive):
        proactive._actions["health_monitor"].run_count = 10
        proactive._actions["health_monitor"].error_count = 2
        stats = await proactive.stats()
        assert stats["total_runs"] == 10
        assert stats["total_errors"] == 2
        assert stats["success_rate"] == 0.8


# ── trigger ──────────────────────────────────────────────────────


class TestTrigger:
    @pytest.mark.asyncio
    async def test_trigger_nonexistent(self, proactive):
        result = await proactive.trigger("nonexistent_action")
        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_existing(self, proactive):
        handler = AsyncMock(return_value="health OK")
        proactive._actions["health_monitor"].handler = handler

        result = await proactive.trigger("health_monitor")
        handler.assert_awaited_once()
        assert result == "health OK"


# ── _execute_action ──────────────────────────────────────────────


class TestExecuteAction:
    @pytest.mark.asyncio
    async def test_low_risk_skips_approval(self, proactive):
        """Low risk actions should not call approval.request_approval."""
        approval = AsyncMock()
        proactive._approval = approval
        handler = AsyncMock(return_value="done")
        proactive._actions["health_monitor"].handler = handler

        result = await proactive._execute_action(proactive._actions["health_monitor"])
        approval.request_approval.assert_not_awaited()
        assert result == "done"

    @pytest.mark.asyncio
    async def test_medium_risk_with_approval(self, proactive):
        """Medium risk actions should go through approval chain."""
        from backend.core.approval_chain import ApprovalStatus

        approval_result = MagicMock()
        approval_result.status = ApprovalStatus.APPROVED
        approval = AsyncMock()
        approval.request_approval = AsyncMock(return_value=approval_result)
        proactive._approval = approval

        handler = AsyncMock(return_value="scanned")
        proactive._actions["opportunity_scanner"].handler = handler

        result = await proactive._execute_action(
            proactive._actions["opportunity_scanner"],
        )
        approval.request_approval.assert_awaited_once()
        handler.assert_awaited_once()
        assert result == "scanned"

    @pytest.mark.asyncio
    async def test_rejected_approval(self, proactive):
        """Rejected approval should return 'rejected by approval chain'."""
        from backend.core.approval_chain import ApprovalStatus

        approval_result = MagicMock()
        approval_result.status = ApprovalStatus.REJECTED
        approval = AsyncMock()
        approval.request_approval = AsyncMock(return_value=approval_result)
        proactive._approval = approval

        handler = AsyncMock()
        proactive._actions["opportunity_scanner"].handler = handler

        result = await proactive._execute_action(
            proactive._actions["opportunity_scanner"],
        )
        assert result == "rejected by approval chain"
        handler.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_count_incremented(self, proactive):
        handler = AsyncMock(return_value="ok")
        proactive._actions["health_monitor"].handler = handler

        await proactive._execute_action(proactive._actions["health_monitor"])
        assert proactive._actions["health_monitor"].run_count == 1

    @pytest.mark.asyncio
    async def test_last_run_set(self, proactive):
        handler = AsyncMock(return_value="ok")
        proactive._actions["health_monitor"].handler = handler

        await proactive._execute_action(proactive._actions["health_monitor"])
        assert proactive._actions["health_monitor"].last_run is not None

    @pytest.mark.asyncio
    async def test_error_increments_error_count(self, proactive):
        handler = AsyncMock(side_effect=RuntimeError("boom"))
        proactive._actions["health_monitor"].handler = handler

        with pytest.raises(RuntimeError, match="boom"):
            await proactive._execute_action(proactive._actions["health_monitor"])
        assert proactive._actions["health_monitor"].error_count == 1


# ── Bus publishing ───────────────────────────────────────────────


class TestBusPublishing:
    @pytest.mark.asyncio
    async def test_publish_on_result(self, proactive):
        """Result should be published to bus after execution."""
        bus = MagicMock()
        msg = MagicMock()
        bus.create_message = MagicMock(return_value=msg)
        bus.publish = AsyncMock()
        proactive._bus = bus

        handler = AsyncMock(return_value="scan complete")
        proactive._actions["health_monitor"].handler = handler

        await proactive._execute_action(proactive._actions["health_monitor"])

        bus.create_message.assert_called_once()
        call_kwargs = bus.create_message.call_args
        assert call_kwargs[1]["topic"] == "system.proactive"
        assert call_kwargs[1]["sender"] == "proactive_engine"
        assert "health_monitor" in call_kwargs[1]["payload"]["action"]
        bus.publish.assert_awaited_once_with(msg)

    @pytest.mark.asyncio
    async def test_no_publish_when_no_result(self, proactive):
        """Bus should not be called when handler returns None."""
        bus = MagicMock()
        bus.publish = AsyncMock()
        proactive._bus = bus

        handler = AsyncMock(return_value=None)
        proactive._actions["health_monitor"].handler = handler

        await proactive._execute_action(proactive._actions["health_monitor"])
        bus.publish.assert_not_awaited()


# ── State persistence ────────────────────────────────────────────


class TestStatePersistence:
    @pytest.mark.asyncio
    async def test_save_state_after_success(self, proactive):
        """state_store.save_proactive_state should be called on success."""
        state_store = MagicMock()
        proactive._state_store = state_store

        handler = AsyncMock(return_value="persisted")
        proactive._actions["health_monitor"].handler = handler

        await proactive._execute_action(proactive._actions["health_monitor"])

        state_store.save_proactive_state.assert_called_once_with(
            "health_monitor",
            1,
            0,
            proactive._actions["health_monitor"].last_run,
            "persisted",
        )

    @pytest.mark.asyncio
    async def test_save_state_after_error(self, proactive):
        """state_store.save_proactive_state should be called on error too."""
        state_store = MagicMock()
        proactive._state_store = state_store

        handler = AsyncMock(side_effect=RuntimeError("fail"))
        proactive._actions["health_monitor"].handler = handler

        with pytest.raises(RuntimeError):
            await proactive._execute_action(proactive._actions["health_monitor"])

        state_store.save_proactive_state.assert_called_once()
        args = state_store.save_proactive_state.call_args[0]
        assert args[0] == "health_monitor"
        assert args[2] == 1  # error_count


# ── Chain engine evaluation ──────────────────────────────────────


class TestChainEngine:
    @pytest.mark.asyncio
    async def test_evaluate_trigger_called(self, proactive):
        """chain_engine.evaluate_trigger should be called after execution."""
        chain_engine = MagicMock()
        chain_engine.evaluate_trigger = AsyncMock()
        proactive.set_chain_engine(chain_engine)

        handler = AsyncMock(return_value="chain result")
        proactive._actions["health_monitor"].handler = handler

        await proactive._execute_action(proactive._actions["health_monitor"])

        chain_engine.evaluate_trigger.assert_awaited_once_with(
            "health_monitor",
            {"result": "chain result"},
        )

    @pytest.mark.asyncio
    async def test_chain_engine_error_does_not_propagate(self, proactive):
        """Chain evaluation errors should be caught, not propagated."""
        chain_engine = MagicMock()
        chain_engine.evaluate_trigger = AsyncMock(
            side_effect=RuntimeError("chain broke"),
        )
        proactive.set_chain_engine(chain_engine)

        handler = AsyncMock(return_value="ok")
        proactive._actions["health_monitor"].handler = handler

        # Should not raise even though chain_engine fails
        result = await proactive._execute_action(proactive._actions["health_monitor"])
        assert result == "ok"


# ── set_chain_engine ─────────────────────────────────────────────


class TestSetChainEngine:
    def test_set_chain_engine(self, proactive):
        assert proactive._chain_engine is None
        engine = MagicMock()
        proactive.set_chain_engine(engine)
        assert proactive._chain_engine is engine
