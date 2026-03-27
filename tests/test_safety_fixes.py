"""Tests for v1.1.0 safety fixes — approval chain, sandbox gate, trading gating."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from backend.core.approval_chain import (
    ApprovalChain,
    ApprovalRequest,
    ApprovalStatus,
    RiskLevel,
    classify_risk,
)
from backend.core.sandbox_gate import SandboxGate, SystemMode


def _make_gate():
    """Create a SandboxGate with a mock state_store."""
    mock_store = MagicMock()
    mock_store.get.return_value = None
    return SandboxGate(state_store=mock_store)


# ── Phase 1A: Hedge fund uses execute_trade (not paper_trade) ──

class TestHedgeFundApprovalAction:
    def test_execute_trade_is_critical(self):
        """execute_trade must be classified as CRITICAL risk."""
        assert classify_risk("execute_trade") == RiskLevel.CRITICAL

    @pytest.mark.asyncio
    async def test_execute_trade_returns_pending(self):
        """CRITICAL action must return PENDING, never auto-approve."""
        chain = ApprovalChain()
        result = await chain.request_approval(
            agent_id="hedge_fund",
            action="execute_trade",
            description="BUY AAPL @ 85% confidence",
        )
        assert result.status == ApprovalStatus.PENDING

    @pytest.mark.asyncio
    async def test_pending_not_auto_approved(self):
        """A PENDING approval must stay pending until explicitly resolved."""
        chain = ApprovalChain()
        result = await chain.request_approval(
            agent_id="hedge_fund",
            action="execute_trade",
            description="BUY AAPL",
        )
        pending = chain.get_pending()
        assert len(pending) >= 1
        assert any(r.id == result.id for r in pending)
        assert result.status == ApprovalStatus.PENDING


# ── Phase 1B: paper_trade is CRITICAL (defense-in-depth) ──

class TestPaperTradeClassification:
    def test_paper_trade_is_critical(self):
        """paper_trade must be CRITICAL to prevent accidental auto-approval."""
        assert classify_risk("paper_trade") == RiskLevel.CRITICAL

    def test_paper_trade_not_low(self):
        """paper_trade must never be LOW risk."""
        assert classify_risk("paper_trade") != RiskLevel.LOW

    @pytest.mark.asyncio
    async def test_paper_trade_requires_approval(self):
        """paper_trade must return PENDING, not AUTO_APPROVED."""
        chain = ApprovalChain()
        result = await chain.request_approval(
            agent_id="test", action="paper_trade", description="Test trade"
        )
        assert result.status == ApprovalStatus.PENDING


# ── Phase 1C: HIGH timeout expires (not auto-approves) ──

class TestHighTimeoutExpiry:
    @pytest.mark.asyncio
    async def test_high_risk_expires_not_approves(self):
        """HIGH risk actions must EXPIRE after timeout, never auto-approve."""
        from datetime import datetime, timedelta, timezone

        chain = ApprovalChain()
        result = await chain.request_approval(
            agent_id="test", action="send_email", description="Send alert"
        )
        assert result.status == ApprovalStatus.PENDING

        # Backdate the request to simulate timeout
        old_time = (datetime.now(timezone.utc) - timedelta(minutes=90)).isoformat()
        backdated = ApprovalRequest(
            id=result.id,
            agent_id=result.agent_id,
            action=result.action,
            description=result.description,
            risk_level=result.risk_level,
            status=result.status,
            context=result.context,
            created_at=old_time,
        )
        chain._requests[result.id] = backdated

        expired = chain.expire_stale(timeout_minutes=60)
        assert len(expired) >= 1
        expired_req = next(r for r in expired if r.id == result.id)
        assert expired_req.status == ApprovalStatus.EXPIRED
        assert expired_req.status != ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_critical_risk_expires_not_approves(self):
        """CRITICAL risk actions must also EXPIRE, never auto-approve."""
        from datetime import datetime, timedelta, timezone

        chain = ApprovalChain()
        result = await chain.request_approval(
            agent_id="test", action="execute_trade", description="Buy stock"
        )

        old_time = (datetime.now(timezone.utc) - timedelta(minutes=120)).isoformat()
        backdated = ApprovalRequest(
            id=result.id,
            agent_id=result.agent_id,
            action=result.action,
            description=result.description,
            risk_level=result.risk_level,
            status=result.status,
            context=result.context,
            created_at=old_time,
        )
        chain._requests[result.id] = backdated

        expired = chain.expire_stale(timeout_minutes=60)
        assert len(expired) >= 1
        expired_req = next(r for r in expired if r.id == result.id)
        assert expired_req.status == ApprovalStatus.EXPIRED


# ── Phase 1D: Polymarket tools in trading set ──

class TestPolymarketTradingTools:
    def test_polymarket_tools_in_trading_set(self):
        """All polymarket order tools must be in _TRADING_TOOLS."""
        from backend.core.plugin_engine import PluginEngine

        polymarket_tools = {
            "polymarket_place_order",
            "polymarket_market_order",
            "polymarket_cancel_order",
            "polymarket_cancel_all",
        }
        for tool in polymarket_tools:
            assert tool in PluginEngine._TRADING_TOOLS, f"{tool} missing from _TRADING_TOOLS"

    def test_polymarket_write_tools_critical(self):
        """Polymarket write tools must be in _TRADING_WRITE_TOOLS."""
        from backend.core.plugin_engine import PluginEngine

        write_tools = {
            "polymarket_place_order",
            "polymarket_market_order",
            "polymarket_cancel_order",
            "polymarket_cancel_all",
        }
        for tool in write_tools:
            assert tool in PluginEngine._TRADING_WRITE_TOOLS, f"{tool} missing from _TRADING_WRITE_TOOLS"

    def test_alpaca_tools_in_trading_set(self):
        """Alpaca tools must also be in _TRADING_TOOLS."""
        from backend.core.plugin_engine import PluginEngine

        assert "alpaca_place_order" in PluginEngine._TRADING_TOOLS


# ── Sandbox Gate Basics ──

class TestSandboxGateBasics:
    def test_default_mode_is_sandbox(self):
        """New SandboxGate must default to SANDBOX mode."""
        gate = _make_gate()
        assert gate._config.global_mode == SystemMode.SANDBOX

    def test_sandbox_blocks_external_actions(self):
        """Sandbox mode must block external actions."""
        gate = _make_gate()
        decision = gate.check(
            system_id="trading",
            action="execute_trade",
            description="Buy AAPL",
        )
        assert not decision.was_executed
        assert decision.mode == "sandbox"

    def test_live_mode_allows_actions(self):
        """Live mode must allow actions."""
        gate = _make_gate()
        gate.set_global_mode(SystemMode.LIVE)
        decision = gate.check(
            system_id="trading",
            action="execute_trade",
            description="Buy AAPL",
        )
        assert decision.was_executed
        assert decision.mode == "live"

    def test_per_system_override(self):
        """Per-system override must take precedence over global mode."""
        gate = _make_gate()
        gate.set_global_mode(SystemMode.LIVE)
        gate.set_system_mode("trading", SystemMode.SANDBOX)
        decision = gate.check(
            system_id="trading",
            action="execute_trade",
            description="Buy AAPL",
        )
        assert not decision.was_executed

    def test_decision_includes_category(self):
        """Gate decisions must include action_category field."""
        gate = _make_gate()
        decision = gate.check(
            system_id="trading",
            action="execute_trade",
            description="Buy AAPL",
        )
        assert hasattr(decision, "action_category")
        assert decision.action_category == "financial"
