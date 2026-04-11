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

from backend.config import LLM_DAILY_BUDGET, LLM_MONTHLY_BUDGET, ROOT_DIR

logger = logging.getLogger("root.cost_tracker")

COST_DB = ROOT_DIR / "data" / "costs.db"

# ── Pricing per 1M tokens (as of 2025) ─────────────────────────────
# Update these when model prices change.
# Anthropic cache pricing: cache_read = 10% of input price (90% savings),
# cache_creation = 125% of input price (25% write premium).

_PRICING: dict[str, dict[str, float]] = {
    # Anthropic
    "claude-haiku-4-5-20241022": {"input": 1.00, "output": 5.00, "cache_read": 0.10, "cache_write": 1.25},
    "claude-sonnet-4-20250514": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "claude-opus-4-20250514": {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75},
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


def compute_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_creation_tokens: int = 0,
) -> float:
    """Compute USD cost for a single LLM call.

    When *cache_read_tokens* or *cache_creation_tokens* are supplied
    (Anthropic prompt caching), the cached portion is billed at the
    discounted rate (90% savings for reads, 25% premium for writes)
    and subtracted from regular input billing.
    """
    pricing = _PRICING.get(model, _DEFAULT_PRICING)

    # Regular input tokens (exclude tokens already counted as cache read/write)
    regular_input = max(input_tokens - cache_read_tokens - cache_creation_tokens, 0)
    cost = regular_input * pricing["input"] / 1_000_000

    # Cache read tokens (90% cheaper than regular input)
    if cache_read_tokens > 0:
        cache_read_price = pricing.get("cache_read", pricing["input"] * 0.1)
        cost += cache_read_tokens * cache_read_price / 1_000_000

    # Cache creation tokens (25% premium over regular input)
    if cache_creation_tokens > 0:
        cache_write_price = pricing.get("cache_write", pricing["input"] * 1.25)
        cost += cache_creation_tokens * cache_write_price / 1_000_000

    # Output tokens
    cost += output_tokens * pricing["output"] / 1_000_000
    return cost


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
                method TEXT DEFAULT 'complete',
                cache_read_tokens INTEGER DEFAULT 0,
                cache_creation_tokens INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_calls_timestamp ON llm_calls(timestamp);
            CREATE INDEX IF NOT EXISTS idx_calls_model ON llm_calls(model);
            CREATE INDEX IF NOT EXISTS idx_calls_agent ON llm_calls(caller_agent);
        """)
        # Migrate existing tables — add cache columns if missing
        self._migrate_cache_columns()

    def _migrate_cache_columns(self) -> None:
        """Add cache_read_tokens / cache_creation_tokens columns if missing."""
        try:
            cols = {
                row[1]
                for row in self.conn.execute("PRAGMA table_info(llm_calls)").fetchall()
            }
            if "cache_read_tokens" not in cols:
                self.conn.execute(
                    "ALTER TABLE llm_calls ADD COLUMN cache_read_tokens INTEGER DEFAULT 0"
                )
            if "cache_creation_tokens" not in cols:
                self.conn.execute(
                    "ALTER TABLE llm_calls ADD COLUMN cache_creation_tokens INTEGER DEFAULT 0"
                )
            self.conn.commit()
        except Exception as exc:
            logger.debug("Cache column migration skipped: %s", exc)

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
        cache_read_tokens: int = 0,
        cache_creation_tokens: int = 0,
    ) -> float:
        """Record an LLM call. Returns computed cost in USD.

        When *cache_read_tokens* / *cache_creation_tokens* are supplied
        (from Anthropic prompt caching), the cost calculation accounts for
        the 90% discount on cached reads and 25% premium on cache writes.
        """
        cost = compute_cost(
            model, input_tokens, output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_creation_tokens=cache_creation_tokens,
        )
        if cache_read_tokens > 0:
            logger.debug(
                "Cache savings: %d tokens read from cache (model=%s, ~%.4f USD saved)",
                cache_read_tokens, model,
                cache_read_tokens * _PRICING.get(model, _DEFAULT_PRICING)["input"] * 0.9 / 1_000_000,
            )
        self.conn.execute(
            """INSERT INTO llm_calls
               (timestamp, provider, model, model_tier, caller_agent,
                input_tokens, output_tokens, total_tokens, cost_usd,
                duration_ms, method, cache_read_tokens, cache_creation_tokens)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _now_iso(), provider, model, model_tier, caller_agent,
                input_tokens, output_tokens, input_tokens + output_tokens,
                cost, duration_ms, method,
                cache_read_tokens, cache_creation_tokens,
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

    def cache_savings(self) -> dict[str, Any]:
        """Return aggregate cache token savings."""
        row = self.conn.execute(
            "SELECT COALESCE(SUM(cache_read_tokens), 0) as total_cache_read, "
            "COALESCE(SUM(cache_creation_tokens), 0) as total_cache_write "
            "FROM llm_calls"
        ).fetchone()
        total_cache_read = row["total_cache_read"]
        total_cache_write = row["total_cache_write"]

        # Estimate savings: cache reads cost 10% of normal input price,
        # so savings = 90% of what those tokens would have cost at full input price.
        # Use default pricing for estimation.
        est_savings = total_cache_read * _DEFAULT_PRICING["input"] * 0.9 / 1_000_000
        return {
            "cache_read_tokens": total_cache_read,
            "cache_creation_tokens": total_cache_write,
            "estimated_savings_usd": round(est_savings, 4),
        }

    # ── Budget Enforcement ────────────────────────────────────────

    def is_within_budget(self) -> bool:
        """Check if current spend is within configured daily and monthly budgets.

        Returns ``True`` if spend is under limits (or if limits are not set / 0).
        Budget limits are read from ``LLM_DAILY_BUDGET`` and ``LLM_MONTHLY_BUDGET``
        in config (via env vars ``ROOT_DAILY_BUDGET``, ``ROOT_MONTHLY_BUDGET``).
        """
        if LLM_DAILY_BUDGET <= 0 and LLM_MONTHLY_BUDGET <= 0:
            return True  # No limits configured

        summary = self.summary()
        daily_spend = summary["daily"]["cost_usd"]
        monthly_spend = summary["monthly"]["cost_usd"]

        if LLM_DAILY_BUDGET > 0 and daily_spend >= LLM_DAILY_BUDGET:
            logger.warning(
                "Daily LLM budget exceeded: spent $%.2f of $%.2f",
                daily_spend, LLM_DAILY_BUDGET,
            )
            return False
        if LLM_MONTHLY_BUDGET > 0 and monthly_spend >= LLM_MONTHLY_BUDGET:
            logger.warning(
                "Monthly LLM budget exceeded: spent $%.2f of $%.2f",
                monthly_spend, LLM_MONTHLY_BUDGET,
            )
            return False
        return True

    def get_remaining_budget(self) -> dict[str, Any]:
        """Return daily and monthly remaining budgets.

        If a budget limit is 0 (unset), the corresponding ``*_remaining`` field
        is ``None`` (unlimited).
        """
        summary = self.summary()
        daily_spend = summary["daily"]["cost_usd"]
        monthly_spend = summary["monthly"]["cost_usd"]

        daily_remaining: Optional[float] = None
        monthly_remaining: Optional[float] = None

        if LLM_DAILY_BUDGET > 0:
            daily_remaining = round(LLM_DAILY_BUDGET - daily_spend, 4)
        if LLM_MONTHLY_BUDGET > 0:
            monthly_remaining = round(LLM_MONTHLY_BUDGET - monthly_spend, 4)

        within = True
        if LLM_DAILY_BUDGET > 0 and daily_spend >= LLM_DAILY_BUDGET:
            within = False
        if LLM_MONTHLY_BUDGET > 0 and monthly_spend >= LLM_MONTHLY_BUDGET:
            within = False

        return {
            "daily_spend": round(daily_spend, 4),
            "daily_limit": LLM_DAILY_BUDGET if LLM_DAILY_BUDGET > 0 else None,
            "daily_remaining": daily_remaining,
            "monthly_spend": round(monthly_spend, 4),
            "monthly_limit": LLM_MONTHLY_BUDGET if LLM_MONTHLY_BUDGET > 0 else None,
            "monthly_remaining": monthly_remaining,
            "within_budget": within,
        }

    def stats(self) -> dict[str, Any]:
        """Quick stats for dashboard integration."""
        return self.summary()
