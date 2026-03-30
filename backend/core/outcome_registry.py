"""
Outcome Registry — Persistent storage for all autonomous action outcomes.

Every autonomous action (proactive, directive, experiment, agent task) records
its outcome here. Provides effectiveness queries by action type and agent,
enabling the closed-loop learning system to identify what works and what doesn't.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from backend.config import DATA_DIR

logger = logging.getLogger("root.outcome_registry")

OUTCOMES_DB = DATA_DIR / "outcomes.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class OutcomeRegistry:
    """Persistent registry tracking outcomes of every autonomous action.

    SQLite-backed with WAL mode for concurrent read/write safety.
    Supports queries by action type, quality threshold, and agent.
    """

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path = db_path or str(OUTCOMES_DB)
        self._conn: Optional[sqlite3.Connection] = None

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        """Initialize the outcome registry database."""
        from pathlib import Path

        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()
        logger.info("OutcomeRegistry started (db=%s)", self._db_path)

    def stop(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("OutcomeRegistry not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS outcomes (
                id TEXT PRIMARY KEY,
                action_type TEXT NOT NULL,
                action_id TEXT NOT NULL,
                intent TEXT NOT NULL,
                result TEXT NOT NULL,
                quality_score REAL NOT NULL,
                context TEXT DEFAULT '{}',
                created_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_outcomes_action_type
                ON outcomes(action_type);
            CREATE INDEX IF NOT EXISTS idx_outcomes_quality
                ON outcomes(quality_score);
            CREATE INDEX IF NOT EXISTS idx_outcomes_created
                ON outcomes(created_at);
        """)

    # ── Recording ─────────────────────────────────────────────────

    def record(
        self,
        action_type: str,
        action_id: str,
        intent: str,
        result: str,
        quality_score: float,
        context: Optional[dict] = None,
    ) -> str:
        """Record an autonomous action outcome. Returns outcome_id.

        Args:
            action_type: Category of action (e.g., "proactive", "directive",
                         "experiment", "agent_task", "trade").
            action_id:   Unique identifier of the specific action instance.
            intent:      What the action was trying to accomplish.
            result:      The actual output / result text.
            quality_score: Evaluated quality 0.0–1.0.
            context:     Optional metadata dict (agent_id, duration, etc.).

        Returns:
            Generated outcome_id string.
        """
        outcome_id = f"out_{uuid.uuid4().hex[:12]}"
        ctx_str = json.dumps(context or {})

        self.conn.execute(
            """INSERT INTO outcomes
               (id, action_type, action_id, intent, result, quality_score, context, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                outcome_id,
                action_type,
                action_id,
                intent[:2000],
                result[:5000],
                max(0.0, min(1.0, quality_score)),
                ctx_str,
                _now_iso(),
            ),
        )
        self.conn.commit()

        logger.debug(
            "Recorded outcome %s: type=%s quality=%.2f",
            outcome_id, action_type, quality_score,
        )
        return outcome_id

    # ── Queries ───────────────────────────────────────────────────

    def get_outcomes(
        self,
        action_type: Optional[str] = None,
        min_quality: float = 0.0,
        limit: int = 50,
    ) -> list[dict]:
        """Retrieve outcomes with optional filters.

        Args:
            action_type: Filter by action type (None = all).
            min_quality: Minimum quality_score threshold.
            limit:       Maximum number of results.

        Returns:
            List of outcome dicts ordered by created_at DESC.
        """
        sql = "SELECT * FROM outcomes WHERE quality_score >= ?"
        params: list[Any] = [min_quality]

        if action_type:
            sql += " AND action_type = ?"
            params.append(action_type)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_effectiveness(self, action_type: str) -> dict:
        """Get effectiveness statistics for an action type.

        Returns:
            Dict with avg_quality, success_rate (quality >= 0.4), total_count.
        """
        row = self.conn.execute(
            """SELECT
                COUNT(*) as total_count,
                AVG(quality_score) as avg_quality,
                SUM(CASE WHEN quality_score >= 0.4 THEN 1 ELSE 0 END) as success_count
               FROM outcomes
               WHERE action_type = ?""",
            (action_type,),
        ).fetchone()

        if not row or row["total_count"] == 0:
            return {"avg_quality": 0.0, "success_rate": 0.0, "total_count": 0}

        return {
            "avg_quality": round(row["avg_quality"], 3),
            "success_rate": round(row["success_count"] / row["total_count"], 3),
            "total_count": row["total_count"],
        }

    def get_agent_effectiveness(self, agent_id: str) -> dict:
        """Get effectiveness statistics for a specific agent.

        Looks up agent_id in the JSON context field.

        Returns:
            Dict with avg_quality, success_rate, total_count.
        """
        # SQLite JSON extraction: context field stores {"agent_id": "..."}
        row = self.conn.execute(
            """SELECT
                COUNT(*) as total_count,
                AVG(quality_score) as avg_quality,
                SUM(CASE WHEN quality_score >= 0.4 THEN 1 ELSE 0 END) as success_count
               FROM outcomes
               WHERE json_extract(context, '$.agent_id') = ?""",
            (agent_id,),
        ).fetchone()

        if not row or row["total_count"] == 0:
            return {"avg_quality": 0.0, "success_rate": 0.0, "total_count": 0}

        return {
            "avg_quality": round(row["avg_quality"], 3),
            "success_rate": round(row["success_count"] / row["total_count"], 3),
            "total_count": row["total_count"],
        }

    # ── Statistics ────────────────────────────────────────────────

    def stats(self) -> dict:
        """Overall outcome registry statistics."""
        total = self.conn.execute(
            "SELECT COUNT(*) as c FROM outcomes"
        ).fetchone()

        avg_quality = self.conn.execute(
            "SELECT AVG(quality_score) as a FROM outcomes"
        ).fetchone()

        success_count = self.conn.execute(
            "SELECT COUNT(*) as c FROM outcomes WHERE quality_score >= 0.4"
        ).fetchone()

        by_type = self.conn.execute(
            """SELECT action_type,
                      COUNT(*) as cnt,
                      AVG(quality_score) as avg_q,
                      SUM(CASE WHEN quality_score >= 0.4 THEN 1 ELSE 0 END) as successes
               FROM outcomes GROUP BY action_type"""
        ).fetchall()

        total_count = total["c"] if total else 0

        return {
            "total_outcomes": total_count,
            "avg_quality": round(avg_quality["a"] or 0, 3) if avg_quality and avg_quality["a"] else 0.0,
            "overall_success_rate": round(
                (success_count["c"] / total_count), 3
            ) if total_count > 0 else 0.0,
            "by_action_type": {
                r["action_type"]: {
                    "count": r["cnt"],
                    "avg_quality": round(r["avg_q"] or 0, 3),
                    "success_rate": round(
                        (r["successes"] or 0) / r["cnt"], 3
                    ) if r["cnt"] > 0 else 0.0,
                }
                for r in by_type
            },
        }

    # ── Internal ──────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        """Convert a database row to a plain dict."""
        d = dict(row)
        try:
            d["context"] = json.loads(d.get("context", "{}"))
        except (json.JSONDecodeError, TypeError):
            d["context"] = {}
        return d
