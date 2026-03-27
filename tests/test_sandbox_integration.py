"""Integration tests for v1.1.1 sandbox gate wiring across all modules.

Verifies that sandbox gate actually blocks actions in revenue_engine,
money_engine, directive_engine, action_chains, and agent_collab.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.sandbox_gate import GateDecision, SandboxGate, SystemMode


def _make_state_store(tmp_path: Path) -> MagicMock:
    """Create a mock state_store backed by a real SQLite connection."""
    db_path = tmp_path / "sandbox_test.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    store = MagicMock()
    store.conn = conn
    store.get.return_value = None
    return store


def _make_gate(tmp_path: Path) -> SandboxGate:
    """Create a SandboxGate in SANDBOX mode with a real DB."""
    store = _make_state_store(tmp_path)
    return SandboxGate(state_store=store)


def _make_blocking_gate(tmp_path: Path) -> SandboxGate:
    """Create a gate in sandbox mode — all checks return was_executed=False."""
    gate = _make_gate(tmp_path)
    assert gate.global_mode == SystemMode.SANDBOX
    return gate


def _make_live_gate(tmp_path: Path) -> SandboxGate:
    """Create a gate in live mode — all checks return was_executed=True."""
    gate = _make_gate(tmp_path)
    gate.set_global_mode(SystemMode.LIVE)
    return gate


# ── Revenue Engine ──────────────────────────────────────────────


class TestRevenueEngineSandbox:
    """Revenue engine methods respect sandbox gate."""

    def _make_engine(self, tmp_path: Path, gate: SandboxGate):
        from backend.core.revenue_engine import RevenueEngine

        engine = RevenueEngine(db_path=tmp_path / "revenue.db")
        engine.start()
        engine._sandbox_gate = gate
        return engine

    def test_record_revenue_blocked_in_sandbox(self, tmp_path):
        gate = _make_blocking_gate(tmp_path)
        engine = self._make_engine(tmp_path, gate)

        product = engine.add_product("Test SaaS", "micro_saas")
        engine.record_revenue(product.id, 500.0, "test revenue")

        products = engine.get_products()
        found = [p for p in products if p.id == product.id]
        assert len(found) == 1
        assert found[0].monthly_revenue == 0.0

        engine.stop()

    def test_record_cost_blocked_in_sandbox(self, tmp_path):
        gate = _make_blocking_gate(tmp_path)
        engine = self._make_engine(tmp_path, gate)

        product = engine.add_product("Test API", "data_products")
        engine.record_cost(product.id, 100.0, "test cost")

        products = engine.get_products()
        found = [p for p in products if p.id == product.id]
        assert len(found) == 1
        assert found[0].monthly_cost == 0.0

        engine.stop()

    def test_auto_remediate_blocked_in_sandbox(self, tmp_path):
        gate = _make_blocking_gate(tmp_path)
        engine = self._make_engine(tmp_path, gate)

        engine.add_product("Loser", "content_network", monthly_cost=10000.0)

        result = engine.auto_remediate()
        assert result.get("sandboxed") is True or result.get("emergency") is False

        engine.stop()

    def test_record_revenue_allowed_in_live(self, tmp_path):
        gate = _make_live_gate(tmp_path)
        engine = self._make_engine(tmp_path, gate)

        product = engine.add_product("Live SaaS", "micro_saas")
        engine.record_revenue(product.id, 750.0, "live revenue")

        products = engine.get_products()
        found = [p for p in products if p.id == product.id]
        assert len(found) == 1
        assert found[0].monthly_revenue == 750.0

        engine.stop()


# ── Money Engine ────────────────────────────────────────────────


class TestMoneyEngineSandbox:
    """Money engine online council respects sandbox gate."""

    @pytest.mark.asyncio
    async def test_online_council_falls_back_to_offline_when_sandboxed(self, tmp_path):
        from backend.core.money_engine import MoneyEngine

        gate = _make_blocking_gate(tmp_path)
        engine = MoneyEngine(
            memory=MagicMock(), skills=MagicMock(), self_dev=MagicMock(),
        )
        engine._sandbox_gate = gate

        mock_session = MagicMock()
        mock_session.id = "test_session"
        engine.convene_council = AsyncMock(return_value=mock_session)

        result = await engine.convene_council_online(focus="test focus")
        engine.convene_council.assert_called_once_with(focus="test focus")
        assert result == mock_session

    @pytest.mark.asyncio
    async def test_online_council_proceeds_when_live(self, tmp_path):
        from backend.core.money_engine import MoneyEngine

        gate = _make_live_gate(tmp_path)
        engine = MoneyEngine(
            memory=MagicMock(), skills=MagicMock(), self_dev=MagicMock(),
        )
        engine._sandbox_gate = gate
        engine._llm = AsyncMock()
        engine._collab = AsyncMock()

        mock_session = MagicMock()
        engine._run_session = AsyncMock(return_value=mock_session)

        result = await engine.convene_council_online(focus="live test")
        engine._run_session.assert_called_once_with("live test", mode="online")


# ── Directive Engine ────────────────────────────────────────────


class TestDirectiveEngineSandbox:
    """Directive dispatch respects sandbox gate."""

    @pytest.mark.asyncio
    async def test_directive_dispatch_blocked_in_sandbox(self, tmp_path):
        from backend.core.directive_engine import Directive, DirectiveEngine

        gate = _make_blocking_gate(tmp_path)
        engine = DirectiveEngine()
        # Set up a real SQLite connection for directive storage
        db_path = tmp_path / "directives.db"
        conn = sqlite3.connect(str(db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        engine._conn = conn
        engine._create_tables()
        engine._sandbox_gate = gate
        engine._collab = AsyncMock()

        # Create a directive directly
        directive = Directive(
            id="dir_test_001",
            title="Test directive",
            rationale="Testing sandbox",
            category="trading",
            assigned_agents=("researcher",),
        )

        result = await engine._dispatch_directive(directive)
        assert result is not None
        assert result.status == "failed"
        assert "sandbox" in (result.result or "").lower()

        conn.close()


# ── Action Chains ───────────────────────────────────────────────


class TestActionChainsSandbox:
    """Action chain external follow-ups respect sandbox gate."""

    @pytest.mark.asyncio
    async def test_external_followup_blocked_in_sandbox(self, tmp_path):
        from backend.core.action_chains import (
            ActionChain,
            ActionChainEngine,
            _EXTERNAL_FOLLOW_UPS,
        )

        gate = _make_blocking_gate(tmp_path)
        proactive = AsyncMock()

        engine = ActionChainEngine(proactive_engine=proactive)
        engine._sandbox_gate = gate

        chain = ActionChain(
            id="test_chain",
            trigger_action="market_scanner",
            trigger_condition=lambda r: True,
            follow_up_action="auto_trade_cycle",  # External
            follow_up_args={},
            description="Test chain",
        )
        engine.register_chain(chain)

        executions = await engine.evaluate_trigger(
            "market_scanner", {"signal_count": 5}
        )
        assert len(executions) == 1
        assert not executions[0].success
        assert "sandbox" in executions[0].follow_up_result.lower()

        # Proactive engine should NOT have been called
        proactive.trigger.assert_not_called()

    @pytest.mark.asyncio
    async def test_internal_followup_passes_through(self, tmp_path):
        from backend.core.action_chains import ActionChain, ActionChainEngine

        gate = _make_blocking_gate(tmp_path)
        proactive = AsyncMock(return_value="scanned")

        engine = ActionChainEngine(proactive_engine=proactive)
        engine._sandbox_gate = gate

        chain = ActionChain(
            id="test_internal",
            trigger_action="goal_tracker",
            trigger_condition=lambda r: True,
            follow_up_action="goal_assessment",  # Internal — not gated
            follow_up_args={},
            description="Internal chain",
        )
        engine.register_chain(chain)

        executions = await engine.evaluate_trigger(
            "goal_tracker", {"status": "stalled"}
        )
        assert len(executions) == 1
        assert executions[0].success
        proactive.trigger.assert_called_once_with("goal_assessment")

    def test_external_followups_set_is_correct(self):
        from backend.core.action_chains import _EXTERNAL_FOLLOW_UPS

        expected = {
            "auto_trade_cycle", "directive", "revenue_seeder",
            "self_rewrite", "notification", "business_discovery",
        }
        assert _EXTERNAL_FOLLOW_UPS == expected


# ── Agent Collaboration ─────────────────────────────────────────


class TestAgentCollabSandbox:
    """Agent collaboration external-domain agents respect sandbox gate."""

    @pytest.mark.asyncio
    async def test_trading_agent_blocked_in_sandbox(self, tmp_path):
        from backend.core.agent_collab import AgentCollaboration

        gate = _make_blocking_gate(tmp_path)
        registry = MagicMock()
        connector = MagicMock()
        connector.send_task = AsyncMock(return_value={"result": "trade executed"})
        registry.get_connector.return_value = connector

        collab = AgentCollaboration(registry=registry)
        collab._sandbox_gate = gate

        result = await collab._execute_single("swarm", "Execute AAPL trade")
        assert "[SANDBOX]" in result.get("result", "")
        connector.send_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_miro_agent_blocked_in_sandbox(self, tmp_path):
        from backend.core.agent_collab import AgentCollaboration

        gate = _make_blocking_gate(tmp_path)
        registry = MagicMock()
        connector = MagicMock()
        connector.send_task = AsyncMock(return_value={"result": "prediction made"})
        registry.get_connector.return_value = connector

        collab = AgentCollaboration(registry=registry)
        collab._sandbox_gate = gate

        result = await collab._execute_single("miro", "Predict BTC direction")
        assert "[SANDBOX]" in result.get("result", "")

    @pytest.mark.asyncio
    async def test_internal_agent_passes_through(self, tmp_path):
        from backend.core.agent_collab import AgentCollaboration

        gate = _make_blocking_gate(tmp_path)
        registry = MagicMock()
        connector = MagicMock()
        connector.send_task = AsyncMock(return_value={"result": "research done"})
        registry.get_connector.return_value = connector

        collab = AgentCollaboration(registry=registry)
        collab._sandbox_gate = gate

        result = await collab._execute_single("researcher", "Research AI trends")
        # Should pass through — researcher is internal domain
        assert "[SANDBOX]" not in result.get("result", "")

    def test_agent_domain_mapping(self):
        from backend.core.agent_collab import AgentCollaboration

        assert AgentCollaboration._agent_to_domain("swarm") == "trading"
        assert AgentCollaboration._agent_to_domain("miro") == "market"
        assert AgentCollaboration._agent_to_domain("analyst") == "market"
        assert AgentCollaboration._agent_to_domain("researcher") == "research"
        assert AgentCollaboration._agent_to_domain("coder") == "code"
        assert AgentCollaboration._agent_to_domain("unknown") == "research"


# ── Fail-Closed Test ────────────────────────────────────────────


class TestSandboxFailClosed:
    """When sandbox gate check() raises, execution must NOT proceed."""

    @pytest.mark.asyncio
    async def test_action_chain_fails_closed_on_gate_error(self, tmp_path):
        """Gate crash on external follow-up — the error bubbles into the
        ChainExecution's follow_up_result via the existing try/except."""
        from backend.core.action_chains import ActionChain, ActionChainEngine

        gate = MagicMock()
        gate.check.side_effect = RuntimeError("Gate DB crashed")
        proactive = AsyncMock()

        engine = ActionChainEngine(proactive_engine=proactive)
        engine._sandbox_gate = gate

        chain = ActionChain(
            id="fail_closed",
            trigger_action="market_scanner",
            trigger_condition=lambda r: True,
            follow_up_action="auto_trade_cycle",
            follow_up_args={},
            description="Should fail closed",
        )
        engine.register_chain(chain)

        executions = await engine.evaluate_trigger(
            "market_scanner", {"signal_count": 1}
        )
        # The gate error should be caught by the outer try/except in _execute_follow_up
        assert len(executions) == 1
        assert not executions[0].success
        assert "error" in executions[0].follow_up_result.lower()
        proactive.trigger.assert_not_called()

    @pytest.mark.asyncio
    async def test_agent_collab_fails_closed_on_gate_error(self, tmp_path):
        from backend.core.agent_collab import AgentCollaboration

        gate = MagicMock()
        gate.check.side_effect = RuntimeError("Gate DB crashed")
        registry = MagicMock()
        connector = MagicMock()
        connector.send_task = AsyncMock()
        registry.get_connector.return_value = connector

        collab = AgentCollaboration(registry=registry)
        collab._sandbox_gate = gate

        result = await collab._execute_single("swarm", "Trade something")
        # The error is caught by _execute_single's outer try/except
        assert "error" in str(result).lower()
        connector.send_task.assert_not_called()
