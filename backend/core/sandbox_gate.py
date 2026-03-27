"""
Sandbox Gate — Sandbox/Live mode system for ROOT.

Modes:
- SANDBOX (default): ROOT operates but CANNOT directly impact external systems.
  All external actions are simulated and logged. Owner gets notifications.
- LIVE: ROOT has FULL autonomous access — trading, finances, deployments.
  Owner still gets notifications for every decision.

Each subsystem can be independently toggled between sandbox and live mode,
with a global default that applies when no override is set.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from backend.core.action_categories import (
    ActionCategory,
    classify_action_category,
    get_policy,
)

logger = logging.getLogger("root.sandbox_gate")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Enums ──────────────────────────────────────────────────────


class SystemMode(str, Enum):
    SANDBOX = "sandbox"
    LIVE = "live"


class SystemId(str, Enum):
    TRADING = "trading"
    NOTIFICATIONS = "notifications"
    CODE_DEPLOY = "code_deploy"
    REVENUE = "revenue"
    AGENTS_EXTERNAL = "agents_external"
    PROACTIVE = "proactive"
    PLUGINS = "plugins"
    FILE_SYSTEM = "file_system"


# ── Frozen Models ──────────────────────────────────────────────


class SandboxConfig(BaseModel):
    """Immutable sandbox configuration."""

    model_config = {"frozen": True}

    global_mode: SystemMode = SystemMode.SANDBOX
    system_overrides: dict[str, SystemMode] = Field(default_factory=dict)
    updated_at: str = Field(default_factory=_now_iso)
    updated_by: str = "system"


class GateDecision(BaseModel):
    """Immutable record of a sandbox gate check."""

    model_config = {"frozen": True}

    id: str = Field(default_factory=lambda: f"gd_{uuid.uuid4().hex[:12]}")
    system_id: str
    action: str
    mode: SystemMode
    was_executed: bool
    agent_id: str = ""
    description: str = ""
    context: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "low"
    action_category: str = "internal"  # ActionCategory value
    requires_approval: bool = False
    created_at: str = Field(default_factory=_now_iso)


# ── Gate Class ─────────────────────────────────────────────────


_CONFIG_TABLE = "sandbox_config"
_DECISION_TABLE = "sandbox_decisions"
_CONFIG_KEY = "current_config"


class SandboxGate:
    """Controls whether ROOT's subsystems operate in sandbox or live mode.

    In sandbox mode, external actions are intercepted and logged as simulated.
    In live mode, actions execute fully with notifications to the owner.
    """

    def __init__(
        self,
        state_store,
        notification_engine=None,
    ) -> None:
        self._state_store = state_store
        self._notification_engine = notification_engine
        self._config: SandboxConfig = SandboxConfig()

        self._ensure_tables()
        self._config = self._load_config()

        logger.info(
            "SandboxGate initialized: global=%s, overrides=%d",
            self._config.global_mode.value,
            len(self._config.system_overrides),
        )

    # ── Table Setup ────────────────────────────────────────────

    def _ensure_tables(self) -> None:
        """Create sandbox tables if they don't exist."""
        self._state_store.conn.executescript(f"""
            CREATE TABLE IF NOT EXISTS {_CONFIG_TABLE} (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS {_DECISION_TABLE} (
                id TEXT PRIMARY KEY,
                system_id TEXT NOT NULL,
                action TEXT NOT NULL,
                mode TEXT NOT NULL,
                was_executed INTEGER NOT NULL DEFAULT 0,
                agent_id TEXT DEFAULT '',
                description TEXT DEFAULT '',
                context TEXT DEFAULT '{{}}',
                risk_level TEXT DEFAULT 'low',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_sd_system
                ON {_DECISION_TABLE}(system_id);
            CREATE INDEX IF NOT EXISTS idx_sd_mode
                ON {_DECISION_TABLE}(mode);
            CREATE INDEX IF NOT EXISTS idx_sd_created
                ON {_DECISION_TABLE}(created_at);
        """)

    # ── Config Persistence ─────────────────────────────────────

    def _load_config(self) -> SandboxConfig:
        """Load config from DB or return defaults."""
        row = self._state_store.conn.execute(
            f"SELECT value FROM {_CONFIG_TABLE} WHERE key = ?",
            (_CONFIG_KEY,),
        ).fetchone()
        if not row:
            return SandboxConfig()
        try:
            data = json.loads(row["value"])
            return SandboxConfig(**data)
        except Exception as exc:
            logger.warning("Failed to parse sandbox config: %s", exc)
            return SandboxConfig()

    def _save_config(self, config: SandboxConfig) -> None:
        """Persist config to DB (immutable — replaces the stored value)."""
        self._state_store.conn.execute(
            f"""INSERT INTO {_CONFIG_TABLE} (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
            (_CONFIG_KEY, config.model_dump_json()),
        )
        self._state_store.conn.commit()

    # ── Mode Queries ───────────────────────────────────────────

    def get_effective_mode(self, system_id: str) -> SystemMode:
        """Get the effective mode for a subsystem.

        Checks system-specific override first, then falls back to global mode.
        """
        override = self._config.system_overrides.get(system_id)
        if override is not None:
            return override
        return self._config.global_mode

    @property
    def global_mode(self) -> SystemMode:
        return self._config.global_mode

    # ── Gate Check ─────────────────────────────────────────────

    def check(
        self,
        system_id: str,
        action: str,
        description: str = "",
        context: Optional[dict[str, Any]] = None,
        agent_id: str = "",
        risk_level: str = "low",
    ) -> GateDecision:
        """Check whether an action should be executed or sandboxed.

        Returns a GateDecision with was_executed=True only if mode is LIVE.
        Logs every decision to the database.
        Sends a notification for live-mode actions.
        """
        effective_mode = self.get_effective_mode(system_id)
        category = classify_action_category(action, context)
        policy = get_policy(category)

        # In LIVE mode, INTERNAL/SYSTEM/DATA_ACCESS execute freely.
        # FINANCIAL/COMMUNICATION/DEPLOYMENT still execute but flag requires_approval
        # (the caller should then route through ApprovalChain).
        was_executed = effective_mode == SystemMode.LIVE
        needs_approval = was_executed and policy.requires_approval

        decision = GateDecision(
            system_id=system_id,
            action=action,
            mode=effective_mode,
            was_executed=was_executed,
            agent_id=agent_id,
            description=description,
            context=context or {},
            risk_level=risk_level,
            action_category=category.value,
            requires_approval=needs_approval,
        )

        self._log_decision(decision)

        if was_executed and self._notification_engine:
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._notify_live_action(decision))
                else:
                    loop.run_until_complete(self._notify_live_action(decision))
            except RuntimeError:
                logger.debug("No event loop for live notification: %s", action)

        if not was_executed:
            logger.info(
                "SANDBOX blocked: [%s] %s — %s (agent=%s)",
                system_id, action, description[:80], agent_id,
            )
            # Notify owner about ROOT's intent (so they can see what ROOT tried to do)
            if self._notification_engine and risk_level in ("high", "critical"):
                try:
                    import asyncio

                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        loop.create_task(self._notify_sandbox_intent(decision))
                except RuntimeError:
                    logger.debug("No event loop for sandbox intent notification: %s", action)

        return decision

    async def _notify_sandbox_intent(self, decision: GateDecision) -> None:
        """Notify owner about a blocked action so they can see ROOT's intent."""
        if not self._notification_engine:
            return
        await self._notification_engine.send(
            title=f"Sandbox Blocked: {decision.action}",
            body=(
                f"ROOT intended to: {decision.description[:200]}\n"
                f"System: {decision.system_id} | Agent: {decision.agent_id or 'system'}\n"
                f"Risk: {decision.risk_level}\n"
                f"Action was NOT executed (sandbox mode)"
            ),
            level="medium",
            source="sandbox_gate",  # Bypasses notification sandbox gate (prevents deadlock)
        )

    async def _notify_live_action(self, decision: GateDecision) -> None:
        """Send notification about a live-mode action."""
        if not self._notification_engine:
            return
        level = "critical" if decision.risk_level in ("high", "critical") else "high"
        await self._notification_engine.send(
            title=f"LIVE Action: {decision.action}",
            body=(
                f"System: {decision.system_id}\n"
                f"Agent: {decision.agent_id or 'system'}\n"
                f"Description: {decision.description[:200]}\n"
                f"Risk: {decision.risk_level}"
            ),
            level=level,
            source="sandbox_gate",
        )

    # ── Mode Setters ───────────────────────────────────────────

    def set_global_mode(self, mode: SystemMode) -> SandboxConfig:
        """Set the global operating mode. Returns the new config."""
        new_config = self._config.model_copy(
            update={
                "global_mode": mode,
                "updated_at": _now_iso(),
                "updated_by": "owner",
            },
        )
        self._config = new_config
        self._save_config(new_config)

        if mode == SystemMode.LIVE and self._notification_engine:
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._notification_engine.send(
                        title="CRITICAL: ROOT switched to LIVE mode",
                        body="Global mode is now LIVE. All subsystems without overrides will execute real actions.",
                        level="critical",
                        source="sandbox_gate",
                    ))
            except RuntimeError:
                pass

        logger.info("Global mode set to %s", mode.value)
        return new_config

    def set_system_mode(self, system_id: str, mode: SystemMode) -> SandboxConfig:
        """Set the mode for a specific subsystem. Returns the new config."""
        new_overrides = {**self._config.system_overrides, system_id: mode}
        new_config = self._config.model_copy(
            update={
                "system_overrides": new_overrides,
                "updated_at": _now_iso(),
                "updated_by": "owner",
            },
        )
        self._config = new_config
        self._save_config(new_config)

        if mode == SystemMode.LIVE and self._notification_engine:
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(self._notification_engine.send(
                        title=f"CRITICAL: {system_id} switched to LIVE mode",
                        body=f"Subsystem '{system_id}' is now LIVE. Real actions will be executed.",
                        level="critical",
                        source="sandbox_gate",
                    ))
            except RuntimeError:
                pass

        logger.info("System '%s' mode set to %s", system_id, mode.value)
        return new_config

    # ── Decision Logging ───────────────────────────────────────

    def _log_decision(self, decision: GateDecision) -> None:
        """Persist a gate decision to the database."""
        try:
            self._state_store.conn.execute(
                f"""INSERT INTO {_DECISION_TABLE}
                    (id, system_id, action, mode, was_executed, agent_id,
                     description, context, risk_level, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    decision.id,
                    decision.system_id,
                    decision.action,
                    decision.mode.value,
                    1 if decision.was_executed else 0,
                    decision.agent_id,
                    decision.description[:500],
                    json.dumps(decision.context),
                    decision.risk_level,
                    decision.created_at,
                ),
            )
            self._state_store.conn.commit()
        except Exception as exc:
            logger.error("Failed to log gate decision: %s", exc)

    # ── Queries ────────────────────────────────────────────────

    def get_decisions(
        self,
        system_id: Optional[str] = None,
        mode: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get recent gate decisions with optional filters."""
        conditions: list[str] = []
        params: list[Any] = []

        if system_id:
            conditions.append("system_id = ?")
            params.append(system_id)
        if mode:
            conditions.append("mode = ?")
            params.append(mode)

        where = " AND ".join(conditions) if conditions else "1=1"
        params.append(limit)

        rows = self._state_store.conn.execute(
            f"SELECT * FROM {_DECISION_TABLE} WHERE {where} ORDER BY created_at DESC LIMIT ?",
            params,
        ).fetchall()

        return [
            {
                "id": r["id"],
                "system_id": r["system_id"],
                "action": r["action"],
                "mode": r["mode"],
                "was_executed": bool(r["was_executed"]),
                "agent_id": r["agent_id"],
                "description": r["description"],
                "context": json.loads(r["context"] or "{}"),
                "risk_level": r["risk_level"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def get_decision_stats(self) -> dict[str, Any]:
        """Get aggregate statistics about gate decisions."""
        total = self._state_store.conn.execute(
            f"SELECT COUNT(*) as c FROM {_DECISION_TABLE}"
        ).fetchone()
        sandboxed = self._state_store.conn.execute(
            f"SELECT COUNT(*) as c FROM {_DECISION_TABLE} WHERE was_executed = 0"
        ).fetchone()
        live = self._state_store.conn.execute(
            f"SELECT COUNT(*) as c FROM {_DECISION_TABLE} WHERE was_executed = 1"
        ).fetchone()
        by_system = self._state_store.conn.execute(
            f"""SELECT system_id, mode, COUNT(*) as cnt
                FROM {_DECISION_TABLE}
                GROUP BY system_id, mode
                ORDER BY cnt DESC"""
        ).fetchall()

        system_breakdown: dict[str, dict[str, int]] = {}
        for row in by_system:
            sid = row["system_id"]
            if sid not in system_breakdown:
                system_breakdown[sid] = {"sandbox": 0, "live": 0}
            system_breakdown[sid][row["mode"]] = row["cnt"]

        return {
            "total_decisions": total["c"] if total else 0,
            "sandboxed": sandboxed["c"] if sandboxed else 0,
            "live_executed": live["c"] if live else 0,
            "by_system": system_breakdown,
        }

    def get_status(self) -> dict[str, Any]:
        """Full sandbox status: all system modes + stats."""
        all_systems: dict[str, str] = {}
        for sid in SystemId:
            all_systems[sid.value] = self.get_effective_mode(sid.value).value

        stats = self.get_decision_stats()

        return {
            "global_mode": self._config.global_mode.value,
            "system_modes": all_systems,
            "system_overrides": {
                k: v.value for k, v in self._config.system_overrides.items()
            },
            "updated_at": self._config.updated_at,
            "updated_by": self._config.updated_by,
            "stats": stats,
        }
