"""
Experimentation Lab — continuous testing of ideas, strategies, and products.

The lab constantly tests:
- New SaaS ideas
- Marketing strategies
- Pricing models
- Trading strategies
- Agent configurations

Successful experiments scale. Failed experiments become lessons.
Results feed into the Experience Memory system.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from backend.config import DATA_DIR

EXPERIMENT_DB = DATA_DIR / "experiments.db"

logger = logging.getLogger("root.experiment_lab")


class ExperimentStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"    # Yohan approved — ready to run
    REJECTED = "rejected"    # Yohan rejected
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SCALED = "scaled"        # Successful and scaled up


class ExperimentCategory(str, Enum):
    SAAS = "saas"
    MARKETING = "marketing"
    PRICING = "pricing"
    TRADING = "trading"
    AUTOMATION = "automation"
    CONTENT = "content"
    AGENT_CONFIG = "agent_config"
    INFRASTRUCTURE = "infrastructure"


@dataclass(frozen=True)
class Experiment:
    """Immutable experiment record."""
    id: str
    title: str
    hypothesis: str
    category: ExperimentCategory
    status: ExperimentStatus = ExperimentStatus.PROPOSED
    design: str = ""                       # How to test
    success_criteria: str = ""             # What constitutes success
    metrics: dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    lesson_learned: Optional[str] = None
    confidence: float = 0.5               # Confidence in hypothesis (0-1)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None
    created_by: str = "system"


class ExperimentLab:
    """Continuous experimentation engine for testing ideas and strategies."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = str(db_path or EXPERIMENT_DB)
        self._conn: Optional[sqlite3.Connection] = None
        self._experience_memory = None  # Late-bind to ExperienceMemory

    def set_experience_memory(self, exp_mem) -> None:
        """Late-bind experience memory for recording lessons."""
        self._experience_memory = exp_mem

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
            raise RuntimeError("ExperimentLab not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS experiments (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                hypothesis TEXT NOT NULL,
                category TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'proposed',
                design TEXT DEFAULT '',
                success_criteria TEXT DEFAULT '',
                metrics TEXT DEFAULT '{}',
                result TEXT,
                lesson_learned TEXT,
                confidence REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                created_by TEXT DEFAULT 'system'
            );

            CREATE INDEX IF NOT EXISTS idx_exp_status ON experiments(status);
            CREATE INDEX IF NOT EXISTS idx_exp_category ON experiments(category);
        """)

    # ── Experiment Lifecycle ───────────────────────────────────

    def propose(
        self,
        title: str,
        hypothesis: str,
        category: str,
        design: str = "",
        success_criteria: str = "",
        confidence: float = 0.5,
        created_by: str = "system",
    ) -> Experiment:
        """Propose a new experiment."""
        cat = ExperimentCategory(category)
        exp_id = f"exp_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """INSERT INTO experiments
               (id, title, hypothesis, category, status, design,
                success_criteria, metrics, confidence, created_at, created_by)
               VALUES (?, ?, ?, ?, 'proposed', ?, ?, '{}', ?, ?, ?)""",
            (exp_id, title, hypothesis, cat.value, design,
             success_criteria, confidence, now, created_by),
        )
        self.conn.commit()
        logger.info("Experiment proposed: %s — %s", exp_id, title)

        return Experiment(
            id=exp_id, title=title, hypothesis=hypothesis,
            category=cat, design=design, success_criteria=success_criteria,
            confidence=confidence, created_at=now, created_by=created_by,
        )

    def approve(self, experiment_id: str) -> bool:
        """Yohan approves an experiment — marks it ready to run."""
        cursor = self.conn.execute(
            "UPDATE experiments SET status = 'approved' WHERE id = ? AND status = 'proposed'",
            (experiment_id,),
        )
        self.conn.commit()
        if cursor.rowcount > 0:
            logger.info("Experiment approved by Yohan: %s", experiment_id)
            return True
        return False

    def reject(self, experiment_id: str) -> bool:
        """Yohan rejects an experiment."""
        cursor = self.conn.execute(
            "UPDATE experiments SET status = 'rejected' WHERE id = ? AND status = 'proposed'",
            (experiment_id,),
        )
        self.conn.commit()
        if cursor.rowcount > 0:
            logger.info("Experiment rejected by Yohan: %s", experiment_id)
            return True
        return False

    def start_experiment(self, experiment_id: str) -> bool:
        """Move experiment from proposed/approved to running."""
        cursor = self.conn.execute(
            "UPDATE experiments SET status = 'running' WHERE id = ? AND status IN ('proposed', 'approved')",
            (experiment_id,),
        )
        self.conn.commit()
        if cursor.rowcount > 0:
            logger.info("Experiment started: %s", experiment_id)
            return True
        return False

    def complete_experiment(
        self,
        experiment_id: str,
        result: str,
        metrics: Optional[dict] = None,
        lesson_learned: Optional[str] = None,
        success: bool = True,
    ) -> Optional[Experiment]:
        """Complete an experiment with results."""
        now = datetime.now(timezone.utc).isoformat()
        status = "completed" if success else "failed"
        metrics_str = json.dumps(metrics or {})

        cursor = self.conn.execute(
            """UPDATE experiments
               SET status = ?, result = ?, metrics = ?, lesson_learned = ?,
                   completed_at = ?
               WHERE id = ? AND status = 'running'""",
            (status, result, metrics_str, lesson_learned, now, experiment_id),
        )
        self.conn.commit()

        if cursor.rowcount == 0:
            return None

        logger.info("Experiment %s: %s", status, experiment_id)

        # Record in experience memory
        if self._experience_memory and lesson_learned:
            exp_type = "success" if success else "failure"
            try:
                self._experience_memory.record_experience(
                    experience_type=exp_type,
                    domain="experimentation",
                    title=f"Experiment: {experiment_id}",
                    description=lesson_learned,
                    context=metrics or {},
                )
            except Exception as exc:
                logger.warning("Failed to record experience: %s", exc)

        return self._get_by_id(experiment_id)

    def scale_experiment(self, experiment_id: str) -> bool:
        """Mark a successful experiment as scaled."""
        cursor = self.conn.execute(
            "UPDATE experiments SET status = 'scaled' WHERE id = ? AND status = 'completed'",
            (experiment_id,),
        )
        self.conn.commit()
        if cursor.rowcount > 0:
            logger.info("Experiment scaled: %s", experiment_id)
            return True
        return False

    # ── Queries ────────────────────────────────────────────────

    def get_proposed(self, limit: int = 20) -> list[Experiment]:
        return self._query("status = 'proposed'", limit=limit)

    def get_running(self, limit: int = 20) -> list[Experiment]:
        return self._query("status = 'running'", limit=limit)

    def get_completed(self, limit: int = 20) -> list[Experiment]:
        return self._query("status IN ('completed', 'failed')", limit=limit)

    def get_scaled(self, limit: int = 20) -> list[Experiment]:
        return self._query("status = 'scaled'", limit=limit)

    def get_by_category(self, category: str, limit: int = 20) -> list[Experiment]:
        return self._query("category = ?", params=[category], limit=limit)

    def _get_by_id(self, experiment_id: str) -> Optional[Experiment]:
        row = self.conn.execute(
            "SELECT * FROM experiments WHERE id = ?", (experiment_id,),
        ).fetchone()
        return self._row_to_experiment(row) if row else None

    _ALLOWED_WHERE_CLAUSES = frozenset({
        "status = 'proposed'",
        "status = 'running'",
        "status IN ('completed', 'failed')",
        "status = 'scaled'",
        "category = ?",
    })

    def _query(self, where: str, params: Optional[list] = None,
               limit: int = 20) -> list[Experiment]:
        if where not in self._ALLOWED_WHERE_CLAUSES:
            raise ValueError(f"Disallowed WHERE clause: {where}")
        sql = f"SELECT * FROM experiments WHERE {where} ORDER BY created_at DESC LIMIT ?"
        all_params = (params or []) + [limit]
        rows = self.conn.execute(sql, all_params).fetchall()
        return [self._row_to_experiment(r) for r in rows]

    def stats(self) -> dict[str, Any]:
        """Lab statistics."""
        rows = self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM experiments GROUP BY status"
        ).fetchall()
        total = self.conn.execute("SELECT COUNT(*) as c FROM experiments").fetchone()
        cat_rows = self.conn.execute(
            "SELECT category, COUNT(*) as cnt FROM experiments GROUP BY category"
        ).fetchall()
        return {
            "total_experiments": total["c"] if total else 0,
            "by_status": {r["status"]: r["cnt"] for r in rows},
            "by_category": {r["category"]: r["cnt"] for r in cat_rows},
        }

    @staticmethod
    def _row_to_experiment(row: sqlite3.Row) -> Experiment:
        try:
            metrics = json.loads(row["metrics"]) if row["metrics"] else {}
        except json.JSONDecodeError:
            metrics = {}
        return Experiment(
            id=row["id"], title=row["title"], hypothesis=row["hypothesis"],
            category=ExperimentCategory(row["category"]),
            status=ExperimentStatus(row["status"]),
            design=row["design"] or "", success_criteria=row["success_criteria"] or "",
            metrics=metrics, result=row["result"],
            lesson_learned=row["lesson_learned"],
            confidence=row["confidence"], created_at=row["created_at"],
            completed_at=row["completed_at"], created_by=row["created_by"] or "system",
        )
