"""
Episodic Trade Memory — per-trade episodic logging with lesson extraction.

Every trade is stored as a structured episode:
(market_id, thesis, ev_calc, action, outcome, brier_error, lesson)

The Meta-Agent uses this for:
- Nightly reflection (what worked, what didn't)
- Pattern recognition (which market conditions → which outcomes)
- Calibration improvement (Brier score tracking per confidence bucket)
- Strategy evolution (kill losing patterns, amplify winning ones)

Persisted in SQLite for crash recovery. Integrates with ROOT's
ExperienceMemory for cross-system wisdom sharing.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.episodic_trade_memory")

EPISODIC_DB = ROOT_DIR / "data" / "episodic_trades.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data Models ──────────────────────────────────────────────

@dataclass(frozen=True)
class TradeEpisode:
    """A complete trade episode with full context."""
    id: str
    market_id: str         # Symbol or market identifier
    thesis: str            # Why we entered
    thesis_signal: str     # bullish | bearish | neutral
    thesis_confidence: float  # 0-100
    ev_calculation: dict   # {true_prob, market_price, edge, kelly_size}
    action: str            # buy | sell | short | cover | hold
    entry_price: float
    exit_price: Optional[float] = None
    quantity: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    brier_error: Optional[float] = None  # (predicted_prob - actual_outcome)^2
    outcome: str = "pending"  # pending | win | loss | breakeven
    lesson: str = ""       # Extracted lesson from this trade
    strategy: str = "unknown"
    regime: str = "unknown"  # Market regime at time of trade
    agents_consulted: list[str] = field(default_factory=list)
    debate_id: Optional[str] = None
    thesis_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    duration_hours: Optional[float] = None
    created_at: str = field(default_factory=_now_iso)
    closed_at: Optional[str] = None


# ── Episodic Trade Memory ────────────────────────────────────

class EpisodicTradeMemory:
    """Persistent episodic memory for all trades."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or EPISODIC_DB
        self._conn: Optional[sqlite3.Connection] = None

    def start(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._create_tables()
        logger.info("Episodic trade memory: started (db=%s)", self._db_path)

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _ensure_started(self) -> None:
        """Auto-start if not already started."""
        if self._conn is None:
            self.start()

    def _create_tables(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS trade_episodes (
                id TEXT PRIMARY KEY,
                market_id TEXT NOT NULL,
                thesis TEXT,
                thesis_signal TEXT,
                thesis_confidence REAL,
                ev_calculation TEXT,
                action TEXT,
                entry_price REAL,
                exit_price REAL,
                quantity REAL,
                pnl REAL DEFAULT 0,
                pnl_pct REAL DEFAULT 0,
                brier_error REAL,
                outcome TEXT DEFAULT 'pending',
                lesson TEXT DEFAULT '',
                strategy TEXT DEFAULT 'unknown',
                regime TEXT DEFAULT 'unknown',
                agents_consulted TEXT DEFAULT '[]',
                debate_id TEXT,
                thesis_id TEXT,
                tags TEXT DEFAULT '[]',
                duration_hours REAL,
                created_at TEXT,
                closed_at TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_ep_market ON trade_episodes(market_id);
            CREATE INDEX IF NOT EXISTS idx_ep_outcome ON trade_episodes(outcome);
            CREATE INDEX IF NOT EXISTS idx_ep_strategy ON trade_episodes(strategy);
            CREATE INDEX IF NOT EXISTS idx_ep_created ON trade_episodes(created_at);
        """)

    def record_entry(
        self,
        market_id: str,
        action: str,
        entry_price: float,
        quantity: float = 0.0,
        thesis: str = "",
        thesis_signal: str = "neutral",
        thesis_confidence: float = 50.0,
        ev_calculation: Optional[dict] = None,
        strategy: str = "unknown",
        regime: str = "unknown",
        agents_consulted: Optional[list[str]] = None,
        debate_id: Optional[str] = None,
        thesis_id: Optional[str] = None,
        tags: Optional[list[str]] = None,
    ) -> str:
        """Record a new trade entry. Returns episode ID."""
        self._ensure_started()
        episode_id = f"ep-{uuid.uuid4().hex[:10]}"

        self._conn.execute(
            """INSERT INTO trade_episodes
               (id, market_id, thesis, thesis_signal, thesis_confidence,
                ev_calculation, action, entry_price, quantity, strategy,
                regime, agents_consulted, debate_id, thesis_id, tags, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                episode_id, market_id, thesis, thesis_signal, thesis_confidence,
                json.dumps(ev_calculation or {}), action, entry_price, quantity,
                strategy, regime,
                json.dumps(agents_consulted or []),
                debate_id, thesis_id,
                json.dumps(tags or []),
                _now_iso(),
            ),
        )
        self._conn.commit()
        return episode_id

    def record_exit(
        self,
        episode_id: str,
        exit_price: float,
        pnl: float = 0.0,
        pnl_pct: float = 0.0,
        brier_error: Optional[float] = None,
        lesson: str = "",
    ) -> None:
        """Record trade exit with outcome."""
        self._ensure_started()
        if pnl > 0:
            outcome = "win"
        elif pnl < 0:
            outcome = "loss"
        else:
            outcome = "breakeven"

        # Calculate duration
        row = self._conn.execute(
            "SELECT created_at FROM trade_episodes WHERE id = ?", (episode_id,)
        ).fetchone()
        duration_hours = None
        if row:
            try:
                created = datetime.fromisoformat(row[0])
                now = datetime.now(timezone.utc)
                duration_hours = (now - created).total_seconds() / 3600
            except Exception:
                pass

        self._conn.execute(
            """UPDATE trade_episodes
               SET exit_price = ?, pnl = ?, pnl_pct = ?, brier_error = ?,
                   outcome = ?, lesson = ?, duration_hours = ?, closed_at = ?
               WHERE id = ?""",
            (exit_price, pnl, pnl_pct, brier_error, outcome, lesson,
             duration_hours, _now_iso(), episode_id),
        )
        self._conn.commit()

    def extract_lesson(self, episode_id: str, llm=None) -> str:
        """Extract a lesson from a completed trade (LLM or heuristic)."""
        self._ensure_started()
        episode = self.get_episode(episode_id)
        if not episode:
            return ""

        # Heuristic lesson extraction (no LLM needed)
        parts = []

        if episode["outcome"] == "win":
            parts.append(f"Winning trade on {episode['market_id']}.")
            if episode["thesis_confidence"] > 80:
                parts.append("High confidence thesis was correct.")
            if episode["strategy"] != "unknown":
                parts.append(f"Strategy '{episode['strategy']}' worked in {episode['regime']} regime.")
        elif episode["outcome"] == "loss":
            parts.append(f"Losing trade on {episode['market_id']}.")
            if episode["thesis_confidence"] > 80:
                parts.append("High confidence thesis was WRONG — potential overconfidence.")
            if episode.get("brier_error") and episode["brier_error"] > 0.25:
                parts.append(f"Brier error {episode['brier_error']:.3f} — probability estimate was poor.")
            parts.append(f"Strategy '{episode['strategy']}' failed in {episode['regime']} regime.")

        duration = episode.get("duration_hours")
        if duration and duration < 1:
            parts.append("Very short hold — possible overtrading.")
        elif duration and duration > 168:
            parts.append("Very long hold (>1 week) — review exit timing.")

        lesson = " ".join(parts)

        # Update episode with lesson
        self._conn.execute(
            "UPDATE trade_episodes SET lesson = ? WHERE id = ?",
            (lesson, episode_id),
        )
        self._conn.commit()

        return lesson

    def get_episode(self, episode_id: str) -> Optional[dict]:
        """Retrieve a single episode."""
        self._ensure_started()
        row = self._conn.execute(
            "SELECT * FROM trade_episodes WHERE id = ?", (episode_id,)
        ).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def get_episodes(
        self,
        market_id: Optional[str] = None,
        outcome: Optional[str] = None,
        strategy: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict]:
        """Query episodes with filters."""
        self._ensure_started()
        query = "SELECT * FROM trade_episodes WHERE 1=1"
        params = []

        if market_id:
            query += " AND market_id = ?"
            params.append(market_id)
        if outcome:
            query += " AND outcome = ?"
            params.append(outcome)
        if strategy:
            query += " AND strategy = ?"
            params.append(strategy)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        rows = self._conn.execute(query, params).fetchall()
        return [self._row_to_dict(r) for r in rows]

    def get_lessons(self, limit: int = 20) -> list[dict]:
        """Get recent lessons from completed trades."""
        self._ensure_started()
        rows = self._conn.execute(
            """SELECT id, market_id, outcome, lesson, strategy, regime,
                      thesis_confidence, brier_error, pnl, pnl_pct, created_at
               FROM trade_episodes
               WHERE outcome != 'pending' AND lesson != ''
               ORDER BY closed_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()

        return [
            {
                "id": r[0], "market_id": r[1], "outcome": r[2],
                "lesson": r[3], "strategy": r[4], "regime": r[5],
                "confidence": r[6], "brier_error": r[7],
                "pnl": r[8], "pnl_pct": r[9], "created_at": r[10],
            }
            for r in rows
        ]

    def get_calibration_data(self) -> list[tuple[float, int]]:
        """Get (predicted_confidence, actual_outcome) pairs for Brier scoring."""
        self._ensure_started()
        rows = self._conn.execute(
            """SELECT thesis_confidence, outcome
               FROM trade_episodes
               WHERE outcome IN ('win', 'loss')""",
        ).fetchall()

        return [
            (r[0] / 100.0, 1 if r[1] == "win" else 0)
            for r in rows
        ]

    def get_strategy_stats(self) -> dict[str, dict]:
        """Aggregate stats per strategy."""
        self._ensure_started()
        rows = self._conn.execute(
            """SELECT strategy,
                      COUNT(*) as total,
                      SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
                      SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                      SUM(pnl) as total_pnl,
                      AVG(pnl_pct) as avg_return,
                      AVG(brier_error) as avg_brier
               FROM trade_episodes
               WHERE outcome != 'pending'
               GROUP BY strategy""",
        ).fetchall()

        return {
            r[0]: {
                "total_trades": r[1],
                "wins": r[2],
                "losses": r[3],
                "win_rate": round(r[2] / r[1], 3) if r[1] > 0 else 0,
                "total_pnl": round(r[4] or 0, 2),
                "avg_return_pct": round(r[5] or 0, 2),
                "avg_brier_error": round(r[6] or 0, 4) if r[6] else None,
            }
            for r in rows
        }

    def stats(self) -> dict:
        """Overall episodic memory stats."""
        self._ensure_started()
        row = self._conn.execute(
            """SELECT
                 COUNT(*) as total,
                 SUM(CASE WHEN outcome = 'pending' THEN 1 ELSE 0 END) as pending,
                 SUM(CASE WHEN outcome = 'win' THEN 1 ELSE 0 END) as wins,
                 SUM(CASE WHEN outcome = 'loss' THEN 1 ELSE 0 END) as losses,
                 SUM(pnl) as total_pnl,
                 AVG(CASE WHEN outcome != 'pending' THEN brier_error END) as avg_brier
               FROM trade_episodes""",
        ).fetchone()

        total = row[0] or 0
        wins = row[2] or 0
        losses = row[3] or 0
        resolved = wins + losses

        return {
            "total_episodes": total,
            "pending": row[1] or 0,
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / resolved, 3) if resolved > 0 else 0,
            "total_pnl": round(row[4] or 0, 2),
            "avg_brier_error": round(row[5] or 0, 4) if row[5] else None,
        }

    def _row_to_dict(self, row) -> dict:
        """Convert database row to dict."""
        cols = [
            "id", "market_id", "thesis", "thesis_signal", "thesis_confidence",
            "ev_calculation", "action", "entry_price", "exit_price", "quantity",
            "pnl", "pnl_pct", "brier_error", "outcome", "lesson", "strategy",
            "regime", "agents_consulted", "debate_id", "thesis_id", "tags",
            "duration_hours", "created_at", "closed_at",
        ]
        d = dict(zip(cols, row))
        # Parse JSON fields
        for key in ("ev_calculation", "agents_consulted", "tags"):
            if isinstance(d.get(key), str):
                try:
                    d[key] = json.loads(d[key])
                except json.JSONDecodeError:
                    d[key] = []
        return d
