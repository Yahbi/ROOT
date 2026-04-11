"""
Escalation Engine — confidence-gated autonomous decision making.

Decides when ROOT should act autonomously vs. ask Yohan:
- Tracks confidence for each action type based on past outcomes
- High confidence + positive history → auto-execute
- Low confidence or negative history → escalate to user
- Learns from overrides (user correcting ROOT's decisions)

Works alongside ApprovalChain but at a higher level:
ApprovalChain gates by risk level, EscalationEngine gates by confidence.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.escalation")

ESCALATION_DB = ROOT_DIR / "data" / "escalation.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class EscalationDecision:
    """Result of an escalation check."""
    action_type: str
    should_auto_execute: bool
    confidence: float
    reason: str
    requires_user_input: bool = False


@dataclass(frozen=True)
class EscalationRecord:
    """Record of a past escalation decision and its outcome."""
    id: str
    action_type: str
    description: str
    auto_executed: bool
    was_overridden: bool = False
    override_action: Optional[str] = None
    outcome_positive: Optional[bool] = None
    created_at: str = field(default_factory=_now_iso)


class EscalationEngine:
    """Confidence-gated decision making for autonomous actions."""

    # Confidence thresholds
    AUTO_EXECUTE_THRESHOLD = 0.75  # Above this → auto-execute
    ESCALATE_THRESHOLD = 0.40     # Below this → always ask user
    # Between thresholds → check risk level and recency

    MIN_HISTORY_FOR_AUTO = 5  # Need at least this many past decisions

    def __init__(self) -> None:
        self._conn: Optional[sqlite3.Connection] = None
        self._confidence_cache: dict[str, float] = {}

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        ESCALATION_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(ESCALATION_DB), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        self._load_confidence()
        logger.info("EscalationEngine started (db=%s)", ESCALATION_DB)

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
            raise RuntimeError("EscalationEngine not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS escalation_history (
                id TEXT PRIMARY KEY,
                action_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                auto_executed INTEGER DEFAULT 0,
                was_overridden INTEGER DEFAULT 0,
                override_action TEXT,
                outcome_positive INTEGER,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS confidence_scores (
                action_type TEXT PRIMARY KEY,
                confidence REAL DEFAULT 0.5,
                total_decisions INTEGER DEFAULT 0,
                auto_executed_count INTEGER DEFAULT 0,
                override_count INTEGER DEFAULT 0,
                positive_outcome_count INTEGER DEFAULT 0,
                updated_at TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_escalation_action
                ON escalation_history(action_type);
            CREATE INDEX IF NOT EXISTS idx_escalation_created
                ON escalation_history(created_at DESC);
        """)

    def _load_confidence(self) -> None:
        rows = self.conn.execute("SELECT action_type, confidence FROM confidence_scores").fetchall()
        self._confidence_cache = {r["action_type"]: r["confidence"] for r in rows}

    # ── Core Decision ────────────────────────────────────────────

    def should_auto_execute(
        self,
        action_type: str,
        risk_level: str = "low",
        description: str = "",
    ) -> EscalationDecision:
        """Decide whether to auto-execute or escalate to user.

        Returns an EscalationDecision with the recommendation.
        """
        confidence = self._confidence_cache.get(action_type, 0.5)

        # Get history count for this action type
        history_row = self.conn.execute(
            "SELECT total_decisions FROM confidence_scores WHERE action_type = ?",
            (action_type,),
        ).fetchone()
        history_count = history_row["total_decisions"] if history_row else 0

        # High-risk actions always need more confidence
        risk_multiplier = {
            "low": 1.0,
            "medium": 0.9,
            "high": 0.7,
            "critical": 0.5,
        }.get(risk_level, 0.8)

        effective_confidence = confidence * risk_multiplier

        # Decision logic
        if history_count < self.MIN_HISTORY_FOR_AUTO:
            return EscalationDecision(
                action_type=action_type,
                should_auto_execute=False,
                confidence=confidence,
                reason=f"Insufficient history ({history_count}/{self.MIN_HISTORY_FOR_AUTO})",
                requires_user_input=True,
            )

        if effective_confidence >= self.AUTO_EXECUTE_THRESHOLD:
            return EscalationDecision(
                action_type=action_type,
                should_auto_execute=True,
                confidence=confidence,
                reason=f"High confidence ({confidence:.2f}) with sufficient history",
            )

        if effective_confidence <= self.ESCALATE_THRESHOLD:
            return EscalationDecision(
                action_type=action_type,
                should_auto_execute=False,
                confidence=confidence,
                reason=f"Low confidence ({confidence:.2f}) — escalating to user",
                requires_user_input=True,
            )

        # Middle zone: auto-execute for low risk, escalate for higher
        if risk_level in ("low", "medium"):
            return EscalationDecision(
                action_type=action_type,
                should_auto_execute=True,
                confidence=confidence,
                reason=f"Medium confidence ({confidence:.2f}) but {risk_level} risk — proceeding",
            )

        return EscalationDecision(
            action_type=action_type,
            should_auto_execute=False,
            confidence=confidence,
            reason=f"Medium confidence ({confidence:.2f}) with {risk_level} risk — escalating",
            requires_user_input=True,
        )

    # ── Recording Outcomes ───────────────────────────────────────

    def record_decision(
        self,
        action_type: str,
        description: str,
        auto_executed: bool,
    ) -> str:
        """Record that a decision was made (auto or manual)."""
        record_id = f"esc_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """INSERT INTO escalation_history
               (id, action_type, description, auto_executed, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (record_id, action_type, description[:500],
             1 if auto_executed else 0, _now_iso()),
        )
        self._update_confidence(action_type, auto_executed=auto_executed)
        self.conn.commit()
        return record_id

    def record_override(self, record_id: str, override_action: str) -> None:
        """Record that the user overrode an auto-executed decision."""
        self.conn.execute(
            """UPDATE escalation_history
               SET was_overridden = 1, override_action = ?
               WHERE id = ?""",
            (override_action[:500], record_id),
        )

        # Get the action type to lower confidence
        row = self.conn.execute(
            "SELECT action_type FROM escalation_history WHERE id = ?", (record_id,)
        ).fetchone()
        if row:
            self._update_confidence(row["action_type"], overridden=True)
        self.conn.commit()

    def record_outcome(self, record_id: str, positive: bool) -> None:
        """Record whether a decision's outcome was positive."""
        self.conn.execute(
            "UPDATE escalation_history SET outcome_positive = ? WHERE id = ?",
            (1 if positive else 0, record_id),
        )

        row = self.conn.execute(
            "SELECT action_type FROM escalation_history WHERE id = ?", (record_id,)
        ).fetchone()
        if row:
            self._update_confidence(row["action_type"], positive_outcome=positive)
        self.conn.commit()

    # ── Confidence Management ────────────────────────────────────

    def _update_confidence(
        self,
        action_type: str,
        auto_executed: bool = False,
        overridden: bool = False,
        positive_outcome: Optional[bool] = None,
    ) -> None:
        """Recalculate confidence for an action type."""
        row = self.conn.execute(
            "SELECT * FROM confidence_scores WHERE action_type = ?",
            (action_type,),
        ).fetchone()

        now = _now_iso()
        if row:
            total = row["total_decisions"] + (1 if auto_executed or not overridden else 0)
            auto_count = row["auto_executed_count"] + (1 if auto_executed else 0)
            override_count = row["override_count"] + (1 if overridden else 0)
            positive_count = row["positive_outcome_count"] + (1 if positive_outcome else 0)

            # Confidence formula: weighted average of success signals
            # Overrides heavily penalize confidence
            if total > 0:
                success_rate = positive_count / max(total, 1)
                override_penalty = override_count / max(total, 1)
                new_confidence = max(0.1, min(0.95,
                    success_rate * 0.6 + (1 - override_penalty) * 0.4
                ))
            else:
                new_confidence = 0.5

            self.conn.execute(
                """UPDATE confidence_scores SET
                   confidence = ?, total_decisions = ?,
                   auto_executed_count = ?, override_count = ?,
                   positive_outcome_count = ?, updated_at = ?
                   WHERE action_type = ?""",
                (new_confidence, total, auto_count, override_count,
                 positive_count, now, action_type),
            )
        else:
            initial_confidence = 0.5
            if positive_outcome:
                initial_confidence = 0.6
            if overridden:
                initial_confidence = 0.3

            self.conn.execute(
                """INSERT INTO confidence_scores
                   (action_type, confidence, total_decisions, auto_executed_count,
                    override_count, positive_outcome_count, updated_at)
                   VALUES (?, ?, 1, ?, ?, ?, ?)""",
                (action_type, initial_confidence,
                 1 if auto_executed else 0,
                 1 if overridden else 0,
                 1 if positive_outcome else 0,
                 now),
            )

        # Update cache
        final = self.conn.execute(
            "SELECT confidence FROM confidence_scores WHERE action_type = ?",
            (action_type,),
        ).fetchone()
        if final:
            self._confidence_cache[action_type] = final["confidence"]

    # ── Queries ──────────────────────────────────────────────────

    def get_confidence_scores(self) -> dict[str, dict[str, Any]]:
        """Get all confidence scores."""
        rows = self.conn.execute(
            "SELECT * FROM confidence_scores ORDER BY confidence DESC"
        ).fetchall()
        return {
            r["action_type"]: {
                "confidence": round(r["confidence"], 3),
                "total_decisions": r["total_decisions"],
                "auto_executed": r["auto_executed_count"],
                "overrides": r["override_count"],
                "positive_outcomes": r["positive_outcome_count"],
            }
            for r in rows
        }

    def get_recent_decisions(self, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            "SELECT * FROM escalation_history ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r["id"],
                "action_type": r["action_type"],
                "description": r["description"],
                "auto_executed": bool(r["auto_executed"]),
                "was_overridden": bool(r["was_overridden"]),
                "outcome_positive": r["outcome_positive"],
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    def stats(self) -> dict[str, Any]:
        total = self.conn.execute(
            "SELECT COUNT(*) as c FROM escalation_history"
        ).fetchone()["c"]
        auto = self.conn.execute(
            "SELECT COUNT(*) as c FROM escalation_history WHERE auto_executed = 1"
        ).fetchone()["c"]
        overrides = self.conn.execute(
            "SELECT COUNT(*) as c FROM escalation_history WHERE was_overridden = 1"
        ).fetchone()["c"]
        positive = self.conn.execute(
            "SELECT COUNT(*) as c FROM escalation_history WHERE outcome_positive = 1"
        ).fetchone()["c"]

        return {
            "total_decisions": total,
            "auto_executed": auto,
            "overrides": overrides,
            "positive_outcomes": positive,
            "auto_rate": round(auto / max(total, 1), 3),
            "override_rate": round(overrides / max(auto, 1), 3),
            "positive_rate": round(positive / max(total, 1), 3),
            "action_types_tracked": len(self._confidence_cache),
        }
