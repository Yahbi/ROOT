"""
State Store — persistent runtime state for systems that would otherwise lose data on restart.

Persists:
- ProactiveAction execution state (run_count, error_count, last_run, last_result)
- AutonomousLoop experiments and cycle count
- Plugin invocation audit log
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.state_store")

STATE_DB = ROOT_DIR / "data" / "state.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateStore:
    """Lightweight SQLite persistence for runtime state."""

    def __init__(self, db_path: Path = STATE_DB) -> None:
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()

    def start(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()
        logger.info("State store: started (%s)", self._db_path)

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self, '_conn') and self._conn:
            self._conn.close()

    @property
    def conn(self) -> sqlite3.Connection:
        if not self._conn:
            self.start()
        return self._conn  # type: ignore[return-value]

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS proactive_state (
                name TEXT PRIMARY KEY,
                run_count INTEGER NOT NULL DEFAULT 0,
                error_count INTEGER NOT NULL DEFAULT 0,
                last_run TEXT,
                last_result TEXT
            );

            CREATE TABLE IF NOT EXISTS experiment_state (
                id TEXT PRIMARY KEY,
                area TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'proposed',
                baseline TEXT,
                result TEXT,
                improvement REAL DEFAULT 0,
                created_at TEXT NOT NULL,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS cycle_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS plugin_invocations (
                id TEXT PRIMARY KEY,
                plugin_name TEXT NOT NULL,
                tool_name TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 1,
                duration_ms REAL DEFAULT 0,
                error_message TEXT,
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_plugin_inv_created
                ON plugin_invocations(created_at);
            CREATE INDEX IF NOT EXISTS idx_plugin_inv_tool
                ON plugin_invocations(tool_name);
        """)

    # ── Proactive State ──────────────────────────────────────────

    def load_proactive_state(self) -> dict[str, dict[str, Any]]:
        """Load all proactive action states. Returns {name: {run_count, error_count, ...}}."""
        rows = self.conn.execute("SELECT * FROM proactive_state").fetchall()
        return {
            row["name"]: {
                "run_count": row["run_count"],
                "error_count": row["error_count"],
                "last_run": row["last_run"],
                "last_result": row["last_result"],
            }
            for row in rows
        }

    def save_proactive_state(
        self, name: str, run_count: int, error_count: int,
        last_run: Optional[str], last_result: Optional[str],
    ) -> None:
        """Save proactive action state (upsert)."""
        with self._lock:
            self.conn.execute(
                """INSERT INTO proactive_state (name, run_count, error_count, last_run, last_result)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(name) DO UPDATE SET
                       run_count = excluded.run_count,
                       error_count = excluded.error_count,
                       last_run = excluded.last_run,
                       last_result = excluded.last_result""",
                (name, run_count, error_count, last_run, (last_result or "")[:2000]),
            )
            self.conn.commit()

    # ── Experiment State ─────────────────────────────────────────

    def load_experiments(self, limit: int = 50) -> list[dict[str, Any]]:
        """Load recent experiments."""
        rows = self.conn.execute(
            "SELECT * FROM experiment_state ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(row) for row in rows]

    def save_experiment(
        self, experiment_id: str, area: str, hypothesis: str,
        status: str = "proposed", baseline: str = "",
        result: str = "", improvement: float = 0,
    ) -> None:
        """Save or update an experiment."""
        now = _now_iso()
        completed = now if status in ("completed", "failed") else None
        with self._lock:
            self.conn.execute(
                """INSERT INTO experiment_state
                   (id, area, hypothesis, status, baseline, result, improvement, created_at, completed_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       status = excluded.status,
                       result = excluded.result,
                       improvement = excluded.improvement,
                       completed_at = excluded.completed_at""",
                (experiment_id, area, hypothesis[:500], status,
                 baseline[:500], result[:2000], improvement, now, completed),
            )
            self.conn.commit()

    # ── Cycle Meta ───────────────────────────────────────────────

    def get_meta(self, key: str, default: str = "0") -> str:
        """Get a metadata value."""
        row = self.conn.execute(
            "SELECT value FROM cycle_meta WHERE key = ?", (key,),
        ).fetchone()
        return row["value"] if row else default

    def set_meta(self, key: str, value: str) -> None:
        """Set a metadata value (upsert)."""
        with self._lock:
            self.conn.execute(
                """INSERT INTO cycle_meta (key, value) VALUES (?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value""",
                (key, value),
            )
            self.conn.commit()

    # ── Plugin Invocation Log ────────────────────────────────────

    def log_plugin_invocation(
        self, plugin_name: str, tool_name: str,
        success: bool, duration_ms: float = 0,
        error_message: str = "",
    ) -> None:
        """Log a plugin tool invocation for audit trail."""
        with self._lock:
            self.conn.execute(
                """INSERT INTO plugin_invocations
                   (id, plugin_name, tool_name, success, duration_ms, error_message, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    f"pi_{uuid.uuid4().hex[:12]}",
                    plugin_name, tool_name,
                    1 if success else 0, duration_ms,
                    error_message[:500] if error_message else None,
                    _now_iso(),
                ),
            )
            self.conn.commit()

    def get_plugin_stats(self) -> dict[str, Any]:
        """Get plugin invocation statistics."""
        rows = self.conn.execute("""
            SELECT tool_name,
                   COUNT(*) as total,
                   SUM(success) as successes,
                   AVG(duration_ms) as avg_duration
            FROM plugin_invocations
            GROUP BY tool_name
            ORDER BY total DESC
        """).fetchall()
        return {
            row["tool_name"]: {
                "total": row["total"],
                "success_rate": round((row["successes"] or 0) / row["total"], 3),
                "avg_duration_ms": round(row["avg_duration"] or 0, 1),
            }
            for row in rows
        }

    def stats(self) -> dict[str, Any]:
        """Overall state store statistics."""
        proactive = self.conn.execute("SELECT COUNT(*) as c FROM proactive_state").fetchone()
        experiments = self.conn.execute("SELECT COUNT(*) as c FROM experiment_state").fetchone()
        invocations = self.conn.execute("SELECT COUNT(*) as c FROM plugin_invocations").fetchone()
        return {
            "proactive_actions_tracked": proactive["c"] if proactive else 0,
            "experiments_tracked": experiments["c"] if experiments else 0,
            "plugin_invocations_logged": invocations["c"] if invocations else 0,
        }
