"""
User Pattern Learning — learns Yohan's habits, preferences, and recurring needs.

Tracks:
- Activity patterns (when active, what topics)
- Request frequency (what gets asked repeatedly)
- Proactive action usefulness (which actions Yohan engages with)
- Response preferences (length, depth, format)
- Anticipation candidates (things ROOT should do before being asked)

All persisted in SQLite for cross-session learning.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.user_patterns")

PATTERNS_DB = ROOT_DIR / "data" / "user_patterns.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class UserPatternEngine:
    """Learns user behavior patterns to anticipate needs."""

    def __init__(self) -> None:
        self._conn: Optional[sqlite3.Connection] = None

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        PATTERNS_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(PATTERNS_DB), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        logger.info("UserPatternEngine started (db=%s)", PATTERNS_DB)

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
            raise RuntimeError("UserPatternEngine not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            -- Every user interaction with timing and topic
            CREATE TABLE IF NOT EXISTS activity_log (
                id TEXT PRIMARY KEY,
                hour_of_day INTEGER NOT NULL,
                day_of_week INTEGER NOT NULL,
                topic TEXT DEFAULT '',
                intent TEXT DEFAULT '',
                message_preview TEXT DEFAULT '',
                agents_used TEXT DEFAULT '',
                response_quality REAL DEFAULT 0.5,
                created_at TEXT NOT NULL
            );

            -- Recurring request patterns (auto-detected)
            CREATE TABLE IF NOT EXISTS recurring_patterns (
                id TEXT PRIMARY KEY,
                pattern_text TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                frequency INTEGER DEFAULT 1,
                avg_interval_hours REAL DEFAULT 0,
                last_seen TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                auto_actionable INTEGER DEFAULT 0,
                suggested_action TEXT
            );

            -- Proactive action engagement tracking
            CREATE TABLE IF NOT EXISTS proactive_engagement (
                id TEXT PRIMARY KEY,
                action_name TEXT NOT NULL,
                was_useful INTEGER DEFAULT 0,
                was_dismissed INTEGER DEFAULT 0,
                was_acted_on INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );

            -- User preferences (learned over time)
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                evidence_count INTEGER DEFAULT 1,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_activity_hour
                ON activity_log(hour_of_day);
            CREATE INDEX IF NOT EXISTS idx_activity_day
                ON activity_log(day_of_week);
            CREATE INDEX IF NOT EXISTS idx_activity_topic
                ON activity_log(topic);
            CREATE INDEX IF NOT EXISTS idx_recurring_freq
                ON recurring_patterns(frequency DESC);
            CREATE INDEX IF NOT EXISTS idx_proactive_action
                ON proactive_engagement(action_name);
        """)

    # ── Activity Tracking ─────────────────────────────────────────

    def record_activity(
        self,
        message: str,
        topic: str = "",
        intent: str = "",
        agents_used: list[str] | None = None,
        response_quality: float = 0.5,
    ) -> None:
        """Record a user interaction for pattern learning."""
        now = datetime.now(timezone.utc)
        self.conn.execute(
            """INSERT INTO activity_log
               (id, hour_of_day, day_of_week, topic, intent, message_preview,
                agents_used, response_quality, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                f"act_{uuid.uuid4().hex[:12]}",
                now.hour,
                now.weekday(),
                topic[:200],
                intent[:200],
                message[:300],
                ",".join(agents_used or []),
                response_quality,
                now.isoformat(),
            ),
        )
        self.conn.commit()

        # Auto-detect recurring patterns
        self._detect_recurring(message, topic)

    def _detect_recurring(self, message: str, topic: str) -> None:
        """Check if this message matches or creates a recurring pattern."""
        # Normalize for comparison
        normalized = message.lower().strip()[:200]
        if len(normalized) < 10:
            return

        # Check existing patterns
        existing = self.conn.execute(
            "SELECT * FROM recurring_patterns WHERE pattern_text = ?",
            (normalized,),
        ).fetchone()

        now = _now_iso()
        if existing:
            # Update frequency
            self.conn.execute(
                """UPDATE recurring_patterns
                   SET frequency = frequency + 1, last_seen = ?
                   WHERE id = ?""",
                (now, existing["id"]),
            )
        else:
            # Check for similar patterns (same topic, similar length)
            similar = self.conn.execute(
                """SELECT * FROM recurring_patterns
                   WHERE category = ? AND ABS(LENGTH(pattern_text) - ?) < 50
                   ORDER BY frequency DESC LIMIT 1""",
                (topic[:200] or "general", len(normalized)),
            ).fetchone()

            if similar and self._text_similarity(normalized, similar["pattern_text"]) > 0.6:
                self.conn.execute(
                    """UPDATE recurring_patterns
                       SET frequency = frequency + 1, last_seen = ?
                       WHERE id = ?""",
                    (now, similar["id"]),
                )
            else:
                self.conn.execute(
                    """INSERT INTO recurring_patterns
                       (id, pattern_text, category, frequency, last_seen, first_seen)
                       VALUES (?, ?, ?, 1, ?, ?)""",
                    (f"rp_{uuid.uuid4().hex[:12]}", normalized,
                     topic[:200] or "general", now, now),
                )
        self.conn.commit()

    @staticmethod
    def _text_similarity(a: str, b: str) -> float:
        """Simple word overlap similarity."""
        words_a = set(a.split())
        words_b = set(b.split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union) if union else 0.0

    # ── Proactive Engagement ─────────────────────────────────────

    def record_proactive_engagement(
        self,
        action_name: str,
        useful: bool = False,
        dismissed: bool = False,
        acted_on: bool = False,
    ) -> None:
        """Track whether a proactive action was useful to the user."""
        self.conn.execute(
            """INSERT INTO proactive_engagement
               (id, action_name, was_useful, was_dismissed, was_acted_on, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (f"pe_{uuid.uuid4().hex[:12]}", action_name,
             1 if useful else 0, 1 if dismissed else 0,
             1 if acted_on else 0, _now_iso()),
        )
        self.conn.commit()

    def get_proactive_usefulness(self) -> dict[str, dict[str, Any]]:
        """Get usefulness scores for each proactive action."""
        rows = self.conn.execute(
            """SELECT action_name,
                      COUNT(*) as total,
                      SUM(was_useful) as useful,
                      SUM(was_dismissed) as dismissed,
                      SUM(was_acted_on) as acted_on
               FROM proactive_engagement
               GROUP BY action_name"""
        ).fetchall()
        return {
            r["action_name"]: {
                "total": r["total"],
                "useful_rate": round((r["useful"] or 0) / r["total"], 3),
                "dismiss_rate": round((r["dismissed"] or 0) / r["total"], 3),
                "action_rate": round((r["acted_on"] or 0) / r["total"], 3),
            }
            for r in rows
        }

    # ── Preference Learning ──────────────────────────────────────

    def learn_preference(self, key: str, value: str, confidence: float = 0.5) -> None:
        """Store or update a learned user preference."""
        existing = self.conn.execute(
            "SELECT * FROM preferences WHERE key = ?", (key,)
        ).fetchone()

        now = _now_iso()
        if existing:
            # Increase confidence with more evidence
            new_confidence = min(1.0, existing["confidence"] + 0.1)
            new_count = existing["evidence_count"] + 1
            self.conn.execute(
                """UPDATE preferences SET value = ?, confidence = ?,
                   evidence_count = ?, updated_at = ? WHERE key = ?""",
                (value[:1000], new_confidence, new_count, now, key),
            )
        else:
            self.conn.execute(
                """INSERT INTO preferences (key, value, confidence, evidence_count, updated_at)
                   VALUES (?, ?, ?, 1, ?)""",
                (key[:200], value[:1000], confidence, now),
            )
        self.conn.commit()

    def get_preference(self, key: str) -> Optional[str]:
        row = self.conn.execute(
            "SELECT value FROM preferences WHERE key = ? AND confidence >= 0.4",
            (key,),
        ).fetchone()
        return row["value"] if row else None

    def get_all_preferences(self) -> dict[str, Any]:
        rows = self.conn.execute(
            "SELECT key, value, confidence FROM preferences ORDER BY confidence DESC"
        ).fetchall()
        return {r["key"]: {"value": r["value"], "confidence": r["confidence"]} for r in rows}

    # ── Pattern Analysis ─────────────────────────────────────────

    def get_active_hours(self) -> dict[int, int]:
        """Get activity distribution by hour of day."""
        rows = self.conn.execute(
            "SELECT hour_of_day, COUNT(*) as cnt FROM activity_log GROUP BY hour_of_day"
        ).fetchall()
        return {r["hour_of_day"]: r["cnt"] for r in rows}

    def get_active_days(self) -> dict[int, int]:
        """Get activity distribution by day of week (0=Monday)."""
        rows = self.conn.execute(
            "SELECT day_of_week, COUNT(*) as cnt FROM activity_log GROUP BY day_of_week"
        ).fetchall()
        return {r["day_of_week"]: r["cnt"] for r in rows}

    def get_top_topics(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get most frequent topics."""
        rows = self.conn.execute(
            """SELECT topic, COUNT(*) as cnt FROM activity_log
               WHERE topic != '' GROUP BY topic ORDER BY cnt DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [{"topic": r["topic"], "count": r["cnt"]} for r in rows]

    def get_recurring_patterns(self, min_frequency: int = 3) -> list[dict[str, Any]]:
        """Get recurring request patterns above threshold."""
        rows = self.conn.execute(
            """SELECT * FROM recurring_patterns
               WHERE frequency >= ?
               ORDER BY frequency DESC LIMIT 20""",
            (min_frequency,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "pattern": r["pattern_text"],
                "category": r["category"],
                "frequency": r["frequency"],
                "auto_actionable": bool(r["auto_actionable"]),
                "suggested_action": r["suggested_action"],
            }
            for r in rows
        ]

    def get_anticipation_candidates(self) -> list[dict[str, Any]]:
        """Identify things ROOT should anticipate doing.

        Based on: high-frequency patterns + time-of-day patterns + proactive usefulness.
        """
        candidates: list[dict[str, Any]] = []

        # High-frequency recurring patterns
        recurring = self.get_recurring_patterns(min_frequency=5)
        for pattern in recurring:
            candidates.append({
                "type": "recurring_request",
                "description": pattern["pattern"][:200],
                "frequency": pattern["frequency"],
                "confidence": min(1.0, pattern["frequency"] / 20),
                "suggested_action": pattern.get("suggested_action") or "auto-execute",
            })

        # Time-based patterns (most active hours)
        active_hours = self.get_active_hours()
        if active_hours:
            peak_hour = max(active_hours, key=active_hours.get)
            candidates.append({
                "type": "time_pattern",
                "description": f"User most active at hour {peak_hour}:00 UTC",
                "frequency": active_hours[peak_hour],
                "confidence": 0.7,
                "suggested_action": f"Prepare briefing before {peak_hour}:00",
            })

        # Proactive actions with high usefulness
        usefulness = self.get_proactive_usefulness()
        for action_name, scores in usefulness.items():
            if scores["useful_rate"] > 0.6 and scores["total"] >= 3:
                candidates.append({
                    "type": "proactive_winner",
                    "description": f"Proactive action '{action_name}' highly valued",
                    "frequency": scores["total"],
                    "confidence": scores["useful_rate"],
                    "suggested_action": f"Increase frequency of {action_name}",
                })

        return sorted(candidates, key=lambda c: c["confidence"], reverse=True)

    # ── Stats ────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        activity_count = self.conn.execute(
            "SELECT COUNT(*) as c FROM activity_log"
        ).fetchone()["c"]
        pattern_count = self.conn.execute(
            "SELECT COUNT(*) as c FROM recurring_patterns"
        ).fetchone()["c"]
        pref_count = self.conn.execute(
            "SELECT COUNT(*) as c FROM preferences"
        ).fetchone()["c"]
        engagement_count = self.conn.execute(
            "SELECT COUNT(*) as c FROM proactive_engagement"
        ).fetchone()["c"]

        return {
            "activities_tracked": activity_count,
            "patterns_detected": pattern_count,
            "preferences_learned": pref_count,
            "proactive_engagements": engagement_count,
            "anticipation_candidates": len(self.get_anticipation_candidates()),
        }
