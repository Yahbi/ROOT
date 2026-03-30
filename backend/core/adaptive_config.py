"""
Adaptive Configuration — persistent self-tuning parameter system.

Replaces hardcoded thresholds with dynamically adjustable parameters
backed by SQLite.  Every parameter has bounds (min/max), a default,
and a full adjustment history so ROOT can inspect *why* a value changed.

Usage:
    cfg = AdaptiveConfig()
    cfg.start()
    interval = cfg.get("proactive_market_interval", 300)
    cfg.adjust("proactive_market_interval", +30, reason="market scanner underperforming")
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config import DATA_DIR

logger = logging.getLogger("root.adaptive")

_DEFAULT_DB = DATA_DIR / "adaptive_config.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Default parameter definitions ────────────────────────────────

@dataclass(frozen=True)
class ParamDef:
    """Immutable definition for a tunable parameter."""

    name: str
    default: float
    min_val: float
    max_val: float
    description: str = ""


_DEFAULT_PARAMS: list[ParamDef] = [
    ParamDef("proactive_market_interval", 300, 60, 3600, "Market scanner interval (seconds)"),
    ParamDef("proactive_health_interval", 300, 60, 1800, "Health monitor interval (seconds)"),
    ParamDef("proactive_goal_interval", 3600, 300, 14400, "Goal tracker interval (seconds)"),
    ParamDef("orchestrator_max_concurrent", 3, 1, 10, "Max concurrent orchestrator tasks"),
    ParamDef("autonomous_loop_interval", 1800, 300, 7200, "Autonomous loop cycle interval (seconds)"),
    ParamDef("directive_cycle_interval", 900, 300, 3600, "Directive engine cycle interval (seconds)"),
    ParamDef("signal_min_confidence", 0.65, 0.3, 0.95, "Minimum signal confidence threshold"),
    ParamDef("trade_cooldown_minutes", 30, 5, 240, "Cooldown between trades (minutes)"),
    ParamDef("memory_decay_factor", 0.995, 0.9, 0.999, "Memory confidence decay factor per cycle"),
]


# ── AdaptiveConfig ───────────────────────────────────────────────

class AdaptiveConfig:
    """Persistent self-tuning parameter store backed by SQLite.

    All parameter values are clamped to their registered [min, max] bounds.
    Every change is recorded in the ``adjustments`` audit table with a reason.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or _DEFAULT_DB
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        self._started = False

    # ── Lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """Open the database, create tables, and register default params."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()
        self._register_defaults()
        self._started = True
        logger.info("AdaptiveConfig started (db=%s, params=%d)", self._db_path, len(_DEFAULT_PARAMS))

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
        self._started = False

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("AdaptiveConfig not started")
        return self._conn

    # ── Schema ────────────────────────────────────────────────

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS params (
                name          TEXT PRIMARY KEY,
                current_value REAL NOT NULL,
                default_value REAL NOT NULL,
                min_value     REAL NOT NULL,
                max_value     REAL NOT NULL,
                description   TEXT NOT NULL DEFAULT '',
                last_adjusted TEXT
            );

            CREATE TABLE IF NOT EXISTS adjustments (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                param       TEXT NOT NULL,
                old_value   REAL NOT NULL,
                new_value   REAL NOT NULL,
                reason      TEXT NOT NULL DEFAULT '',
                adjusted_at TEXT NOT NULL DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_adjustments_param
                ON adjustments(param);
            CREATE INDEX IF NOT EXISTS idx_adjustments_at
                ON adjustments(adjusted_at);
        """)

    def _register_defaults(self) -> None:
        """Seed all default parameters (skip if already present)."""
        for p in _DEFAULT_PARAMS:
            self.register(p.name, p.default, p.min_val, p.max_val, p.description)

    # ── Public API ────────────────────────────────────────────

    def register(
        self,
        param: str,
        default: float,
        min_val: float,
        max_val: float,
        description: str = "",
    ) -> None:
        """Register a tunable parameter with bounds.

        If the parameter already exists it is *not* overwritten — this allows
        persisted tunings to survive restarts.
        """
        with self._lock:
            existing = self.conn.execute(
                "SELECT 1 FROM params WHERE name = ?", (param,),
            ).fetchone()
            if existing:
                return
            self.conn.execute(
                """INSERT INTO params (name, current_value, default_value, min_value, max_value, description, last_adjusted)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (param, default, default, min_val, max_val, description, _now_iso()),
            )
            self.conn.commit()
            logger.debug("Registered param %s (default=%.4f, range=[%.4f, %.4f])", param, default, min_val, max_val)

    def get(self, param: str, default: Optional[float] = None) -> float:
        """Get the current value for *param*.

        Returns *default* (or raises ``KeyError``) when the param is unknown.
        """
        with self._lock:
            row = self.conn.execute(
                "SELECT current_value FROM params WHERE name = ?", (param,),
            ).fetchone()
            if row is None:
                if default is not None:
                    return default
                raise KeyError(f"Unknown adaptive param: {param}")
            return float(row["current_value"])

    def set(self, param: str, value: float, reason: str = "") -> None:
        """Set *param* to *value*, clamped to its registered bounds."""
        with self._lock:
            row = self.conn.execute(
                "SELECT current_value, min_value, max_value FROM params WHERE name = ?",
                (param,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown adaptive param: {param}")

            old_value = float(row["current_value"])
            clamped = max(float(row["min_value"]), min(float(row["max_value"]), value))

            self.conn.execute(
                "UPDATE params SET current_value = ?, last_adjusted = ? WHERE name = ?",
                (clamped, _now_iso(), param),
            )
            self.conn.execute(
                "INSERT INTO adjustments (param, old_value, new_value, reason, adjusted_at) VALUES (?, ?, ?, ?, ?)",
                (param, old_value, clamped, reason, _now_iso()),
            )
            self.conn.commit()
            if old_value != clamped:
                logger.info("Param %s: %.4f -> %.4f (%s)", param, old_value, clamped, reason or "no reason")

    def adjust(self, param: str, delta: float, reason: str = "") -> float:
        """Adjust *param* by *delta*, clamped to bounds. Returns the new value."""
        with self._lock:
            row = self.conn.execute(
                "SELECT current_value, min_value, max_value FROM params WHERE name = ?",
                (param,),
            ).fetchone()
            if row is None:
                raise KeyError(f"Unknown adaptive param: {param}")

            old_value = float(row["current_value"])
            new_value = max(float(row["min_value"]), min(float(row["max_value"]), old_value + delta))

            self.conn.execute(
                "UPDATE params SET current_value = ?, last_adjusted = ? WHERE name = ?",
                (new_value, _now_iso(), param),
            )
            self.conn.execute(
                "INSERT INTO adjustments (param, old_value, new_value, reason, adjusted_at) VALUES (?, ?, ?, ?, ?)",
                (param, old_value, new_value, reason, _now_iso()),
            )
            self.conn.commit()
            if old_value != new_value:
                logger.info("Param %s: %.4f -> %.4f (delta=%.4f, %s)", param, old_value, new_value, delta, reason or "no reason")
            return new_value

    def get_history(self, param: str, limit: int = 20) -> list[dict]:
        """Return the most recent adjustment history entries for *param*."""
        with self._lock:
            rows = self.conn.execute(
                """SELECT param, old_value, new_value, reason, adjusted_at
                   FROM adjustments
                   WHERE param = ?
                   ORDER BY adjusted_at DESC
                   LIMIT ?""",
                (param, limit),
            ).fetchall()
            return [
                {
                    "param": r["param"],
                    "old_value": r["old_value"],
                    "new_value": r["new_value"],
                    "reason": r["reason"],
                    "adjusted_at": r["adjusted_at"],
                }
                for r in rows
            ]

    def get_all(self) -> dict[str, dict]:
        """Return all parameters with current values and bounds."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT name, current_value, default_value, min_value, max_value, description, last_adjusted FROM params"
            ).fetchall()
            return {
                r["name"]: {
                    "current_value": r["current_value"],
                    "default_value": r["default_value"],
                    "min_value": r["min_value"],
                    "max_value": r["max_value"],
                    "description": r["description"],
                    "last_adjusted": r["last_adjusted"],
                }
                for r in rows
            }

    def stats(self) -> dict[str, Any]:
        """Summary statistics for the adaptive config system."""
        with self._lock:
            param_count = self.conn.execute("SELECT COUNT(*) as c FROM params").fetchone()
            adj_count = self.conn.execute("SELECT COUNT(*) as c FROM adjustments").fetchone()
            # How many params have drifted from their defaults?
            drifted = self.conn.execute(
                "SELECT COUNT(*) as c FROM params WHERE current_value != default_value"
            ).fetchone()
            return {
                "total_params": param_count["c"] if param_count else 0,
                "total_adjustments": adj_count["c"] if adj_count else 0,
                "params_drifted_from_default": drifted["c"] if drifted else 0,
                "started": self._started,
                "db_path": str(self._db_path),
            }
