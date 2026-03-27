"""
Approval Chain — Risk-based task approval system.

From YOHAN-Command-Center pattern:
- LOW risk: auto-approved (search, analyze, recall, score)
- MEDIUM risk: notify Yohan + proceed (draft emails, create tasks, research)
- HIGH risk: Yohan must approve before execution (send messages, post content)
- CRITICAL risk: Yohan approves + confirms (execute trades, transfer money, delete data)

Agents tag their actions with risk levels. The chain decides whether to
auto-approve, queue for approval, or block until confirmed.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("root.approval")


class RiskLevel(str, Enum):
    LOW = "low"          # Auto-approved
    MEDIUM = "medium"    # Notify + proceed
    HIGH = "high"        # Must approve
    CRITICAL = "critical"  # Must approve + confirm


class ApprovalStatus(str, Enum):
    AUTO_APPROVED = "auto_approved"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ApprovalRequest:
    """Immutable approval request."""
    id: str
    agent_id: str
    action: str
    description: str
    risk_level: RiskLevel
    status: ApprovalStatus = ApprovalStatus.PENDING
    context: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    resolved_at: Optional[str] = None
    resolver: Optional[str] = None  # "auto", "yohan", "timeout"
    # Doctrine-required fields: reason, benefit, risk analysis
    reason: Optional[str] = None
    benefit: Optional[str] = None
    risk_analysis: Optional[str] = None


# ── Risk classification rules ────────────────────────────────────

_LOW_ACTIONS = frozenset({
    # Research, analysis, learning — agents do freely
    "search", "analyze", "recall", "score", "summarize", "read",
    "health_check", "status", "report", "list", "calculate",
    "forecast", "review", "gap_analysis", "quality_scoring",
    "brainstorm", "plan", "draft", "research", "web_search",
    "memory_recall", "reflect",
    # Skill building & learning — agents evolve freely
    "create_skill", "update_knowledge", "learn", "evolve",
    "propose_improvement", "self_improve", "build_skill",
    "store_knowledge", "memory_store", "run_experiment",
    "discover_sources", "auto_update_catalog",
    # Predictions & simulations
    "predict", "simulate", "market_scan", "github_scan",
    # Content & task creation — autonomous (moved from MEDIUM)
    "create_task", "write_document", "generate_code",
    "create_report", "schedule_task", "note", "bookmark",
    "draft_email", "code_proposal",
    # Autonomous operations — ROOT acts freely
    "optimize", "refactor", "backtest", "compare", "evaluate",
    "classify", "tag", "categorize", "extract", "transform",
    "aggregate", "correlate", "benchmark", "profile",
    "goal_decompose", "task_execute", "chain_trigger",
    "directive_execute", "proactive_action",
    # Code editing & self-improvement — ROOT edits freely
    "self_rewrite", "code_edit", "code_improve", "modify_workflow",
    "update_config", "install_plugin", "enable_feature", "disable_feature",
})

_MEDIUM_ACTIONS = frozenset({
    # Actions with external side effects — notify but proceed
    "deploy_staging", "run_migration", "modify_production_config",
})

_HIGH_ACTIONS = frozenset({
    "send_email", "send_message", "post_content", "push_code",
    "create_pr", "publish", "notify_external", "share",
    "modify_config", "install_package", "run_shell_command",
    "deploy", "merge_pr",
})

_CRITICAL_ACTIONS = frozenset({
    "execute_trade", "transfer_funds", "delete_data", "drop_table",
    "reset_system", "modify_permissions", "revoke_access",
    "force_push", "delete_repository", "shutdown",
    "live_trade", "withdraw", "paper_trade",
    # Doctrine: major changes require Yohan approval
    "architecture_change", "system_expansion", "major_rewrite",
    "large_financial_decision", "deploy_new_system",
})


def classify_risk(action: str, context: Optional[dict] = None) -> RiskLevel:
    """Classify the risk level of an action."""
    action_lower = action.lower().replace(" ", "_")

    # Check explicit lists
    if action_lower in _CRITICAL_ACTIONS:
        return RiskLevel.CRITICAL
    if action_lower in _HIGH_ACTIONS:
        return RiskLevel.HIGH
    if action_lower in _MEDIUM_ACTIONS:
        return RiskLevel.MEDIUM
    if action_lower in _LOW_ACTIONS:
        return RiskLevel.LOW

    # Context-based escalation
    if context:
        if context.get("involves_money"):
            return RiskLevel.CRITICAL
        if context.get("external_communication"):
            return RiskLevel.HIGH
        if context.get("modifies_state"):
            return RiskLevel.MEDIUM

    # Default: medium (safe default — notify but proceed)
    return RiskLevel.MEDIUM


class ApprovalChain:
    """Manages approval requests with risk-based routing."""

    EXPIRY_SECONDS = 3600  # Pending requests expire after 1 hour

    def __init__(self, bus=None, escalation=None) -> None:
        self._requests: dict[str, ApprovalRequest] = {}
        self._history: deque[ApprovalRequest] = deque(maxlen=500)
        self._bus = bus  # MessageBus for notifications
        self._escalation = escalation  # EscalationEngine for confidence gating

    async def request_approval(
        self,
        agent_id: str,
        action: str,
        description: str,
        context: Optional[dict] = None,
        risk_override: Optional[RiskLevel] = None,
        reason: Optional[str] = None,
        benefit: Optional[str] = None,
        risk_analysis: Optional[str] = None,
    ) -> ApprovalRequest:
        """Submit an action for approval. Returns immediately for LOW/MEDIUM.
        Blocks for HIGH/CRITICAL until approved or rejected.

        For HIGH/CRITICAL actions, reason+benefit+risk_analysis should be
        provided per the ASTRA-ROOT governance doctrine.
        """

        risk = risk_override or classify_risk(action, context)
        req_id = f"apr_{uuid.uuid4().hex[:12]}"

        request = ApprovalRequest(
            id=req_id,
            agent_id=agent_id,
            action=action,
            description=description,
            risk_level=risk,
            context=context or {},
            reason=reason,
            benefit=benefit,
            risk_analysis=risk_analysis,
        )

        if risk == RiskLevel.LOW:
            # Auto-approve
            approved = ApprovalRequest(
                id=request.id,
                agent_id=request.agent_id,
                action=request.action,
                description=request.description,
                risk_level=request.risk_level,
                status=ApprovalStatus.AUTO_APPROVED,
                context=request.context,
                created_at=request.created_at,
                resolved_at=datetime.now(timezone.utc).isoformat(),
                resolver="auto",
            )
            self._history.append(approved)
            logger.debug("Auto-approved: %s (%s)", action, agent_id)
            return approved

        # Escalation gate: check confidence before auto-approving MEDIUM risk
        if risk == RiskLevel.MEDIUM and self._escalation:
            esc_decision = self._escalation.should_auto_execute(
                action, risk_level=risk.value,
            )
            if not esc_decision.should_auto_execute:
                logger.info(
                    "Escalation bumped %s to HIGH: %s", action, esc_decision.reason,
                )
                risk = RiskLevel.HIGH
                request = ApprovalRequest(
                    id=request.id, agent_id=request.agent_id,
                    action=request.action, description=request.description,
                    risk_level=RiskLevel.HIGH, context=request.context,
                    created_at=request.created_at,
                )

        if risk == RiskLevel.MEDIUM:
            # Notify + auto-approve
            approved = ApprovalRequest(
                id=request.id,
                agent_id=request.agent_id,
                action=request.action,
                description=request.description,
                risk_level=request.risk_level,
                status=ApprovalStatus.AUTO_APPROVED,
                context=request.context,
                created_at=request.created_at,
                resolved_at=datetime.now(timezone.utc).isoformat(),
                resolver="auto_notify",
            )
            self._history.append(approved)

            # Notify via bus
            if self._bus:
                msg = self._bus.create_message(
                    topic="system.approval",
                    sender="approval_chain",
                    payload={
                        "type": "notification",
                        "request_id": req_id,
                        "agent": agent_id,
                        "action": action,
                        "description": description,
                        "risk": risk.value,
                    },
                )
                await self._bus.publish(msg)

            logger.info("Medium-risk auto-approved (notified): %s (%s)", action, agent_id)
            return approved

        # HIGH / CRITICAL — queue for manual approval
        self._requests[req_id] = request
        logger.info("Queued for approval [%s]: %s — %s (%s)", risk.value, action, description, agent_id)

        # Notify via bus
        if self._bus:
            msg = self._bus.create_message(
                topic="system.approval",
                sender="approval_chain",
                payload={
                    "type": "approval_required",
                    "request_id": req_id,
                    "agent": agent_id,
                    "action": action,
                    "description": description,
                    "risk": risk.value,
                },
            )
            await self._bus.publish(msg)

        return request

    def approve(self, request_id: str, resolver: str = "yohan") -> Optional[ApprovalRequest]:
        """Approve a pending request."""
        request = self._requests.pop(request_id, None)
        if not request:
            return None

        approved = ApprovalRequest(
            id=request.id,
            agent_id=request.agent_id,
            action=request.action,
            description=request.description,
            risk_level=request.risk_level,
            status=ApprovalStatus.APPROVED,
            context=request.context,
            created_at=request.created_at,
            resolved_at=datetime.now(timezone.utc).isoformat(),
            resolver=resolver,
        )
        self._history.append(approved)
        logger.info("Approved: %s (%s) by %s", request.action, request.agent_id, resolver)
        return approved

    def reject(self, request_id: str, resolver: str = "yohan") -> Optional[ApprovalRequest]:
        """Reject a pending request."""
        request = self._requests.pop(request_id, None)
        if not request:
            return None

        rejected = ApprovalRequest(
            id=request.id,
            agent_id=request.agent_id,
            action=request.action,
            description=request.description,
            risk_level=request.risk_level,
            status=ApprovalStatus.REJECTED,
            context=request.context,
            created_at=request.created_at,
            resolved_at=datetime.now(timezone.utc).isoformat(),
            resolver=resolver,
        )
        self._history.append(rejected)
        logger.info("Rejected: %s (%s) by %s", request.action, request.agent_id, resolver)
        return rejected

    def get_pending(self) -> list[ApprovalRequest]:
        """Get all pending approval requests."""
        return list(self._requests.values())

    def get_history(self, limit: int = 50) -> list[ApprovalRequest]:
        """Get recent approval history."""
        items = list(self._history)
        return list(reversed(items[-limit:]))

    def expire_stale(self, timeout_minutes: int = 60) -> list[ApprovalRequest]:
        """Auto-resolve stale pending approvals.

        HIGH risk: auto-approve after timeout (was likely bumped from MEDIUM).
        CRITICAL risk: never auto-approve, but mark as expired.
        Returns list of resolved requests.
        """
        now = datetime.now(timezone.utc)
        resolved: list[ApprovalRequest] = []
        stale_ids: list[str] = []

        for req_id, req in self._requests.items():
            try:
                created = datetime.fromisoformat(req.created_at)
                age_minutes = (now - created).total_seconds() / 60
            except (ValueError, TypeError):
                continue

            if age_minutes < timeout_minutes:
                continue

            if req.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                # Never auto-approve HIGH or CRITICAL — expire them
                expired = ApprovalRequest(
                    id=req.id, agent_id=req.agent_id,
                    action=req.action, description=req.description,
                    risk_level=req.risk_level,
                    status=ApprovalStatus.EXPIRED,
                    context=req.context, created_at=req.created_at,
                    resolved_at=now.isoformat(),
                    resolver="timeout_expired",
                )
                self._history.append(expired)
                resolved.append(expired)
                stale_ids.append(req_id)
                logger.warning(
                    "%s approval expired (NOT auto-approved): %s (%s) after %.0f min",
                    req.risk_level.value.upper(), req.action, req.agent_id, age_minutes,
                )

        for req_id in stale_ids:
            self._requests.pop(req_id, None)

        return resolved

    def stats(self) -> dict[str, Any]:
        """Approval chain statistics."""
        history = self._history
        return {
            "pending": len(self._requests),
            "total_processed": len(history),
            "auto_approved": sum(1 for r in history if r.status == ApprovalStatus.AUTO_APPROVED),
            "manually_approved": sum(1 for r in history if r.status == ApprovalStatus.APPROVED),
            "rejected": sum(1 for r in history if r.status == ApprovalStatus.REJECTED),
            "expired": sum(1 for r in history if r.status == ApprovalStatus.EXPIRED),
            "by_risk": {
                "low": sum(1 for r in history if r.risk_level == RiskLevel.LOW),
                "medium": sum(1 for r in history if r.risk_level == RiskLevel.MEDIUM),
                "high": sum(1 for r in history if r.risk_level == RiskLevel.HIGH),
                "critical": sum(1 for r in history if r.risk_level == RiskLevel.CRITICAL),
            },
        }
