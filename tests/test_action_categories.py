"""Tests for action category classification and live mode policies."""

from __future__ import annotations

import pytest

from backend.core.action_categories import (
    ActionCategory,
    CategoryPolicy,
    LIVE_MODE_POLICIES,
    classify_action_category,
    get_policy,
)


class TestClassifyActionCategory:
    def test_financial_exact_match(self):
        assert classify_action_category("execute_trade") == ActionCategory.FINANCIAL
        assert classify_action_category("transfer_funds") == ActionCategory.FINANCIAL
        assert classify_action_category("polymarket_place_order") == ActionCategory.FINANCIAL

    def test_communication_exact_match(self):
        assert classify_action_category("send_email") == ActionCategory.COMMUNICATION
        assert classify_action_category("post_content") == ActionCategory.COMMUNICATION
        assert classify_action_category("create_pr") == ActionCategory.COMMUNICATION

    def test_deployment_exact_match(self):
        assert classify_action_category("deploy") == ActionCategory.DEPLOYMENT
        assert classify_action_category("run_migration") == ActionCategory.DEPLOYMENT
        assert classify_action_category("self_rewrite") == ActionCategory.DEPLOYMENT

    def test_data_access_exact_match(self):
        assert classify_action_category("market_scan") == ActionCategory.DATA_ACCESS
        assert classify_action_category("web_search") == ActionCategory.DATA_ACCESS
        assert classify_action_category("fetch_prices") == ActionCategory.DATA_ACCESS

    def test_system_exact_match(self):
        assert classify_action_category("health_check") == ActionCategory.SYSTEM
        assert classify_action_category("status_query") == ActionCategory.SYSTEM

    def test_financial_prefix_match(self):
        assert classify_action_category("execute_trade:AAPL") == ActionCategory.FINANCIAL
        assert classify_action_category("plugin_invoke:alpaca_place_order") == ActionCategory.FINANCIAL
        assert classify_action_category("plugin_invoke:polymarket_place_order") == ActionCategory.FINANCIAL

    def test_data_access_prefix_match(self):
        assert classify_action_category("market_scan:AAPL") == ActionCategory.DATA_ACCESS
        assert classify_action_category("plugin_invoke:polymarket_markets") == ActionCategory.DATA_ACCESS
        assert classify_action_category("plugin_invoke:alpaca_positions") == ActionCategory.DATA_ACCESS

    def test_context_money_escalation(self):
        assert classify_action_category("unknown_action", {"involves_money": True}) == ActionCategory.FINANCIAL

    def test_context_email_escalation(self):
        assert classify_action_category("unknown_action", {"sends_email": True}) == ActionCategory.COMMUNICATION

    def test_context_deploy_escalation(self):
        assert classify_action_category("unknown_action", {"deploys": True}) == ActionCategory.DEPLOYMENT

    def test_unknown_defaults_to_data_access(self):
        """Unknown actions should default to DATA_ACCESS (safe — low notification)."""
        assert classify_action_category("something_completely_new") == ActionCategory.DATA_ACCESS

    def test_case_insensitive(self):
        assert classify_action_category("Execute_Trade") == ActionCategory.FINANCIAL
        assert classify_action_category("SEND_EMAIL") == ActionCategory.COMMUNICATION

    def test_space_to_underscore(self):
        assert classify_action_category("execute trade") == ActionCategory.FINANCIAL


class TestLiveModePolicies:
    def test_all_categories_have_policies(self):
        """Every ActionCategory must have a corresponding policy."""
        for cat in ActionCategory:
            assert cat in LIVE_MODE_POLICIES, f"Missing policy for {cat.value}"

    def test_financial_requires_approval(self):
        policy = LIVE_MODE_POLICIES[ActionCategory.FINANCIAL]
        assert policy.requires_approval is True
        assert policy.notification_level == "critical"
        assert policy.auto_execute_delay_seconds == -1  # never auto-execute

    def test_communication_requires_approval(self):
        policy = LIVE_MODE_POLICIES[ActionCategory.COMMUNICATION]
        assert policy.requires_approval is True
        assert policy.notification_level == "high"

    def test_deployment_requires_approval(self):
        policy = LIVE_MODE_POLICIES[ActionCategory.DEPLOYMENT]
        assert policy.requires_approval is True
        assert policy.notification_level == "high"

    def test_data_access_auto_executes(self):
        policy = LIVE_MODE_POLICIES[ActionCategory.DATA_ACCESS]
        assert policy.requires_approval is False
        assert policy.auto_execute_delay_seconds == 0

    def test_system_auto_executes(self):
        policy = LIVE_MODE_POLICIES[ActionCategory.SYSTEM]
        assert policy.requires_approval is False
        assert policy.notification_level == "none"

    def test_internal_never_gated(self):
        policy = LIVE_MODE_POLICIES[ActionCategory.INTERNAL]
        assert policy.requires_approval is False
        assert policy.notification_level == "none"
        assert policy.auto_execute_delay_seconds == 0

    def test_policy_frozen(self):
        """CategoryPolicy must be immutable."""
        policy = LIVE_MODE_POLICIES[ActionCategory.FINANCIAL]
        with pytest.raises(AttributeError):
            policy.requires_approval = False  # type: ignore


class TestGetPolicy:
    def test_returns_correct_policy(self):
        policy = get_policy(ActionCategory.FINANCIAL)
        assert isinstance(policy, CategoryPolicy)
        assert policy.category == ActionCategory.FINANCIAL

    def test_all_categories_resolve(self):
        for cat in ActionCategory:
            policy = get_policy(cat)
            assert policy.category == cat
