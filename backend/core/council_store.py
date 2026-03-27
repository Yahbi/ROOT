"""
Council Store — Persists council debate records with individual agent perspectives.

Stores the full reasoning from each agent in a MiRo council debate,
enabling deep-dive analysis and historical review of how different
agents assessed the same topic.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.council_store")

COUNCIL_DB = ROOT_DIR / "data" / "councils.db"


@dataclass(frozen=True)
class CouncilPerspective:
    """Immutable record of one agent's perspective in a debate."""

    agent_id: str
    agent_role: str
    stance: str  # bullish, bearish, neutral
    reasoning: str
    confidence: float
    key_points: list[str]


@dataclass(frozen=True)
class CouncilDebateRecord:
    """Immutable record of a full council debate."""

    id: str
    topic: str
    symbols: str
    perspectives: list[CouncilPerspective]
    consensus: str
    verdict: str
    created_at: str


class CouncilStore:
    """Persists council debate records in SQLite."""

    def __init__(self) -> None:
        self._conn: Optional[sqlite3.Connection] = None

    def start(self) -> None:
        """Initialize the council store database."""
        COUNCIL_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(COUNCIL_DB), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        logger.info("CouncilStore started (db=%s)", COUNCIL_DB)

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("CouncilStore not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS council_debates (
                id TEXT PRIMARY KEY,
                topic TEXT NOT NULL,
                symbols TEXT NOT NULL DEFAULT '',
                consensus TEXT NOT NULL DEFAULT '',
                verdict TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS council_perspectives (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                debate_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                agent_role TEXT NOT NULL DEFAULT '',
                stance TEXT NOT NULL DEFAULT 'neutral',
                reasoning TEXT NOT NULL DEFAULT '',
                confidence REAL NOT NULL DEFAULT 0.5,
                key_points TEXT NOT NULL DEFAULT '[]',
                FOREIGN KEY (debate_id) REFERENCES council_debates(id)
            );

            CREATE INDEX IF NOT EXISTS idx_debates_created
                ON council_debates(created_at);
            CREATE INDEX IF NOT EXISTS idx_perspectives_debate
                ON council_perspectives(debate_id);
        """)

    def record_debate(
        self,
        topic: str,
        symbols: str,
        perspectives: list[CouncilPerspective],
        consensus: str,
        verdict: str,
    ) -> str:
        """Store a complete council debate. Returns debate ID."""
        debate_id = f"council_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """INSERT INTO council_debates (id, topic, symbols, consensus, verdict, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (debate_id, topic, symbols, consensus, verdict[:2000], now),
        )

        for p in perspectives:
            key_points_json = json.dumps(p.key_points[:10])
            self.conn.execute(
                """INSERT INTO council_perspectives
                   (debate_id, agent_id, agent_role, stance, reasoning, confidence, key_points)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    debate_id,
                    p.agent_id,
                    p.agent_role,
                    p.stance,
                    p.reasoning[:2000],
                    max(0.0, min(1.0, p.confidence)),
                    key_points_json,
                ),
            )

        self.conn.commit()
        logger.info("Recorded council debate %s: %s (%d perspectives)",
                     debate_id, topic[:50], len(perspectives))
        return debate_id

    def get_debate(self, debate_id: str) -> Optional[CouncilDebateRecord]:
        """Retrieve a full debate record with all perspectives."""
        row = self.conn.execute(
            "SELECT * FROM council_debates WHERE id = ?", (debate_id,),
        ).fetchone()
        if not row:
            return None

        persp_rows = self.conn.execute(
            "SELECT * FROM council_perspectives WHERE debate_id = ? ORDER BY agent_id",
            (debate_id,),
        ).fetchall()

        perspectives = [
            CouncilPerspective(
                agent_id=p["agent_id"],
                agent_role=p["agent_role"],
                stance=p["stance"],
                reasoning=p["reasoning"],
                confidence=p["confidence"],
                key_points=json.loads(p["key_points"]),
            )
            for p in persp_rows
        ]

        return CouncilDebateRecord(
            id=row["id"],
            topic=row["topic"],
            symbols=row["symbols"],
            perspectives=perspectives,
            consensus=row["consensus"],
            verdict=row["verdict"],
            created_at=row["created_at"],
        )

    def list_debates(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent debates (summaries only)."""
        rows = self.conn.execute(
            """SELECT d.id, d.topic, d.symbols, d.verdict, d.created_at,
                      COUNT(p.id) as perspective_count
               FROM council_debates d
               LEFT JOIN council_perspectives p ON d.id = p.debate_id
               GROUP BY d.id
               ORDER BY d.created_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()

        return [
            {
                "id": r["id"],
                "topic": r["topic"],
                "symbols": r["symbols"],
                "verdict": r["verdict"][:200],
                "perspective_count": r["perspective_count"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def stats(self) -> dict[str, Any]:
        """Return council debate statistics."""
        total = self.conn.execute(
            "SELECT COUNT(*) as c FROM council_debates",
        ).fetchone()
        perspectives = self.conn.execute(
            "SELECT COUNT(*) as c FROM council_perspectives",
        ).fetchone()

        stance_counts = self.conn.execute(
            """SELECT stance, COUNT(*) as c FROM council_perspectives
               GROUP BY stance""",
        ).fetchall()

        return {
            "total_debates": total["c"] if total else 0,
            "total_perspectives": perspectives["c"] if perspectives else 0,
            "stance_distribution": {
                r["stance"]: r["c"] for r in stance_counts
            },
        }
