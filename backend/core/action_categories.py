"""
Action Categories — Classifies external actions for sandbox/live mode policy.

Each action ROOT wants to take is categorized into one of six categories,
each with its own notification and approval policy. This is orthogonal to
the approval chain's risk levels — categories determine HOW to notify,
risk levels determine WHETHER to approve.

Categories:
- FINANCIAL: trades, transfers, purchases → CRITICAL notification + approval
- COMMUNICATION: emails, messages, posts → HIGH notification + approval
- DEPLOYMENT: code deploy, config change → HIGH notification + approval
- DATA_ACCESS: API calls, web scraping → LOW notification, auto-execute
- SYSTEM: health checks, status queries → no notification, auto-execute
- INTERNAL: learning, reflection, memory → never gated
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ActionCategory(str, Enum):
    FINANCIAL = "financial"
    COMMUNICATION = "communication"
    DEPLOYMENT = "deployment"
    DATA_ACCESS = "data_access"
    SYSTEM = "system"
    INTERNAL = "internal"


@dataclass(frozen=True)
class CategoryPolicy:
    """Defines how an action category behaves in LIVE mode."""

    category: ActionCategory
    requires_approval: bool
    notification_level: str  # "critical", "high", "medium", "low", "none"
    auto_execute_delay_seconds: int  # 0 = immediate, -1 = wait for approval


# ── Live Mode Policies ──────────────────────────────────────────

LIVE_MODE_POLICIES: dict[ActionCategory, CategoryPolicy] = {
    ActionCategory.FINANCIAL: CategoryPolicy(
        category=ActionCategory.FINANCIAL,
        requires_approval=True,
        notification_level="critical",
        auto_execute_delay_seconds=-1,  # Never auto-execute, wait for approval
    ),
    ActionCategory.COMMUNICATION: CategoryPolicy(
        category=ActionCategory.COMMUNICATION,
        requires_approval=True,
        notification_level="high",
        auto_execute_delay_seconds=-1,
    ),
    ActionCategory.DEPLOYMENT: CategoryPolicy(
        category=ActionCategory.DEPLOYMENT,
        requires_approval=True,
        notification_level="high",
        auto_execute_delay_seconds=-1,
    ),
    ActionCategory.DATA_ACCESS: CategoryPolicy(
        category=ActionCategory.DATA_ACCESS,
        requires_approval=False,
        notification_level="low",
        auto_execute_delay_seconds=0,
    ),
    ActionCategory.SYSTEM: CategoryPolicy(
        category=ActionCategory.SYSTEM,
        requires_approval=False,
        notification_level="none",
        auto_execute_delay_seconds=0,
    ),
    ActionCategory.INTERNAL: CategoryPolicy(
        category=ActionCategory.INTERNAL,
        requires_approval=False,
        notification_level="none",
        auto_execute_delay_seconds=0,
    ),
}


# ── Action → Category Mapping ──────────────────────────────────

_FINANCIAL_ACTIONS = frozenset({
    "execute_trade", "paper_trade", "live_trade", "transfer_funds",
    "withdraw", "purchase", "large_financial_decision",
    "polymarket_place_order", "polymarket_market_order",
    "polymarket_cancel_order", "polymarket_cancel_all",
    "alpaca_place_order", "alpaca_cancel_order",
})

_COMMUNICATION_ACTIONS = frozenset({
    "send_email", "send_message", "post_content", "notify_external",
    "publish", "share", "create_pr", "push_code",
})

_DEPLOYMENT_ACTIONS = frozenset({
    "deploy", "deploy_staging", "deploy_new_system", "merge_pr",
    "force_push", "run_migration", "modify_production_config",
    "install_package", "run_shell_command", "modify_config",
    "code_deploy", "self_rewrite", "major_rewrite",
    "architecture_change", "system_expansion",
})

_DATA_ACCESS_ACTIONS = frozenset({
    "market_scan", "fetch_prices", "fetch_news", "web_search",
    "api_call", "rss_fetch", "github_scan", "data_discovery",
})

_SYSTEM_ACTIONS = frozenset({
    "health_check", "status_query", "diagnostics",
})

_FINANCIAL_PREFIXES = ("execute_trade:", "polymarket_trade:", "plugin_invoke:alpaca_place",
                       "plugin_invoke:polymarket_place", "plugin_invoke:polymarket_market_order",
                       "plugin_invoke:polymarket_cancel", "plugin_invoke:alpaca_cancel")

_DATA_ACCESS_PREFIXES = ("market_scan:", "fetch:", "scan:", "plugin_invoke:polymarket_markets",
                         "plugin_invoke:polymarket_events", "plugin_invoke:polymarket_orderbook",
                         "plugin_invoke:polymarket_price", "plugin_invoke:polymarket_balance",
                         "plugin_invoke:polymarket_positions", "plugin_invoke:polymarket_open_orders",
                         "plugin_invoke:alpaca_account", "plugin_invoke:alpaca_positions",
                         "plugin_invoke:alpaca_market_data", "plugin_invoke:alpaca_order_history")


def classify_action_category(
    action: str,
    context: dict[str, Any] | None = None,
) -> ActionCategory:
    """Classify an action into a category for notification/approval policy.

    Checks exact matches first, then prefix matches, then context hints.
    Unknown actions default to DATA_ACCESS (safe default with LOW notification).
    """
    action_lower = action.lower().replace(" ", "_")
    ctx = context or {}

    # Exact match
    if action_lower in _FINANCIAL_ACTIONS:
        return ActionCategory.FINANCIAL
    if action_lower in _COMMUNICATION_ACTIONS:
        return ActionCategory.COMMUNICATION
    if action_lower in _DEPLOYMENT_ACTIONS:
        return ActionCategory.DEPLOYMENT
    if action_lower in _DATA_ACCESS_ACTIONS:
        return ActionCategory.DATA_ACCESS
    if action_lower in _SYSTEM_ACTIONS:
        return ActionCategory.SYSTEM

    # Prefix match (for composite actions like "execute_trade:AAPL")
    for prefix in _FINANCIAL_PREFIXES:
        if action_lower.startswith(prefix):
            return ActionCategory.FINANCIAL
    for prefix in _DATA_ACCESS_PREFIXES:
        if action_lower.startswith(prefix):
            return ActionCategory.DATA_ACCESS

    # Context-based hints
    if ctx.get("involves_money"):
        return ActionCategory.FINANCIAL
    if ctx.get("sends_notification") or ctx.get("sends_email"):
        return ActionCategory.COMMUNICATION
    if ctx.get("deploys") or ctx.get("modifies_code"):
        return ActionCategory.DEPLOYMENT

    # Default: DATA_ACCESS (safe — LOW notification, auto-execute)
    return ActionCategory.DATA_ACCESS


def get_policy(category: ActionCategory) -> CategoryPolicy:
    """Get the live-mode policy for an action category."""
    return LIVE_MODE_POLICIES[category]
