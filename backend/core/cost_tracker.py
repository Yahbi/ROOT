"""LLM Cost Tracker — records every LLM call with token usage and computed cost.

Provides SQLite-backed persistence with daily/weekly/monthly aggregates
and per-agent cost breakdowns.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.cost_tracker")

COST_DB = ROOT_DIR / "data" / "costs.db"

# ── Pricing per 1M tokens (as of 2025) ─────────────────────────────
# Update these when model prices change.

_PRICING: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-haiku-4-5-20241022": {"input": 1.00, "output": 5.00},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00},
    # OpenAI
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "o3-mini": {"input": 1.10, "output": 4.40},
    # DeepSeek (open-source, very cost-effective)
    "deepseek-chat": {"input": 0.14, "output": 0.28},
    "deepseek-reasoner": {"input": 0.55, "output": 2.19},
}

# Fallback for unknown models
_DEFAULT_PRICING = {"input": 3.00, "output": 15.00}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Compute USD cost for a single LLM call."""
    pricing = _PRICING.get(model, _DEFAULT_PRICING)
    return (
        input_tokens * pricing["input"] / 1_000_000
        + output_tokens * pricing["output"] / 1_000_000
    )


class CostTracker:
    """SQLite-backed LLM cost tracker."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or COST_DB
        self._conn: Optional[sqlite3.Connection] = None

    def start(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        logger.info("CostTracker started (db=%s)", self._db_path)

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("CostTracker not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                model_tier TEXT DEFAULT 'default',
                caller_agent TEXT DEFAULT 'root',
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                duration_ms INTEGER DEFAULT 0,
                method TEXT DEFAULT 'complete'
            );

            CREATE INDEX IF NOT EXISTS idx_calls_timestamp ON llm_calls(timestamp);
            CREATE INDEX IF NOT EXISTS idx_calls_model ON llm_calls(model);
            CREATE INDEX IF NOT EXISTS idx_calls_agent ON llm_calls(caller_agent);
        """)

    # ── Recording ──────────────────────────────────────────────────

    def record(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        model_tier: str = "default",
        caller_agent: str = "root",
        duration_ms: int = 0,
        method: str = "complete",
    ) -> float:
        """Record an LLM call. Returns computed cost in USD."""
        cost = compute_cost(model, input_tokens, output_tokens)
        self.conn.execute(
            """INSERT INTO llm_calls
               (timestamp, provider, model, model_tier, caller_agent,
                input_tokens, output_tokens, total_tokens, cost_usd,
                duration_ms, method)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _now_iso(), provider, model, model_tier, caller_agent,
                input_tokens, output_tokens, input_tokens + output_tokens,
                cost, duration_ms, method,
            ),
        )
        self.conn.commit()
        return cost

    # ── Queries ────────────────────────────────────────────────────

    def summary(self) -> dict[str, Any]:
        """Get overall cost summary with daily/weekly/monthly breakdowns."""
        row = self.conn.execute(
            "SELECT COUNT(*) as calls, COALESCE(SUM(cost_usd), 0) as total_cost, "
            "COALESCE(SUM(input_tokens), 0) as total_input, "
            "COALESCE(SUM(output_tokens), 0) as total_output "
            "FROM llm_calls"
        ).fetchone()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        daily = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) as cost, COUNT(*) as calls "
            "FROM llm_calls WHERE timestamp >= ?",
            (today,),
        ).fetchone()

        # Last 7 days
        weekly = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) as cost, COUNT(*) as calls "
            "FROM llm_calls WHERE timestamp >= date('now', '-7 days')"
        ).fetchone()

        # Last 30 days
        monthly = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) as cost, COUNT(*) as calls "
            "FROM llm_calls WHERE timestamp >= date('now', '-30 days')"
        ).fetchone()

        return {
            "total_calls": row["calls"],
            "total_cost_usd": round(row["total_cost"], 4),
            "total_input_tokens": row["total_input"],
            "total_output_tokens": row["total_output"],
            "daily": {"cost_usd": round(daily["cost"], 4), "calls": daily["calls"]},
            "weekly": {"cost_usd": round(weekly["cost"], 4), "calls": weekly["calls"]},
            "monthly": {"cost_usd": round(monthly["cost"], 4), "calls": monthly["calls"]},
        }

    def by_agent(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get cost breakdown by caller agent."""
        rows = self.conn.execute(
            "SELECT caller_agent, COUNT(*) as calls, "
            "COALESCE(SUM(cost_usd), 0) as total_cost, "
            "COALESCE(SUM(input_tokens), 0) as input_tokens, "
            "COALESCE(SUM(output_tokens), 0) as output_tokens "
            "FROM llm_calls GROUP BY caller_agent "
            "ORDER BY total_cost DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "agent": r["caller_agent"],
                "calls": r["calls"],
                "cost_usd": round(r["total_cost"], 4),
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
            }
            for r in rows
        ]

    def by_model(self) -> list[dict[str, Any]]:
        """Get cost breakdown by model."""
        rows = self.conn.execute(
            "SELECT model, COUNT(*) as calls, "
            "COALESCE(SUM(cost_usd), 0) as total_cost, "
            "COALESCE(SUM(input_tokens), 0) as input_tokens, "
            "COALESCE(SUM(output_tokens), 0) as output_tokens "
            "FROM llm_calls GROUP BY model ORDER BY total_cost DESC"
        ).fetchall()
        return [
            {
                "model": r["model"],
                "calls": r["calls"],
                "cost_usd": round(r["total_cost"], 4),
                "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"],
            }
            for r in rows
        ]

    def daily_trend(self, days: int = 30) -> list[dict[str, Any]]:
        """Get daily cost trend."""
        rows = self.conn.execute(
            "SELECT DATE(timestamp) as day, COUNT(*) as calls, "
            "COALESCE(SUM(cost_usd), 0) as cost, "
            "COALESCE(SUM(input_tokens + output_tokens), 0) as tokens "
            "FROM llm_calls "
            "WHERE timestamp >= date('now', ? || ' days') "
            "GROUP BY day ORDER BY day",
            (f"-{days}",),
        ).fetchall()
        return [
            {
                "date": r["day"],
                "calls": r["calls"],
                "cost_usd": round(r["cost"], 4),
                "tokens": r["tokens"],
            }
            for r in rows
        ]

    def stats(self) -> dict[str, Any]:
        """Quick stats for dashboard integration."""
        return self.summary()
