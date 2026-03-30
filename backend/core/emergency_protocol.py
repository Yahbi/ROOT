"""
Emergency Protocol — automatic system health monitoring and emergency response.

Continuously evaluates system metrics against safety thresholds:
- Error rate > 50%        → CRITICAL
- LLM failure rate > 80%  → CRITICAL
- Trading daily P&L < -3% → CRITICAL
- Memory corruption       → CRITICAL

On CRITICAL: pauses all autonomous actions and notifies Yohan immediately.
On WARNING:  logs the issue and notifies, continues with caution.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("root.emergency_protocol")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Enums & Data ──────────────────────────────────────────────


class Severity(str, Enum):
    OK = "ok"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(frozen=True)
class EmergencyStatus:
    """Immutable snapshot of a health check result."""

    severity: Severity
    issues: tuple[str, ...]
    affected_subsystems: tuple[str, ...]
    recommended_actions: tuple[str, ...]
    checked_at: str


# ── Default thresholds ────────────────────────────────────────

_THRESHOLDS = {
    "error_rate_critical": 0.50,
    "error_rate_warning": 0.30,
    "llm_failure_rate_critical": 0.80,
    "llm_failure_rate_warning": 0.50,
    "trading_daily_pnl_critical": -0.03,  # -3% of portfolio
    "trading_daily_pnl_warning": -0.01,   # -1% of portfolio
}


# ── Main class ────────────────────────────────────────────────


class EmergencyProtocol:
    """Automatic system health monitoring and emergency response.

    Evaluates metrics, classifies severity, pauses subsystems on
    critical issues, and notifies Yohan through the notification engine.
    """

    def __init__(
        self,
        notification_engine=None,
        state_store=None,
    ) -> None:
        self._notification_engine = notification_engine
        self._state_store = state_store
        self._paused: set[str] = set()
        self._lock = threading.Lock()
        self._check_count = 0
        self._critical_count = 0
        self._warning_count = 0
        self._last_status: Optional[EmergencyStatus] = None
        logger.info("EmergencyProtocol initialised")

    # ── Health check ──────────────────────────────────────────

    def check_health(self, metrics: dict[str, Any]) -> EmergencyStatus:
        """Evaluate system metrics and return an EmergencyStatus.

        Expected metrics keys (all optional — missing keys are skipped):
            error_rate:         float 0-1  (fraction of recent requests that errored)
            llm_failure_rate:   float 0-1  (fraction of LLM calls that failed)
            trading_daily_pnl:  float      (daily P&L as fraction of portfolio, e.g. -0.02)
            memory_corruption:  bool       (any corruption detected?)

        Returns:
            EmergencyStatus with severity, issues, affected subsystems,
            and recommended actions.
        """
        self._check_count += 1
        issues: list[str] = []
        affected: list[str] = []
        actions: list[str] = []
        severity = Severity.OK

        # ── Error rate ────────────────────────────────────────
        error_rate = metrics.get("error_rate")
        if error_rate is not None:
            if error_rate > _THRESHOLDS["error_rate_critical"]:
                severity = Severity.CRITICAL
                issues.append(f"Error rate critical: {error_rate:.1%}")
                affected.append("request_handling")
                actions.append("Pause autonomous actions and investigate error source")
            elif error_rate > _THRESHOLDS["error_rate_warning"]:
                severity = max(severity, Severity.WARNING, key=lambda s: list(Severity).index(s))
                issues.append(f"Error rate elevated: {error_rate:.1%}")
                affected.append("request_handling")
                actions.append("Monitor error rate closely; reduce autonomous action frequency")

        # ── LLM failure rate ──────────────────────────────────
        llm_failure_rate = metrics.get("llm_failure_rate")
        if llm_failure_rate is not None:
            if llm_failure_rate > _THRESHOLDS["llm_failure_rate_critical"]:
                severity = Severity.CRITICAL
                issues.append(f"LLM failure rate critical: {llm_failure_rate:.1%}")
                affected.append("llm_service")
                actions.append("Switch to offline brain fallback; notify Yohan")
            elif llm_failure_rate > _THRESHOLDS["llm_failure_rate_warning"]:
                severity = max(severity, Severity.WARNING, key=lambda s: list(Severity).index(s))
                issues.append(f"LLM failure rate elevated: {llm_failure_rate:.1%}")
                affected.append("llm_service")
                actions.append("Enable offline brain fallback for non-critical tasks")

        # ── Trading daily P&L ─────────────────────────────────
        trading_pnl = metrics.get("trading_daily_pnl")
        if trading_pnl is not None:
            if trading_pnl < _THRESHOLDS["trading_daily_pnl_critical"]:
                severity = Severity.CRITICAL
                issues.append(f"Trading daily P&L critical: {trading_pnl:.2%}")
                affected.append("trading")
                actions.append("Halt all autonomous trading; notify Yohan immediately")
            elif trading_pnl < _THRESHOLDS["trading_daily_pnl_warning"]:
                severity = max(severity, Severity.WARNING, key=lambda s: list(Severity).index(s))
                issues.append(f"Trading daily P&L declining: {trading_pnl:.2%}")
                affected.append("trading")
                actions.append("Reduce trade frequency; tighten stop-losses")

        # ── Memory corruption ─────────────────────────────────
        memory_corruption = metrics.get("memory_corruption")
        if memory_corruption:
            severity = Severity.CRITICAL
            issues.append("Memory corruption detected")
            affected.append("memory_engine")
            actions.append("Pause memory writes; run integrity check; notify Yohan")

        status = EmergencyStatus(
            severity=severity,
            issues=tuple(issues),
            affected_subsystems=tuple(affected),
            recommended_actions=tuple(actions),
            checked_at=_now_iso(),
        )

        if severity == Severity.CRITICAL:
            self._critical_count += 1
            logger.critical("EMERGENCY: %s", "; ".join(issues))
        elif severity == Severity.WARNING:
            self._warning_count += 1
            logger.warning("Health warning: %s", "; ".join(issues))
        else:
            logger.debug("Health check OK")

        self._last_status = status
        return status

    # ── Emergency response ────────────────────────────────────

    async def respond(self, status: EmergencyStatus) -> None:
        """Execute the appropriate response for a given EmergencyStatus.

        - CRITICAL: Pause all autonomous actions, notify Yohan.
        - WARNING: Log and notify, continue with reduced frequency.
        - OK: Normal operation (no action needed).
        """
        if status.severity == Severity.OK:
            return

        if status.severity == Severity.CRITICAL:
            # Pause all affected subsystems.
            for subsystem in status.affected_subsystems:
                self.pause_subsystem(subsystem)

            # Also pause general autonomous execution.
            self.pause_subsystem("autonomous_loop")
            self.pause_subsystem("proactive_engine")
            self.pause_subsystem("directive_engine")

            logger.critical(
                "CRITICAL response: paused %d subsystems, notifying Yohan",
                len(self._paused),
            )

            # Notify Yohan.
            if self._notification_engine is not None:
                try:
                    await self._notification_engine.send(
                        title="EMERGENCY — ROOT Critical Alert",
                        body=(
                            f"Issues: {'; '.join(status.issues)}\n"
                            f"Affected: {', '.join(status.affected_subsystems)}\n"
                            f"Actions: {'; '.join(status.recommended_actions)}\n"
                            f"Paused subsystems: {', '.join(sorted(self._paused))}"
                        ),
                        level="critical",
                        source="emergency_protocol",
                    )
                except Exception as exc:
                    logger.error("Failed to send critical notification: %s", exc)

        elif status.severity == Severity.WARNING:
            logger.warning(
                "WARNING response: %s — continuing with caution",
                "; ".join(status.issues),
            )

            if self._notification_engine is not None:
                try:
                    await self._notification_engine.send(
                        title="ROOT Health Warning",
                        body=(
                            f"Issues: {'; '.join(status.issues)}\n"
                            f"Recommended: {'; '.join(status.recommended_actions)}"
                        ),
                        level="high",
                        source="emergency_protocol",
                    )
                except Exception as exc:
                    logger.error("Failed to send warning notification: %s", exc)

    # ── Subsystem pause / resume ──────────────────────────────

    def pause_subsystem(self, name: str) -> None:
        """Pause a subsystem by name."""
        with self._lock:
            self._paused.add(name)
        logger.warning("Paused subsystem: %s", name)

    def resume_subsystem(self, name: str) -> None:
        """Resume a previously paused subsystem."""
        with self._lock:
            self._paused.discard(name)
        logger.info("Resumed subsystem: %s", name)

    def get_paused(self) -> set[str]:
        """Return the set of currently paused subsystem names."""
        with self._lock:
            return set(self._paused)

    # ── Stats ─────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return runtime statistics."""
        with self._lock:
            paused_snapshot = set(self._paused)
        return {
            "total_checks": self._check_count,
            "critical_count": self._critical_count,
            "warning_count": self._warning_count,
            "paused_subsystems": sorted(paused_snapshot),
            "paused_count": len(paused_snapshot),
            "last_severity": self._last_status.severity.value if self._last_status else None,
            "has_notification_engine": self._notification_engine is not None,
            "has_state_store": self._state_store is not None,
        }
