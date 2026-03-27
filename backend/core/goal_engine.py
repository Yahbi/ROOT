"""
Goal Engine — autonomous goal management for ROOT.

Maintains a persistent priority queue of goals derived from:
- User's stated objectives
- Patterns detected by user_patterns engine
- Proactive engine discoveries
- Learning engine insights

Breaks goals into actionable tasks, tracks progress across sessions,
and learns which goals matter most.
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

logger = logging.getLogger("root.goal_engine")

GOALS_DB = ROOT_DIR / "data" / "goals.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class Goal:
    """An immutable goal with progress tracking."""
    id: str
    title: str
    description: str
    priority: int = 5  # 1=critical, 5=normal, 9=background
    status: str = "active"  # active | paused | completed | abandoned
    source: str = "user"  # user | pattern | proactive | autonomous | reflection
    category: str = "general"  # general, trading, learning, automation, health, career
    progress: float = 0.0  # 0.0 to 1.0
    milestones: tuple[str, ...] = ()
    completed_milestones: tuple[str, ...] = ()
    tasks_generated: int = 0
    tasks_completed: int = 0
    deadline: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    completed_at: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class GoalEngine:
    """Persistent goal management with autonomous decomposition."""

    MAX_ACTIVE_GOALS = 20

    def __init__(self, memory=None, llm=None, task_queue=None) -> None:
        self._memory = memory
        self._llm = llm
        self._task_queue = task_queue
        self._conn: Optional[sqlite3.Connection] = None

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        GOALS_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(GOALS_DB), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        logger.info("GoalEngine started (db=%s)", GOALS_DB)

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("GoalEngine not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS goals (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                priority INTEGER DEFAULT 5,
                status TEXT DEFAULT 'active',
                source TEXT DEFAULT 'user',
                category TEXT DEFAULT 'general',
                progress REAL DEFAULT 0.0,
                milestones TEXT DEFAULT '[]',
                completed_milestones TEXT DEFAULT '[]',
                tasks_generated INTEGER DEFAULT 0,
                tasks_completed INTEGER DEFAULT 0,
                deadline TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                completed_at TEXT,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS goal_events (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (goal_id) REFERENCES goals(id)
            );

            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
            CREATE INDEX IF NOT EXISTS idx_goals_priority ON goals(priority);
            CREATE INDEX IF NOT EXISTS idx_goal_events_goal ON goal_events(goal_id);
        """)

    # ── Goal CRUD ────────────────────────────────────────────────

    def add_goal(
        self,
        title: str,
        description: str = "",
        priority: int = 5,
        source: str = "user",
        category: str = "general",
        milestones: list[str] | None = None,
        deadline: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> Goal:
        """Add a new goal."""
        active_count = self.conn.execute(
            "SELECT COUNT(*) as c FROM goals WHERE status = 'active'"
        ).fetchone()["c"]
        if active_count >= self.MAX_ACTIVE_GOALS:
            # Auto-pause lowest priority goal
            self.conn.execute(
                """UPDATE goals SET status = 'paused', updated_at = ?
                   WHERE id = (
                       SELECT id FROM goals WHERE status = 'active'
                       ORDER BY priority DESC, updated_at ASC LIMIT 1
                   )""",
                (_now_iso(),),
            )

        goal_id = f"goal_{uuid.uuid4().hex[:12]}"
        now = _now_iso()

        self.conn.execute(
            """INSERT INTO goals
               (id, title, description, priority, source, category,
                milestones, deadline, created_at, updated_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (goal_id, title[:500], description[:2000], priority, source,
             category, json.dumps(milestones or []), deadline,
             now, now, json.dumps(metadata or {})),
        )
        self._log_event(goal_id, "created", f"Goal created: {title[:200]}")
        self.conn.commit()

        return Goal(
            id=goal_id, title=title[:500], description=description[:2000],
            priority=priority, source=source, category=category,
            milestones=tuple(milestones or []), deadline=deadline,
            created_at=now, updated_at=now, metadata=metadata or {},
        )

    def update_progress(self, goal_id: str, progress: float, note: str = "") -> Optional[Goal]:
        """Update goal progress (0.0 to 1.0)."""
        progress = max(0.0, min(1.0, progress))
        now = _now_iso()

        if progress >= 1.0:
            self.conn.execute(
                "UPDATE goals SET progress = ?, updated_at = ?, status = 'completed', completed_at = ? WHERE id = ?",
                (progress, now, now, goal_id),
            )
        else:
            self.conn.execute(
                "UPDATE goals SET progress = ?, updated_at = ? WHERE id = ?",
                (progress, now, goal_id),
            )
        self._log_event(goal_id, "progress", f"Progress: {progress:.0%}" + (f" — {note}" if note else ""))
        self.conn.commit()
        return self.get_goal(goal_id)

    def complete_milestone(self, goal_id: str, milestone: str) -> Optional[Goal]:
        """Mark a milestone as completed."""
        goal = self.get_goal(goal_id)
        if not goal:
            return None

        completed = list(goal.completed_milestones)
        if milestone not in completed:
            completed.append(milestone)

        # Recalculate progress
        total_milestones = len(goal.milestones)
        new_progress = len(completed) / total_milestones if total_milestones > 0 else goal.progress

        now = _now_iso()
        self.conn.execute(
            """UPDATE goals SET completed_milestones = ?, progress = ?,
               updated_at = ? WHERE id = ?""",
            (json.dumps(completed), new_progress, now, goal_id),
        )
        self._log_event(goal_id, "milestone", f"Completed: {milestone}")
        self.conn.commit()
        return self.get_goal(goal_id)

    def record_task_completion(self, goal_id: str) -> None:
        """Increment tasks_completed for a goal."""
        now = _now_iso()
        self.conn.execute(
            """UPDATE goals SET tasks_completed = tasks_completed + 1,
               updated_at = ? WHERE id = ?""",
            (now, goal_id),
        )
        self.conn.commit()

    def pause_goal(self, goal_id: str) -> bool:
        cursor = self.conn.execute(
            "UPDATE goals SET status = 'paused', updated_at = ? WHERE id = ? AND status = 'active'",
            (_now_iso(), goal_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def resume_goal(self, goal_id: str) -> bool:
        cursor = self.conn.execute(
            "UPDATE goals SET status = 'active', updated_at = ? WHERE id = ? AND status = 'paused'",
            (_now_iso(), goal_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def abandon_goal(self, goal_id: str) -> bool:
        now = _now_iso()
        cursor = self.conn.execute(
            "UPDATE goals SET status = 'abandoned', updated_at = ?, completed_at = ? WHERE id = ?",
            (now, now, goal_id),
        )
        self._log_event(goal_id, "abandoned", "Goal abandoned")
        self.conn.commit()
        return cursor.rowcount > 0

    # ── Autonomous Decomposition ─────────────────────────────────

    async def decompose_goal(self, goal_id: str) -> list[str]:
        """Use LLM to break a goal into tasks and queue them."""
        goal = self.get_goal(goal_id)
        if not goal or not self._llm:
            return []

        prompt = (
            f"Break this goal into 3-7 concrete, actionable tasks.\n\n"
            f"GOAL: {goal.title}\n"
            f"DESCRIPTION: {goal.description}\n"
            f"CATEGORY: {goal.category}\n\n"
            "Return ONLY valid JSON (no markdown):\n"
            '{"tasks": [{"description": "...", "priority": 5}]}'
        )

        try:
            response = await self._llm.complete(
                system="You decompose goals into concrete tasks. Be specific and actionable.",
                messages=[{"role": "user", "content": prompt}],
                model_tier="fast",
                max_tokens=800,
            )
            raw = response.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            data = json.loads(raw)
            task_dicts = data.get("tasks", [])[:7]
        except Exception as exc:
            logger.warning("Goal decomposition failed: %s", exc)
            task_dicts = [{"description": goal.title, "priority": goal.priority}]

        task_ids: list[str] = []
        for td in task_dicts:
            if self._task_queue:
                queued = self._task_queue.enqueue(
                    goal=str(td.get("description", "")),
                    priority=int(td.get("priority", goal.priority)),
                    source="goal_engine",
                    metadata={"goal_id": goal_id},
                )
                task_ids.append(queued.id)

        # Update goal task count
        now = _now_iso()
        self.conn.execute(
            "UPDATE goals SET tasks_generated = tasks_generated + ?, updated_at = ? WHERE id = ?",
            (len(task_ids), now, goal_id),
        )
        self._log_event(goal_id, "decomposed", f"Generated {len(task_ids)} tasks")
        self.conn.commit()
        return task_ids

    # ── Goal Assessment (background) ────────────────────────────

    async def assess_all_goals(self) -> dict[str, Any]:
        """Assess progress on all active goals. Called by proactive engine."""
        active = self.get_active_goals()
        if not active:
            return {"goals_assessed": 0}

        results: dict[str, Any] = {"goals_assessed": len(active), "updates": []}

        for goal in active:
            # Check if goal has stalled (no updates in 7 days)
            try:
                updated = datetime.fromisoformat(goal.updated_at)
                days_since = (datetime.now(timezone.utc) - updated).days
                if days_since > 7 and goal.progress < 1.0:
                    results["updates"].append({
                        "goal_id": goal.id,
                        "title": goal.title,
                        "status": "stalled",
                        "days_inactive": days_since,
                    })
            except (ValueError, TypeError):
                pass

            # Auto-complete goals where all tasks are done
            if goal.tasks_generated > 0 and goal.tasks_completed >= goal.tasks_generated:
                self.update_progress(goal.id, 1.0, "All tasks completed")
                results["updates"].append({
                    "goal_id": goal.id,
                    "title": goal.title,
                    "status": "auto_completed",
                })

        return results

    async def auto_recover_stalled(self, max_recoveries: int = 3) -> dict[str, Any]:
        """Automatically recover stalled goals by decomposing them into tasks.

        For goals stalled 7-13 days: decompose into fresh tasks.
        For goals stalled 14+ days: decompose + lower priority (avoid infinite loops).
        For goals stalled 30+ days: abandon and create a replacement with lessons learned.
        """
        assessment = await self.assess_all_goals()
        stalled = [u for u in assessment.get("updates", []) if u.get("status") == "stalled"]

        recovered: list[dict[str, Any]] = []
        for stall in stalled[:max_recoveries]:
            goal_id = stall.get("goal_id", "")
            days = stall.get("days_inactive", 0)
            goal = self.get_goal(goal_id)
            if not goal:
                continue

            if days >= 30:
                # Abandon and log lesson
                self.abandon_goal(goal_id)
                self._log_event(goal_id, "auto_abandoned",
                                f"Auto-abandoned after {days} days stalled")
                recovered.append({
                    "goal_id": goal_id, "action": "abandoned",
                    "reason": f"Stalled {days}d — auto-abandoned",
                })
            elif days >= 14:
                # Decompose with lower priority
                task_ids = await self.decompose_goal(goal_id)
                if goal.priority < 9:
                    now = _now_iso()
                    self.conn.execute(
                        "UPDATE goals SET priority = ?, updated_at = ? WHERE id = ?",
                        (min(goal.priority + 2, 9), now, goal_id),
                    )
                    self.conn.commit()
                self._log_event(goal_id, "auto_recovered",
                                f"Decomposed into {len(task_ids)} tasks (priority lowered)")
                recovered.append({
                    "goal_id": goal_id, "action": "decomposed_deprioritized",
                    "tasks_created": len(task_ids),
                })
            elif days >= 7:
                # Standard decomposition
                task_ids = await self.decompose_goal(goal_id)
                self._log_event(goal_id, "auto_recovered",
                                f"Auto-decomposed into {len(task_ids)} tasks")
                recovered.append({
                    "goal_id": goal_id, "action": "decomposed",
                    "tasks_created": len(task_ids),
                })

        logger.info("Goal auto-recovery: %d goals processed", len(recovered))
        return {"recovered": recovered, "total_stalled": len(stalled)}

    # ── Queries ───────────────────────────────────────────────────

    def get_goal(self, goal_id: str) -> Optional[Goal]:
        row = self.conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
        return self._row_to_goal(row) if row else None

    def get_active_goals(self, limit: int = 20) -> list[Goal]:
        rows = self.conn.execute(
            "SELECT * FROM goals WHERE status = 'active' ORDER BY priority ASC, updated_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_goal(r) for r in rows]

    def get_goals_by_category(self, category: str) -> list[Goal]:
        rows = self.conn.execute(
            "SELECT * FROM goals WHERE category = ? AND status = 'active' ORDER BY priority ASC",
            (category,),
        ).fetchall()
        return [self._row_to_goal(r) for r in rows]

    def get_all_goals(self, limit: int = 50) -> list[Goal]:
        rows = self.conn.execute(
            "SELECT * FROM goals ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [self._row_to_goal(r) for r in rows]

    def get_goal_events(self, goal_id: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """SELECT * FROM goal_events WHERE goal_id = ?
               ORDER BY created_at DESC LIMIT ?""",
            (goal_id, limit),
        ).fetchall()
        return [
            {"id": r["id"], "event_type": r["event_type"],
             "description": r["description"], "created_at": r["created_at"]}
            for r in rows
        ]

    def stats(self) -> dict[str, Any]:
        rows = self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM goals GROUP BY status"
        ).fetchall()
        by_status = {r["status"]: r["cnt"] for r in rows}

        cat_rows = self.conn.execute(
            "SELECT category, COUNT(*) as cnt FROM goals WHERE status = 'active' GROUP BY category"
        ).fetchall()
        by_category = {r["category"]: r["cnt"] for r in cat_rows}

        avg_progress = self.conn.execute(
            "SELECT AVG(progress) as avg FROM goals WHERE status = 'active'"
        ).fetchone()

        return {
            "total_goals": sum(by_status.values()),
            "by_status": by_status,
            "by_category": by_category,
            "avg_active_progress": round((avg_progress["avg"] or 0), 3),
        }

    # ── Helpers ───────────────────────────────────────────────────

    def _log_event(self, goal_id: str, event_type: str, description: str) -> None:
        self.conn.execute(
            "INSERT INTO goal_events (id, goal_id, event_type, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (f"ge_{uuid.uuid4().hex[:12]}", goal_id, event_type, description[:500], _now_iso()),
        )

    def _row_to_goal(self, row: sqlite3.Row) -> Goal:
        milestones = []
        completed_milestones = []
        metadata = {}
        try:
            milestones = json.loads(row["milestones"] or "[]")
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            completed_milestones = json.loads(row["completed_milestones"] or "[]")
        except (json.JSONDecodeError, TypeError):
            pass
        try:
            metadata = json.loads(row["metadata"] or "{}")
        except (json.JSONDecodeError, TypeError):
            pass

        return Goal(
            id=row["id"], title=row["title"],
            description=row["description"] or "",
            priority=row["priority"], status=row["status"],
            source=row["source"] or "user",
            category=row["category"] or "general",
            progress=row["progress"] or 0.0,
            milestones=tuple(milestones),
            completed_milestones=tuple(completed_milestones),
            tasks_generated=row["tasks_generated"] or 0,
            tasks_completed=row["tasks_completed"] or 0,
            deadline=row["deadline"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            metadata=metadata,
        )
