"""
Experience Memory — layered memory system for the ASTRA-ROOT civilization.

Three memory layers:
- Short-term: Active task context (in-memory, auto-expires)
- Long-term: Persistent knowledge base (SQLite, existing MemoryEngine)
- Experience: Success patterns, failures, strategies, lessons learned (SQLite)

Experience memory is the system's wisdom — it learns from outcomes
and informs future decisions.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from backend.config import DATA_DIR

EXPERIENCE_DB = DATA_DIR / "experience.db"


class ExperienceType(str, Enum):
    SUCCESS = "success"          # What worked
    FAILURE = "failure"          # What didn't work (and why)
    STRATEGY = "strategy"        # Reusable strategy pattern
    LESSON = "lesson"            # Generalized lesson learned


@dataclass(frozen=True)
class Experience:
    """Immutable experience record."""
    id: str
    experience_type: ExperienceType
    domain: str                  # e.g., "trading", "automation", "research"
    title: str
    description: str
    context: dict[str, Any] = field(default_factory=dict)
    outcome: Optional[str] = None
    confidence: float = 1.0      # How reliable this lesson is (0-1)
    times_applied: int = 0       # How often this experience was used
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ShortTermEntry:
    """In-memory short-term context entry."""
    id: str
    content: str
    task_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    ttl_seconds: int = 3600      # Auto-expire after 1 hour


class ExperienceMemory:
    """Three-layer memory system: short-term, long-term (via MemoryEngine), experience."""

    MAX_SHORT_TERM = 100

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = str(db_path or EXPERIENCE_DB)
        self._conn: Optional[sqlite3.Connection] = None
        self._short_term: dict[str, ShortTermEntry] = {}

    # ── Lifecycle ──────────────────────────────────────────────

    def start(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("ExperienceMemory not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS experiences (
                id TEXT PRIMARY KEY,
                experience_type TEXT NOT NULL,
                domain TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                context TEXT DEFAULT '{}',
                outcome TEXT,
                confidence REAL DEFAULT 1.0,
                times_applied INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                tags TEXT DEFAULT ''
            );

            CREATE INDEX IF NOT EXISTS idx_exp_type ON experiences(experience_type);
            CREATE INDEX IF NOT EXISTS idx_exp_domain ON experiences(domain);
            CREATE INDEX IF NOT EXISTS idx_exp_confidence ON experiences(confidence);
        """)

    # ── Short-Term Memory ──────────────────────────────────────

    def store_short_term(self, content: str, task_id: Optional[str] = None,
                         ttl_seconds: int = 3600) -> ShortTermEntry:
        """Store active task context in short-term memory."""
        entry = ShortTermEntry(
            id=f"stm_{uuid.uuid4().hex[:12]}",
            content=content,
            task_id=task_id,
            ttl_seconds=ttl_seconds,
        )
        self._short_term[entry.id] = entry
        self._enforce_short_term_limit()
        return entry

    def get_short_term(self, task_id: Optional[str] = None) -> list[ShortTermEntry]:
        """Get active short-term entries, optionally filtered by task."""
        now = datetime.now(timezone.utc)
        active: list[ShortTermEntry] = []
        expired: list[str] = []

        for entry_id, entry in self._short_term.items():
            created = datetime.fromisoformat(entry.created_at)
            age = (now - created).total_seconds()
            if age > entry.ttl_seconds:
                expired.append(entry_id)
            elif task_id is None or entry.task_id == task_id:
                active.append(entry)

        for eid in expired:
            self._short_term.pop(eid, None)

        return active

    def clear_short_term(self, task_id: Optional[str] = None) -> int:
        """Clear short-term entries. If task_id given, only clear that task's context."""
        if task_id is None:
            count = len(self._short_term)
            self._short_term.clear()
            return count
        to_remove = [k for k, v in self._short_term.items() if v.task_id == task_id]
        for k in to_remove:
            self._short_term.pop(k)
        return len(to_remove)

    def _enforce_short_term_limit(self) -> None:
        if len(self._short_term) <= self.MAX_SHORT_TERM:
            return
        sorted_entries = sorted(self._short_term.values(),
                                key=lambda e: e.created_at)
        excess = len(self._short_term) - self.MAX_SHORT_TERM
        for entry in sorted_entries[:excess]:
            self._short_term.pop(entry.id, None)

    # ── Experience Memory (Long-Lived Wisdom) ──────────────────

    def record_experience(
        self,
        experience_type: str,
        domain: str,
        title: str,
        description: str,
        context: Optional[dict] = None,
        outcome: Optional[str] = None,
        confidence: float = 1.0,
        tags: Optional[list[str]] = None,
    ) -> Experience:
        """Record a new experience (success, failure, strategy, or lesson)."""
        exp_type = ExperienceType(experience_type)
        if not 0.0 <= confidence <= 1.0:
            raise ValueError("Confidence must be between 0.0 and 1.0")

        exp_id = f"exp_{uuid.uuid4().hex[:12]}"
        import json
        ctx_str = json.dumps(context or {})
        tags_str = ",".join(tags or [])
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """INSERT INTO experiences
               (id, experience_type, domain, title, description, context,
                outcome, confidence, times_applied, created_at, tags)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?)""",
            (exp_id, exp_type.value, domain, title, description,
             ctx_str, outcome, confidence, now, tags_str),
        )
        self.conn.commit()

        return Experience(
            id=exp_id, experience_type=exp_type, domain=domain,
            title=title, description=description,
            context=context or {}, outcome=outcome,
            confidence=confidence, created_at=now,
            tags=tags or [],
        )

    def record_success(self, domain: str, title: str, description: str,
                        **kwargs) -> Experience:
        """Convenience: record a success pattern."""
        return self.record_experience("success", domain, title, description, **kwargs)

    def record_failure(self, domain: str, title: str, description: str,
                        **kwargs) -> Experience:
        """Convenience: record a failure with lessons."""
        return self.record_experience("failure", domain, title, description, **kwargs)

    def record_strategy(self, domain: str, title: str, description: str,
                         **kwargs) -> Experience:
        """Convenience: record a reusable strategy."""
        return self.record_experience("strategy", domain, title, description, **kwargs)

    def record_lesson(self, domain: str, title: str, description: str,
                       **kwargs) -> Experience:
        """Convenience: record a generalized lesson."""
        return self.record_experience("lesson", domain, title, description, **kwargs)

    def get_experiences(
        self,
        domain: Optional[str] = None,
        experience_type: Optional[str] = None,
        min_confidence: float = 0.0,
        limit: int = 20,
    ) -> list[Experience]:
        """Query experiences with optional filters."""
        sql = "SELECT * FROM experiences WHERE confidence >= ?"
        params: list[Any] = [min_confidence]

        if domain:
            sql += " AND domain = ?"
            params.append(domain)
        if experience_type:
            sql += " AND experience_type = ?"
            params.append(experience_type)

        sql += " ORDER BY confidence DESC, times_applied DESC LIMIT ?"
        params.append(limit)

        rows = self.conn.execute(sql, params).fetchall()
        return [self._row_to_experience(r) for r in rows]

    def get_successes(self, domain: Optional[str] = None, limit: int = 10) -> list[Experience]:
        return self.get_experiences(domain=domain, experience_type="success", limit=limit)

    def get_failures(self, domain: Optional[str] = None, limit: int = 10) -> list[Experience]:
        return self.get_experiences(domain=domain, experience_type="failure", limit=limit)

    def get_strategies(self, domain: Optional[str] = None, limit: int = 10) -> list[Experience]:
        return self.get_experiences(domain=domain, experience_type="strategy", limit=limit)

    def get_lessons(self, domain: Optional[str] = None, limit: int = 10) -> list[Experience]:
        return self.get_experiences(domain=domain, experience_type="lesson", limit=limit)

    def apply_experience(self, experience_id: str) -> None:
        """Mark an experience as applied (increment usage counter)."""
        self.conn.execute(
            "UPDATE experiences SET times_applied = times_applied + 1 WHERE id = ?",
            (experience_id,),
        )
        self.conn.commit()

    def strengthen(self, experience_id: str, boost: float = 0.05) -> None:
        """Strengthen an experience's confidence."""
        self.conn.execute(
            "UPDATE experiences SET confidence = MIN(1.0, confidence + ?) WHERE id = ?",
            (boost, experience_id),
        )
        self.conn.commit()

    def weaken(self, experience_id: str, penalty: float = 0.1) -> None:
        """Weaken an experience's confidence."""
        self.conn.execute(
            "UPDATE experiences SET confidence = MAX(0.0, confidence - ?) WHERE id = ?",
            (penalty, experience_id),
        )
        self.conn.commit()

    def search_experiences(self, query: str, limit: int = 10) -> list[Experience]:
        """Simple keyword search across experiences."""
        pattern = f"%{query}%"
        rows = self.conn.execute(
            """SELECT * FROM experiences
               WHERE title LIKE ? OR description LIKE ? OR tags LIKE ?
               ORDER BY confidence DESC LIMIT ?""",
            (pattern, pattern, pattern, limit),
        ).fetchall()
        return [self._row_to_experience(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        """Experience memory statistics."""
        rows = self.conn.execute(
            """SELECT experience_type, COUNT(*) as cnt, AVG(confidence) as avg_conf
               FROM experiences GROUP BY experience_type"""
        ).fetchall()
        total = self.conn.execute("SELECT COUNT(*) as c FROM experiences").fetchone()
        return {
            "total_experiences": total["c"] if total else 0,
            "short_term_entries": len(self._short_term),
            "by_type": {
                r["experience_type"]: {
                    "count": r["cnt"],
                    "avg_confidence": round(r["avg_conf"], 3),
                }
                for r in rows
            },
        }

    @staticmethod
    def _row_to_experience(row: sqlite3.Row) -> Experience:
        import json
        tags = [t.strip() for t in row["tags"].split(",") if t.strip()]
        try:
            context = json.loads(row["context"]) if row["context"] else {}
        except json.JSONDecodeError:
            context = {}
        return Experience(
            id=row["id"],
            experience_type=ExperienceType(row["experience_type"]),
            domain=row["domain"],
            title=row["title"],
            description=row["description"],
            context=context,
            outcome=row["outcome"],
            confidence=row["confidence"],
            times_applied=row["times_applied"],
            created_at=row["created_at"],
            tags=tags,
        )
