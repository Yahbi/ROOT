"""Tests for the Approval Chain — risk classification and approval flow."""

from __future__ import annotations

import pytest

from backend.core.approval_chain import (
    ApprovalChain,
    ApprovalStatus,
    RiskLevel,
    classify_risk,
)


class TestRiskClassification:
    def test_low_risk_actions(self):
        assert classify_risk("search") == RiskLevel.LOW
        assert classify_risk("analyze") == RiskLevel.LOW
        assert classify_risk("web_search") == RiskLevel.LOW

    def test_low_risk_expanded_actions(self):
        # These moved from MEDIUM to LOW for more autonomy
        assert classify_risk("draft_email") == RiskLevel.LOW
        assert classify_risk("generate_code") == RiskLevel.LOW
        assert classify_risk("create_task") == RiskLevel.LOW

    def test_medium_risk_actions(self):
        assert classify_risk("deploy_staging") == RiskLevel.MEDIUM
        assert classify_risk("run_migration") == RiskLevel.MEDIUM

    def test_high_risk_actions(self):
        assert classify_risk("send_email") == RiskLevel.HIGH
        assert classify_risk("run_shell_command") == RiskLevel.HIGH

    def test_critical_risk_actions(self):
        assert classify_risk("execute_trade") == RiskLevel.CRITICAL
        assert classify_risk("delete_data") == RiskLevel.CRITICAL

    def test_context_escalation(self):
        assert classify_risk("unknown", {"involves_money": True}) == RiskLevel.CRITICAL
        assert classify_risk("unknown", {"external_communication": True}) == RiskLevel.HIGH

    def test_default_is_medium(self):
        assert classify_risk("some_unknown_action") == RiskLevel.MEDIUM


class TestApprovalChain:
    @pytest.mark.asyncio
    async def test_low_risk_auto_approved(self):
        chain = ApprovalChain()
        result = await chain.request_approval("test", "search", "Search the web")
        assert result.status == ApprovalStatus.AUTO_APPROVED

    @pytest.mark.asyncio
    async def test_medium_risk_auto_approved_with_notify(self):
        chain = ApprovalChain()
        result = await chain.request_approval("test", "deploy_staging", "Deploy to staging")
        assert result.status == ApprovalStatus.AUTO_APPROVED
        assert result.resolver == "auto_notify"

    @pytest.mark.asyncio
    async def test_high_risk_pending(self):
        chain = ApprovalChain()
        result = await chain.request_approval("test", "send_email", "Send an email")
        assert result.status == ApprovalStatus.PENDING
        assert len(chain.get_pending()) == 1

    @pytest.mark.asyncio
    async def test_approve_pending(self):
        chain = ApprovalChain()
        result = await chain.request_approval("test", "send_email", "Send an email")
        approved = chain.approve(result.id)
        assert approved is not None
        assert approved.status == ApprovalStatus.APPROVED
        assert len(chain.get_pending()) == 0

    @pytest.mark.asyncio
    async def test_reject_pending(self):
        chain = ApprovalChain()
        result = await chain.request_approval("test", "send_email", "Send an email")
        rejected = chain.reject(result.id)
        assert rejected is not None
        assert rejected.status == ApprovalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_history_bounded(self):
        chain = ApprovalChain()
        for i in range(600):
            await chain.request_approval("test", "search", f"Search {i}")
        assert len(chain._history) <= 500
