"""
Digest Engine — daily/weekly reporting and summaries for ROOT.

Generates:
- Daily digest: what ROOT did while Yohan was away
- Weekly learning summary: what ROOT got better at
- Alert digest: things needing Yohan's attention
- Portfolio summary: trading activity and P&L

Reports are stored in memory and can be retrieved via API.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.digest")

DIGEST_DB = ROOT_DIR / "data" / "digests.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Digest:
    """An immutable digest/report."""
    id: str
    digest_type: str  # daily | weekly | alert | portfolio | custom
    title: str
    content: str
    highlights: tuple[str, ...] = ()
    metrics: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso)
    period_start: Optional[str] = None
    period_end: Optional[str] = None


class DigestEngine:
    """Generates and stores periodic reports."""

    def __init__(
        self,
        memory=None,
        learning=None,
        goal_engine=None,
        task_queue=None,
        user_patterns=None,
        hedge_fund=None,
        llm=None,
    ) -> None:
        self._memory = memory
        self._learning = learning
        self._goal_engine = goal_engine
        self._task_queue = task_queue
        self._user_patterns = user_patterns
        self._hedge_fund = hedge_fund
        self._llm = llm
        self._conn: Optional[sqlite3.Connection] = None

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        DIGEST_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(DIGEST_DB), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        logger.info("DigestEngine started (db=%s)", DIGEST_DB)

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
        if self._conn is None:
            raise RuntimeError("DigestEngine not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS digests (
                id TEXT PRIMARY KEY,
                digest_type TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                highlights TEXT DEFAULT '[]',
                metrics TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                period_start TEXT,
                period_end TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_digest_type ON digests(digest_type);
            CREATE INDEX IF NOT EXISTS idx_digest_created ON digests(created_at DESC);
        """)

    # ── Digest Generation ────────────────────────────────────────

    async def generate_daily(self) -> Digest:
        """Generate a daily activity digest."""
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        period_start = yesterday.isoformat()
        period_end = now.isoformat()

        sections: list[str] = []
        highlights: list[str] = []
        metrics: dict[str, Any] = {}

        # 1. Learning engine insights
        if self._learning:
            stats = self._learning.stats()
            insights = self._learning.get_insights()
            metrics["interactions"] = stats.get("interactions_tracked", 0)
            metrics["agent_outcomes"] = stats.get("agent_outcomes_tracked", 0)
            metrics["avg_quality"] = stats.get("avg_interaction_quality", 0)

            quality_trend = insights.get("quality_trend", {})
            if quality_trend:
                direction = quality_trend.get("direction", "stable")
                sections.append(f"**Quality Trend**: {direction} (recent: {quality_trend.get('recent_avg', 0):.2f})")
                if direction == "improving":
                    highlights.append("Response quality is improving")

        # 2. Goal progress
        if self._goal_engine:
            goal_stats = self._goal_engine.stats()
            active_goals = goal_stats.get("by_status", {}).get("active", 0)
            avg_progress = goal_stats.get("avg_active_progress", 0)
            metrics["active_goals"] = active_goals
            metrics["avg_goal_progress"] = avg_progress
            sections.append(f"**Goals**: {active_goals} active, {avg_progress:.0%} avg progress")

        # 3. Task queue activity
        if self._task_queue:
            tq_stats = self._task_queue.stats()
            completed = tq_stats.get("by_status", {}).get("completed", 0)
            pending = tq_stats.get("by_status", {}).get("pending", 0)
            metrics["tasks_completed"] = completed
            metrics["tasks_pending"] = pending
            sections.append(f"**Tasks**: {completed} completed, {pending} pending")
            if completed > 5:
                highlights.append(f"Completed {completed} tasks autonomously")

        # 4. Memory stats
        if self._memory:
            mem_count = self._memory.count()
            metrics["memories"] = mem_count
            sections.append(f"**Memory**: {mem_count} entries")

        # 5. User patterns
        if self._user_patterns:
            pattern_stats = self._user_patterns.stats()
            metrics["patterns_detected"] = pattern_stats.get("patterns_detected", 0)
            anticipation = pattern_stats.get("anticipation_candidates", 0)
            if anticipation > 0:
                highlights.append(f"Identified {anticipation} things to anticipate")

        # 6. Trading summary
        if self._hedge_fund:
            try:
                portfolio = self._hedge_fund.get_portfolio_summary()
                if portfolio:
                    metrics["portfolio"] = portfolio
                    sections.append(f"**Portfolio**: {json.dumps(portfolio)[:200]}")
            except Exception as exc:
                logger.warning("Failed to fetch portfolio summary for digest: %s", exc)

        # Synthesize with LLM if available
        raw_content = "\n\n".join(sections) if sections else "No activity recorded."

        if self._llm and sections:
            try:
                synthesis = await self._llm.complete(
                    system=(
                        "You are ROOT, Yohan's AI system. Write a concise daily digest. "
                        "Use bullet points. Highlight wins and issues. Be brief but informative."
                    ),
                    messages=[{"role": "user", "content": (
                        f"Generate my daily digest from this data:\n\n{raw_content}\n\n"
                        f"Highlights so far: {', '.join(highlights) if highlights else 'None'}\n\n"
                        "Format as a brief, scannable report."
                    )}],
                    model_tier="fast",
                    max_tokens=600,
                )
                content = synthesis.strip()
            except Exception as exc:
                logger.warning("Failed to synthesize daily digest with LLM: %s", exc)
                content = raw_content
        else:
            content = raw_content

        title = f"Daily Digest — {now.strftime('%Y-%m-%d')}"
        digest = Digest(
            id=f"digest_{uuid.uuid4().hex[:12]}",
            digest_type="daily",
            title=title,
            content=content,
            highlights=tuple(highlights),
            metrics=metrics,
            period_start=period_start,
            period_end=period_end,
        )

        self._store_digest(digest)
        return digest

    async def generate_weekly(self) -> Digest:
        """Generate a weekly learning and progress summary."""
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)

        sections: list[str] = []
        highlights: list[str] = []
        metrics: dict[str, Any] = {}

        # Experiment learning stats
        if self._learning:
            exp_stats = self._learning.get_experiment_stats()
            if exp_stats:
                for area, data in exp_stats.items():
                    sections.append(
                        f"**{area}**: {data['total']} experiments, "
                        f"{data['success_rate']:.0%} success rate"
                    )
                metrics["experiment_stats"] = exp_stats

        # Goal completion count
        if self._goal_engine:
            goals = self._goal_engine.get_all_goals(limit=100)
            completed_this_week = sum(
                1 for g in goals
                if g.status == "completed" and g.completed_at
                and g.completed_at >= week_ago.isoformat()
            )
            metrics["goals_completed_this_week"] = completed_this_week
            if completed_this_week > 0:
                highlights.append(f"Completed {completed_this_week} goals this week")

        # Recent daily digests summary
        recent_dailies = self.get_digests("daily", limit=7)
        if recent_dailies:
            all_daily_highlights = []
            for d in recent_dailies:
                all_daily_highlights.extend(d.highlights)
            if all_daily_highlights:
                sections.append("**Weekly Highlights**: " + "; ".join(all_daily_highlights[:10]))

        raw_content = "\n\n".join(sections) if sections else "Insufficient data for weekly summary."

        if self._llm and sections:
            try:
                synthesis = await self._llm.complete(
                    system="Write a concise weekly progress summary. Focus on learning and growth.",
                    messages=[{"role": "user", "content": raw_content}],
                    model_tier="fast", max_tokens=500,
                )
                content = synthesis.strip()
            except Exception as exc:
                logger.warning("Failed to synthesize weekly digest with LLM: %s", exc)
                content = raw_content
        else:
            content = raw_content

        digest = Digest(
            id=f"digest_{uuid.uuid4().hex[:12]}",
            digest_type="weekly",
            title=f"Weekly Summary — {now.strftime('%Y-W%W')}",
            content=content,
            highlights=tuple(highlights),
            metrics=metrics,
            period_start=week_ago.isoformat(),
            period_end=now.isoformat(),
        )
        self._store_digest(digest)
        return digest

    async def generate_alert_digest(self, alerts: list[str]) -> Digest:
        """Generate an alert digest for things needing attention."""
        content = "**Alerts requiring attention:**\n\n" + "\n".join(f"- {a}" for a in alerts)
        digest = Digest(
            id=f"digest_{uuid.uuid4().hex[:12]}",
            digest_type="alert",
            title=f"Alert Digest — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}",
            content=content,
            highlights=tuple(alerts[:5]),
        )
        self._store_digest(digest)
        return digest

    # ── Storage ──────────────────────────────────────────────────

    def _store_digest(self, digest: Digest) -> None:
        self.conn.execute(
            """INSERT INTO digests
               (id, digest_type, title, content, highlights, metrics,
                created_at, period_start, period_end)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (digest.id, digest.digest_type, digest.title, digest.content,
             json.dumps(list(digest.highlights)), json.dumps(digest.metrics),
             digest.created_at, digest.period_start, digest.period_end),
        )
        self.conn.commit()

        # Trim old digests (keep last 100)
        self.conn.execute(
            """DELETE FROM digests WHERE id NOT IN (
                SELECT id FROM digests ORDER BY created_at DESC LIMIT 100
            )"""
        )
        self.conn.commit()

    # ── Queries ──────────────────────────────────────────────────

    def get_digests(self, digest_type: Optional[str] = None, limit: int = 10) -> list[Digest]:
        if digest_type:
            rows = self.conn.execute(
                "SELECT * FROM digests WHERE digest_type = ? ORDER BY created_at DESC LIMIT ?",
                (digest_type, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM digests ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row_to_digest(r) for r in rows]

    def get_latest(self, digest_type: str = "daily") -> Optional[Digest]:
        row = self.conn.execute(
            "SELECT * FROM digests WHERE digest_type = ? ORDER BY created_at DESC LIMIT 1",
            (digest_type,),
        ).fetchone()
        return self._row_to_digest(row) if row else None

    def stats(self) -> dict[str, Any]:
        rows = self.conn.execute(
            "SELECT digest_type, COUNT(*) as cnt FROM digests GROUP BY digest_type"
        ).fetchall()
        return {
            "total_digests": sum(r["cnt"] for r in rows),
            "by_type": {r["digest_type"]: r["cnt"] for r in rows},
        }

    def _row_to_digest(self, row: sqlite3.Row) -> Digest:
        highlights = ()
        metrics = {}
        try:
            highlights = tuple(json.loads(row["highlights"] or "[]"))
        except (json.JSONDecodeError, TypeError):
            logger.debug("(json.JSONDecodeError, TypeError) suppressed", exc_info=True)
        try:
            metrics = json.loads(row["metrics"] or "{}")
        except (json.JSONDecodeError, TypeError):
            logger.debug("(json.JSONDecodeError, TypeError) suppressed", exc_info=True)
        return Digest(
            id=row["id"], digest_type=row["digest_type"],
            title=row["title"], content=row["content"],
            highlights=highlights, metrics=metrics,
            created_at=row["created_at"],
            period_start=row["period_start"],
            period_end=row["period_end"],
        )
