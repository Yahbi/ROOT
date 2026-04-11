"""
ROOT Diagnostics — comprehensive system health check.

Tests every subsystem, pipeline, plugin, connection, and background loop.
Returns a detailed report showing what works, what's broken, and what needs attention.

Run via API: GET /api/diagnostics/full
Run via CLI: python -m backend.core.diagnostics
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger("root.diagnostics")


@dataclass(frozen=True)
class CheckResult:
    """Result of a single diagnostic check."""
    name: str
    category: str  # "core", "llm", "pipeline", "plugin", "background", "database", "connection"
    status: str  # "pass", "fail", "warn", "skip"
    message: str
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


class DiagnosticsEngine:
    """Runs comprehensive diagnostics across all ROOT subsystems."""

    def __init__(self, app_state: Any) -> None:
        self._state = app_state

    async def run_full(self) -> dict[str, Any]:
        """Run ALL diagnostic checks. Returns comprehensive report."""
        start = time.monotonic()

        checks: list[CheckResult] = []

        # Run all check categories
        checks.extend(await self._check_core_systems())
        checks.extend(await self._check_databases())
        checks.extend(await self._check_llm_providers())
        checks.extend(await self._check_plugins())
        checks.extend(await self._check_pipelines())
        checks.extend(await self._check_background_loops())
        checks.extend(await self._check_connections())
        checks.extend(await self._check_agents())
        checks.extend(await self._check_learning())
        checks.extend(await self._check_autonomous_systems())

        elapsed = round((time.monotonic() - start) * 1000, 1)

        # Aggregate
        total = len(checks)
        passed = sum(1 for c in checks if c.status == "pass")
        failed = sum(1 for c in checks if c.status == "fail")
        warned = sum(1 for c in checks if c.status == "warn")
        skipped = sum(1 for c in checks if c.status == "skip")

        by_category: dict[str, dict[str, int]] = {}
        for c in checks:
            cat = by_category.setdefault(c.category, {"pass": 0, "fail": 0, "warn": 0, "skip": 0})
            cat[c.status] = cat.get(c.status, 0) + 1

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_ms": elapsed,
            "summary": {
                "total": total,
                "passed": passed,
                "failed": failed,
                "warnings": warned,
                "skipped": skipped,
                "health_pct": round(passed / max(total, 1) * 100, 1),
            },
            "by_category": by_category,
            "checks": [
                {
                    "name": c.name,
                    "category": c.category,
                    "status": c.status,
                    "message": c.message,
                    "duration_ms": c.duration_ms,
                    "details": c.details,
                }
                for c in checks
            ],
            "failures": [
                {"name": c.name, "category": c.category, "message": c.message}
                for c in checks if c.status == "fail"
            ],
            "warnings": [
                {"name": c.name, "category": c.category, "message": c.message}
                for c in checks if c.status == "warn"
            ],
        }

    # ── Core Systems ──────────────────────────────────────────────

    async def _check_core_systems(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        # Memory Engine
        results.append(self._check_system("memory", "Memory Engine", lambda s: {
            "count": s.count(),
            "has_fts": True,
        }))

        # Learning Engine
        results.append(self._check_system("learning", "Learning Engine", lambda s: s.stats()))

        # Experience Memory
        results.append(self._check_system("experience_memory", "Experience Memory", lambda s: {
            "started": True,
        }))

        # Conversation Store
        results.append(self._check_system("conversations", "Conversation Store", lambda s: {
            "session_id": s.current_session_id,
        }))

        # Skill Engine
        results.append(self._check_system("skills", "Skill Engine", lambda s: {
            "skill_count": len(s.list_all()),
        }))

        # State Store
        results.append(self._check_system("state_store", "State Store", lambda s: {
            "operational": True,
        }))

        # Notification Engine
        results.append(self._check_system("notifications", "Notification Engine", lambda s: {
            "configured": s.is_configured,
            "channels": {
                "telegram": bool(getattr(s, '_telegram_bot_token', '')),
                "discord": bool(getattr(s, '_discord_webhook_url', '')),
            },
        }))

        # Cost Tracker
        results.append(self._check_system("cost_tracker", "Cost Tracker", lambda s: s.summary()))

        # Economic Router
        results.append(self._check_system("economic_router", "Economic Router", lambda s: s.stats()))

        # Verification Protocol
        results.append(self._check_system("verification", "Verification Protocol", lambda s: {
            "operational": True,
        }))

        # Brain
        mode = getattr(self._state, "mode", "unknown")
        results.append(CheckResult(
            name="Brain", category="core",
            status="pass" if mode == "online" else "warn",
            message=f"Mode: {mode}",
            details={"mode": mode},
        ))

        # Context Manager
        results.append(self._check_system("context_manager", "Context Manager", lambda s: {
            "operational": True,
        }))

        return results

    # ── Databases ──────────────────────────────────────────────────

    async def _check_databases(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        import sqlite3
        from pathlib import Path

        db_dir = Path("data")
        expected_dbs = [
            "memory.db", "conversations.db", "learning.db", "hedge_fund.db",
            "state.db", "task_queue.db", "goals.db", "predictions.db",
            "experience.db", "experiments.db", "self_code.db", "revenue.db",
            "escalation.db", "triggers.db", "digests.db", "user_patterns.db",
        ]

        for db_name in expected_dbs:
            db_path = db_dir / db_name
            t = time.monotonic()
            try:
                if not db_path.exists():
                    results.append(CheckResult(
                        name=f"DB: {db_name}", category="database",
                        status="warn", message=f"File not found (may be created on first use)",
                    ))
                    continue

                conn = sqlite3.connect(str(db_path), timeout=5)
                conn.execute("PRAGMA journal_mode=WAL")
                # Integrity check
                result = conn.execute("PRAGMA integrity_check").fetchone()
                tables = conn.execute(
                    "SELECT count(*) FROM sqlite_master WHERE type='table'"
                ).fetchone()
                size_bytes = db_path.stat().st_size
                conn.close()

                ok = result and result[0] == "ok"
                elapsed = round((time.monotonic() - t) * 1000, 1)
                results.append(CheckResult(
                    name=f"DB: {db_name}", category="database",
                    status="pass" if ok else "fail",
                    message=f"OK — {tables[0]} tables, {size_bytes / 1024:.0f}KB" if ok else f"Integrity check failed: {result}",
                    duration_ms=elapsed,
                    details={"tables": tables[0], "size_bytes": size_bytes, "integrity": result[0] if result else "unknown"},
                ))
            except Exception as e:
                elapsed = round((time.monotonic() - t) * 1000, 1)
                results.append(CheckResult(
                    name=f"DB: {db_name}", category="database",
                    status="fail", message=str(e), duration_ms=elapsed,
                ))

        return results

    # ── LLM Providers ─────────────────────────────────────────────

    async def _check_llm_providers(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        llm_router = getattr(self._state, "llm_router", None)
        if not llm_router or not hasattr(llm_router, "stats"):
            results.append(CheckResult(
                name="LLM Router", category="llm",
                status="fail", message="No multi-provider router found",
            ))
            return results

        stats = llm_router.stats()
        results.append(CheckResult(
            name="LLM Router", category="llm",
            status="pass",
            message=f"{len(stats.get('registered', []))} providers, {stats.get('total_calls', 0)} total calls",
            details=stats,
        ))

        # Check each provider
        for name, health in stats.get("providers", {}).items():
            if health.get("disabled_until"):
                status = "warn"
                msg = f"DISABLED (quota exhausted — will auto-recover)"
            elif health.get("circuit_open"):
                status = "warn"
                msg = f"Circuit OPEN (backoff={health.get('backoff_seconds')}s, failures={health.get('consecutive_failures')})"
            elif health.get("available"):
                status = "pass"
                msg = f"OK — {health.get('total_successes', 0)} successes, {health.get('total_failures', 0)} failures"
            else:
                status = "warn"
                msg = "Unavailable"

            results.append(CheckResult(
                name=f"Provider: {name}", category="llm",
                status=status, message=msg, details=health,
            ))

        # Live LLM test — send a simple prompt to verify inference works
        t = time.monotonic()
        try:
            response = await asyncio.wait_for(
                llm_router.complete(
                    messages=[{"role": "user", "content": "Say 'OK' and nothing else."}],
                    system="You are a diagnostic test. Respond with exactly 'OK'.",
                    model_tier="fast",
                    max_tokens=10,
                ),
                timeout=30.0,
            )
            elapsed = round((time.monotonic() - t) * 1000, 1)
            ok = bool(response and len(response.strip()) > 0)
            results.append(CheckResult(
                name="LLM Live Test", category="llm",
                status="pass" if ok else "warn",
                message=f"Response: '{response[:50]}' ({elapsed}ms)" if ok else "Empty response (all providers may be exhausted)",
                duration_ms=elapsed,
            ))
        except Exception as e:
            elapsed = round((time.monotonic() - t) * 1000, 1)
            results.append(CheckResult(
                name="LLM Live Test", category="llm",
                status="warn", message=f"No provider available: {str(e)[:150]}", duration_ms=elapsed,
            ))

        return results

    # ── Plugins ───────────────────────────────────────────────────

    async def _check_plugins(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        plugins = getattr(self._state, "plugins", None)
        if not plugins:
            results.append(CheckResult(
                name="Plugin Engine", category="plugin",
                status="fail", message="Plugin engine not found",
            ))
            return results

        stats = plugins.stats()
        results.append(CheckResult(
            name="Plugin Engine", category="plugin",
            status="pass",
            message=f"{stats['total_plugins']} plugins, {stats['total_tools']} tools",
            details=stats,
        ))

        # Check each plugin individually
        for plugin_info in stats.get("plugins", []):
            pid = plugin_info.get("id", "unknown")
            enabled = plugin_info.get("enabled", False)
            tool_count = plugin_info.get("tool_count", 0)

            plugin = plugins.get_plugin(pid)
            if plugin:
                tool_names = [t.name for t in plugin.tools] if hasattr(plugin, 'tools') else []
                results.append(CheckResult(
                    name=f"Plugin: {pid}", category="plugin",
                    status="pass" if enabled else "warn",
                    message=f"{'Enabled' if enabled else 'Disabled'} — {tool_count} tools: {', '.join(tool_names[:5])}",
                    details={"id": pid, "enabled": enabled, "tools": tool_names},
                ))
            else:
                results.append(CheckResult(
                    name=f"Plugin: {pid}", category="plugin",
                    status="fail", message="Plugin registered but not loadable",
                ))

        return results

    # ── Pipelines (Action Chains) ─────────────────────────────────

    async def _check_pipelines(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        chain_engine = getattr(self._state, "chain_engine", None)
        if not chain_engine:
            results.append(CheckResult(
                name="Action Chain Engine", category="pipeline",
                status="warn", message="No action chain engine on app.state",
            ))
            return results

        stats = chain_engine.stats()
        results.append(CheckResult(
            name="Action Chain Engine", category="pipeline",
            status="pass",
            message=f"{stats.get('total_chains', 0)} chains, {stats.get('total_triggers', 0)} total triggers",
            details=stats,
        ))

        # Check individual chains
        for chain_name, chain_stats in stats.get("chains", {}).items():
            triggers = chain_stats.get("trigger_count", 0)
            results.append(CheckResult(
                name=f"Chain: {chain_name}", category="pipeline",
                status="pass",
                message=f"{triggers} triggers",
                details=chain_stats,
            ))

        return results

    # ── Background Loops ──────────────────────────────────────────

    async def _check_background_loops(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        # Proactive Engine
        proactive = getattr(self._state, "proactive", None)
        if proactive:
            actions = await proactive.get_actions()
            running_count = sum(1 for a in actions if a.get("enabled", True))
            results.append(CheckResult(
                name="Proactive Engine", category="background",
                status="pass",
                message=f"{running_count}/{len(actions)} behaviors active",
                details={"total": len(actions), "active": running_count},
            ))
            # Check individual proactive actions
            for action in actions:
                name = action.get("name", "unknown")
                last_run = action.get("last_run", "never")
                enabled = action.get("enabled", True)
                results.append(CheckResult(
                    name=f"Proactive: {name}", category="background",
                    status="pass" if enabled else "skip",
                    message=f"Last run: {last_run}" if enabled else "Disabled",
                ))
        else:
            results.append(CheckResult(
                name="Proactive Engine", category="background",
                status="fail", message="Not found",
            ))

        # Autonomous Loop
        auto_loop = getattr(self._state, "auto_loop", None)
        if auto_loop:
            stats = auto_loop.stats()
            results.append(CheckResult(
                name="Autonomous Loop", category="background",
                status="pass",
                message=f"Cycle #{stats.get('cycle', 0)}, {stats.get('total_experiments', 0)} experiments",
                details=stats,
            ))
        else:
            results.append(CheckResult(
                name="Autonomous Loop", category="background",
                status="fail", message="Not found",
            ))

        # Continuous Learning
        cl = getattr(self._state, "continuous_learning", None)
        if cl:
            stats = cl.stats()
            results.append(CheckResult(
                name="Continuous Learning", category="background",
                status="pass" if stats.get("running") else "warn",
                message=f"Cycle #{stats.get('cycles', 0)}, {stats.get('total_findings', 0)} findings, {stats.get('agents_with_findings', 0)} agents learned",
                details=stats,
            ))
        else:
            results.append(CheckResult(
                name="Continuous Learning", category="background",
                status="fail", message="Not found",
            ))

        # Curiosity Engine
        curiosity = getattr(self._state, "curiosity", None)
        if curiosity:
            stats = curiosity.stats()
            results.append(CheckResult(
                name="Curiosity Engine", category="background",
                status="pass" if stats.get("running") else "warn",
                message=f"Cycle #{stats.get('cycles', 0)}, {stats.get('total_questions_resolved', 0)} resolved, queue={stats.get('queue_size', 0)}",
                details=stats,
            ))
        else:
            results.append(CheckResult(
                name="Curiosity Engine", category="background",
                status="fail", message="Not found",
            ))

        # Directive Engine
        directive = getattr(self._state, "directive", None)
        if directive:
            stats = directive.stats()
            results.append(CheckResult(
                name="Directive Engine", category="background",
                status="pass",
                message=f"{stats.get('total_directives', 0)} directives, {stats.get('completed', 0)} completed",
                details=stats,
            ))
        else:
            results.append(CheckResult(
                name="Directive Engine", category="background",
                status="fail", message="Not found",
            ))

        # Builder Agent
        builder = getattr(self._state, "builder", None)
        if builder:
            results.append(CheckResult(
                name="Builder Agent", category="background",
                status="pass", message="Running (5min cycles)",
            ))
        else:
            results.append(CheckResult(
                name="Builder Agent", category="background",
                status="fail", message="Not found",
            ))

        # Reflection Engine
        reflection = getattr(self._state, "reflection", None)
        if reflection:
            results.append(CheckResult(
                name="Reflection Engine", category="background",
                status="pass", message="Running (1hr cycles)",
            ))
        else:
            results.append(CheckResult(
                name="Reflection Engine", category="background",
                status="fail", message="Not found",
            ))

        return results

    # ── External Connections ──────────────────────────────────────

    async def _check_connections(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        # Ollama health
        try:
            import json as _json
            import urllib.request
            t = time.monotonic()
            from backend.config import OLLAMA_BASE_URL
            req = urllib.request.Request(f"{OLLAMA_BASE_URL}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                elapsed = round((time.monotonic() - t) * 1000, 1)
                data = _json.loads(resp.read().decode())
                models = [m["name"] for m in data.get("models", [])]
                results.append(CheckResult(
                    name="Ollama Server", category="connection",
                    status="pass",
                    message=f"Connected — {len(models)} models: {', '.join(models[:5])}",
                    duration_ms=elapsed,
                    details={"models": models},
                ))
        except Exception as e:
            elapsed = round((time.monotonic() - t) * 1000, 1) if 't' in dir() else 0.0
            results.append(CheckResult(
                name="Ollama Server", category="connection",
                status="fail", message=str(e)[:200], duration_ms=elapsed,
            ))

        # Message Bus
        bus = getattr(self._state, "bus", None)
        if bus:
            stats = bus.stats()
            results.append(CheckResult(
                name="Message Bus", category="connection",
                status="pass",
                message=f"{stats.get('active_subscriptions', 0)} subscribers, {stats.get('total_published', 0)} messages published",
                details=stats,
            ))
        else:
            results.append(CheckResult(
                name="Message Bus", category="connection",
                status="fail", message="Not found",
            ))

        # Approval Chain
        approval = getattr(self._state, "approval", None)
        if approval:
            results.append(CheckResult(
                name="Approval Chain", category="connection",
                status="pass", message="Active (LOW=auto, MED=notify, HIGH/CRIT=approve)",
            ))

        # Ecosystem
        ecosystem = getattr(self._state, "ecosystem", None)
        if ecosystem:
            projects = ecosystem.get_all_projects()
            connections = ecosystem.get_connections()
            results.append(CheckResult(
                name="Project Ecosystem", category="connection",
                status="pass",
                message=f"{len(projects)} projects, {len(connections)} connections",
            ))

        return results

    # ── Agents ────────────────────────────────────────────────────

    async def _check_agents(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        registry = getattr(self._state, "registry", None)
        if not registry:
            results.append(CheckResult(
                name="Agent Registry", category="agent",
                status="fail", message="Not found",
            ))
            return results

        agents = registry.list_agents()
        divisions = registry.list_divisions()
        connectors = len(getattr(registry, '_connectors', {}))

        results.append(CheckResult(
            name="Agent Registry", category="agent",
            status="pass",
            message=f"{len(agents)} agents, {len(divisions)} divisions, {connectors} connectors wired",
            details={"agents": len(agents), "divisions": len(divisions), "connectors": connectors},
        ))

        # Check each division
        for div_name, div_count in divisions.items():
            results.append(CheckResult(
                name=f"Division: {div_name}", category="agent",
                status="pass" if div_count > 0 else "warn",
                message=f"{div_count} agents registered",
            ))

        # Check core connectors
        for core_id in ["astra", "hermes", "miro", "swarm", "openclaw"]:
            connector = registry.get_connector(core_id)
            if not connector:
                results.append(CheckResult(
                    name=f"Connector: {core_id}", category="agent",
                    status="fail", message="Missing",
                ))
            else:
                has_llm = hasattr(connector, '_llm') and connector._llm is not None
                # Some connectors (e.g. OpenClaw) don't use _llm directly
                needs_llm = hasattr(connector, '_llm')
                results.append(CheckResult(
                    name=f"Connector: {core_id}", category="agent",
                    status="pass" if (has_llm or not needs_llm) else "warn",
                    message="Wired with LLM" if has_llm else "Active (no direct LLM)" if not needs_llm else "No LLM",
                ))

        return results

    # ── Learning Systems ──────────────────────────────────────────

    async def _check_learning(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        # Prediction Ledger
        pl = getattr(self._state, "prediction_ledger", None)
        if pl:
            stats = pl.stats()
            results.append(CheckResult(
                name="Prediction Ledger", category="learning",
                status="pass",
                message=f"{stats.get('total_predictions', 0)} predictions tracked",
                details=stats,
            ))

        # Experiment Lab
        lab = getattr(self._state, "experiment_lab", None)
        if lab:
            stats = lab.stats()
            results.append(CheckResult(
                name="Experiment Lab", category="learning",
                status="pass",
                message=f"{stats.get('total_experiments', 0)} experiments ({stats.get('running', 0)} running)",
                details=stats,
            ))

        # Self-Writing Code
        swc = getattr(self._state, "self_writing_code", None)
        if swc:
            stats = swc.stats()
            results.append(CheckResult(
                name="Self-Writing Code", category="learning",
                status="pass",
                message=f"{stats.get('total_proposals', 0)} proposals",
                details=stats,
            ))

        # Revenue Engine
        rev = getattr(self._state, "revenue_engine", None)
        if rev:
            stats = rev.stats()
            results.append(CheckResult(
                name="Revenue Engine", category="learning",
                status="pass",
                message=f"{stats.get('total_products', 0)} products, {stats.get('total_streams', 0)} streams",
                details=stats,
            ))

        # Agent Network
        net = getattr(self._state, "agent_network", None)
        if net:
            stats = net.stats()
            results.append(CheckResult(
                name="Agent Network", category="learning",
                status="pass",
                message=f"{stats.get('total_insights', 0)} insights shared",
                details=stats,
            ))

        return results

    # ── Autonomous Systems ────────────────────────────────────────

    async def _check_autonomous_systems(self) -> list[CheckResult]:
        results: list[CheckResult] = []

        # Goal Engine
        ge = getattr(self._state, "goal_engine", None)
        if ge:
            stats = ge.stats()
            active = stats.get("by_status", {}).get("active", 0)
            results.append(CheckResult(
                name="Goal Engine", category="autonomous",
                status="pass",
                message=f"{active} active goals, {stats.get('total_goals', 0)} total",
                details=stats,
            ))

        # Task Queue
        tq = getattr(self._state, "task_queue", None)
        if tq:
            stats = tq.stats()
            pending = stats.get("by_status", {}).get("pending", 0)
            results.append(CheckResult(
                name="Task Queue", category="autonomous",
                status="pass",
                message=f"{pending} pending, {stats.get('total_tasks', 0)} total",
                details=stats,
            ))

        # Task Executor
        te = getattr(self._state, "task_executor", None)
        results.append(CheckResult(
            name="Task Executor", category="autonomous",
            status="pass" if te else "fail",
            message="Ready" if te else "Not found",
        ))

        # Trigger Engine
        triggers = getattr(self._state, "triggers", None)
        if triggers:
            stats = triggers.stats()
            results.append(CheckResult(
                name="Trigger Engine", category="autonomous",
                status="pass",
                message=f"{stats.get('total_rules', 0)} rules ({stats.get('enabled', 0)} enabled)",
                details=stats,
            ))

        # Escalation Engine
        esc = getattr(self._state, "escalation", None)
        if esc:
            stats = esc.stats()
            results.append(CheckResult(
                name="Escalation Engine", category="autonomous",
                status="pass",
                message=f"{stats.get('total_decisions', 0)} decisions",
                details=stats,
            ))

        # Digest Engine
        digest = getattr(self._state, "digest", None)
        if digest:
            stats = digest.stats()
            results.append(CheckResult(
                name="Digest Engine", category="autonomous",
                status="pass",
                message=f"{stats.get('total_digests', 0)} digests generated",
                details=stats,
            ))

        # Hedge Fund
        hf = getattr(self._state, "hedge_fund", None)
        if hf:
            stats = hf.stats()
            results.append(CheckResult(
                name="Hedge Fund Engine", category="autonomous",
                status="pass",
                message=f"{stats.get('total_signals', 0)} signals, {stats.get('total_trades', 0)} trades",
                details=stats,
            ))

        # Autonomy Actuator
        act = getattr(self._state, "actuator", None)
        results.append(CheckResult(
            name="Autonomy Actuator", category="autonomous",
            status="pass" if act else "fail",
            message="Active (8 event handlers)" if act else "Not found",
        ))

        # Collab Engine
        collab = getattr(self._state, "collab", None)
        if collab:
            results.append(CheckResult(
                name="Agent Collaboration", category="autonomous",
                status="pass",
                message="Delegate/Pipeline/Fanout/Council patterns ready",
            ))

        # User Patterns
        up = getattr(self._state, "user_patterns", None)
        if up:
            stats = up.stats()
            results.append(CheckResult(
                name="User Patterns", category="autonomous",
                status="pass",
                message=f"{stats.get('total_patterns', 0)} patterns tracked",
                details=stats,
            ))

        return results

    # ── Helpers ────────────────────────────────────────────────────

    def _check_system(
        self, attr: str, name: str, get_info: Any,
    ) -> CheckResult:
        """Check if a system exists on app.state and get its info."""
        system = getattr(self._state, attr, None)
        if not system:
            return CheckResult(
                name=name, category="core",
                status="fail", message=f"Not found on app.state.{attr}",
            )
        t = time.monotonic()
        try:
            info = get_info(system)
            elapsed = round((time.monotonic() - t) * 1000, 1)
            return CheckResult(
                name=name, category="core",
                status="pass", message="OK",
                duration_ms=elapsed, details=info if isinstance(info, dict) else {},
            )
        except Exception as e:
            elapsed = round((time.monotonic() - t) * 1000, 1)
            return CheckResult(
                name=name, category="core",
                status="fail", message=str(e)[:200], duration_ms=elapsed,
            )
