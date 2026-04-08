"""
Goal Engine — autonomous goal management for ROOT.

Maintains a persistent priority queue of goals derived from:
- User's stated objectives
- Patterns detected by user_patterns engine
- Proactive engine discoveries
- Learning engine insights

Breaks goals into actionable tasks, tracks progress across sessions,
and learns which goals matter most.

Enhanced features (v1.1):
- Dependency tracking: goals can depend on other goals
- Progress estimation: velocity-based completion date prediction
- Priority scoring: importance × urgency matrix
- Structured milestones: trackable sub-items with metadata
- Conflict detection: identify goals competing for same resources
- Suggestion engine: propose new goals based on capabilities and gaps
- Retrospective: auto-analyse completed goals for lessons
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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
    # v1.1 fields
    depends_on: tuple[str, ...] = ()       # goal IDs this goal depends on
    importance: int = 5                    # 1–9 for priority matrix
    urgency: int = 5                       # 1–9 for priority matrix
    resources: tuple[str, ...] = ()        # resource tags (e.g. "llm", "capital", "time")
    priority_score: float = 0.0            # computed importance × urgency (normalised)


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
                metadata TEXT DEFAULT '{}',
                depends_on TEXT DEFAULT '[]',
                importance INTEGER DEFAULT 5,
                urgency INTEGER DEFAULT 5,
                resources TEXT DEFAULT '[]',
                priority_score REAL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS goal_events (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                description TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (goal_id) REFERENCES goals(id)
            );

            CREATE TABLE IF NOT EXISTS goal_milestones (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                order_index INTEGER DEFAULT 0,
                due_date TEXT,
                completed_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (goal_id) REFERENCES goals(id)
            );

            CREATE TABLE IF NOT EXISTS goal_retrospectives (
                id TEXT PRIMARY KEY,
                goal_id TEXT NOT NULL,
                duration_days REAL,
                completion_accuracy REAL,
                lessons TEXT DEFAULT '[]',
                successes TEXT DEFAULT '[]',
                obstacles TEXT DEFAULT '[]',
                velocity_avg REAL DEFAULT 0.0,
                created_at TEXT NOT NULL,
                FOREIGN KEY (goal_id) REFERENCES goals(id)
            );

            CREATE INDEX IF NOT EXISTS idx_goals_status ON goals(status);
            CREATE INDEX IF NOT EXISTS idx_goals_priority ON goals(priority);
            CREATE INDEX IF NOT EXISTS idx_goals_priority_score ON goals(priority_score);
            CREATE INDEX IF NOT EXISTS idx_goal_events_goal ON goal_events(goal_id);
            CREATE INDEX IF NOT EXISTS idx_goal_milestones_goal ON goal_milestones(goal_id);
            CREATE INDEX IF NOT EXISTS idx_goal_retro_goal ON goal_retrospectives(goal_id);
        """)
        self._migrate_schema()

    def _migrate_schema(self) -> None:
        """Add new columns to existing databases (idempotent)."""
        new_cols = [
            ("depends_on", "TEXT DEFAULT '[]'"),
            ("importance", "INTEGER DEFAULT 5"),
            ("urgency", "INTEGER DEFAULT 5"),
            ("resources", "TEXT DEFAULT '[]'"),
            ("priority_score", "REAL DEFAULT 0.0"),
        ]
        existing = {
            row[1]
            for row in self.conn.execute("PRAGMA table_info(goals)").fetchall()
        }
        for col, typedef in new_cols:
            if col not in existing:
                self.conn.execute(f"ALTER TABLE goals ADD COLUMN {col} {typedef}")
        self.conn.commit()

    # ── Priority Scoring ─────────────────────────────────────────

    @staticmethod
    def compute_priority_score(importance: int, urgency: int) -> float:
        """Importance × urgency matrix, normalised to [0, 1].

        Both axes are 1–9 (1=highest). We invert so that score=1 is best.
        """
        inv_imp = (10 - max(1, min(9, importance))) / 9.0
        inv_urg = (10 - max(1, min(9, urgency))) / 9.0
        return round(inv_imp * inv_urg, 4)

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
        depends_on: list[str] | None = None,
        importance: int = 5,
        urgency: int = 5,
        resources: list[str] | None = None,
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
        priority_score = self.compute_priority_score(importance, urgency)

        self.conn.execute(
            """INSERT INTO goals
               (id, title, description, priority, source, category,
                milestones, deadline, created_at, updated_at, metadata,
                depends_on, importance, urgency, resources, priority_score)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (goal_id, title[:500], description[:2000], priority, source,
             category, json.dumps(milestones or []), deadline,
             now, now, json.dumps(metadata or {}),
             json.dumps(depends_on or []), importance, urgency,
             json.dumps(resources or []), priority_score),
        )
        self._log_event(goal_id, "created", f"Goal created: {title[:200]}")
        self.conn.commit()

        return Goal(
            id=goal_id, title=title[:500], description=description[:2000],
            priority=priority, source=source, category=category,
            milestones=tuple(milestones or []), deadline=deadline,
            created_at=now, updated_at=now, metadata=metadata or {},
            depends_on=tuple(depends_on or []),
            importance=importance, urgency=urgency,
            resources=tuple(resources or []),
            priority_score=priority_score,
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

    # ── Dependency Tracking ──────────────────────────────────────

    def add_dependency(self, goal_id: str, depends_on_id: str) -> bool:
        """Make goal_id depend on depends_on_id."""
        goal = self.get_goal(goal_id)
        if not goal or not self.get_goal(depends_on_id):
            return False
        deps = list(goal.depends_on)
        if depends_on_id in deps:
            return True  # already set
        # Cycle guard: depends_on_id must not already depend (directly/transitively) on goal_id
        if self._would_create_cycle(goal_id, depends_on_id):
            logger.warning("Dependency cycle detected: %s -> %s", goal_id, depends_on_id)
            return False
        deps.append(depends_on_id)
        self.conn.execute(
            "UPDATE goals SET depends_on = ?, updated_at = ? WHERE id = ?",
            (json.dumps(deps), _now_iso(), goal_id),
        )
        self._log_event(goal_id, "dependency_added", f"Depends on {depends_on_id}")
        self.conn.commit()
        return True

    def remove_dependency(self, goal_id: str, depends_on_id: str) -> bool:
        """Remove a dependency from goal_id."""
        goal = self.get_goal(goal_id)
        if not goal:
            return False
        deps = [d for d in goal.depends_on if d != depends_on_id]
        self.conn.execute(
            "UPDATE goals SET depends_on = ?, updated_at = ? WHERE id = ?",
            (json.dumps(deps), _now_iso(), goal_id),
        )
        self._log_event(goal_id, "dependency_removed", f"Removed dep on {depends_on_id}")
        self.conn.commit()
        return True

    def get_blocked_goals(self) -> list[dict[str, Any]]:
        """Return active goals whose dependencies are not yet completed."""
        active = self.get_active_goals(limit=100)
        blocked: list[dict[str, Any]] = []
        for goal in active:
            if not goal.depends_on:
                continue
            blocking: list[str] = []
            for dep_id in goal.depends_on:
                dep = self.get_goal(dep_id)
                if dep and dep.status != "completed":
                    blocking.append(dep_id)
            if blocking:
                blocked.append({
                    "goal_id": goal.id,
                    "title": goal.title,
                    "blocked_by": blocking,
                })
        return blocked

    def get_dependency_graph(self) -> dict[str, list[str]]:
        """Return full dependency map {goal_id: [depends_on, ...]}."""
        rows = self.conn.execute(
            "SELECT id, depends_on FROM goals WHERE status != 'abandoned'"
        ).fetchall()
        graph: dict[str, list[str]] = {}
        for row in rows:
            deps = []
            try:
                deps = json.loads(row["depends_on"] or "[]")
            except (json.JSONDecodeError, TypeError):
                pass
            graph[row["id"]] = deps
        return graph

    def _would_create_cycle(self, goal_id: str, new_dep_id: str) -> bool:
        """DFS check: would adding new_dep_id as a dep of goal_id create a cycle?"""
        graph = self.get_dependency_graph()
        visited: set[str] = set()

        def dfs(node: str) -> bool:
            if node == goal_id:
                return True
            if node in visited:
                return False
            visited.add(node)
            for dep in graph.get(node, []):
                if dfs(dep):
                    return True
            return False

        return dfs(new_dep_id)

    # ── Progress Estimation ──────────────────────────────────────

    def estimate_completion(self, goal_id: str) -> dict[str, Any]:
        """Predict completion date based on velocity (progress/day)."""
        goal = self.get_goal(goal_id)
        if not goal:
            return {"error": "Goal not found"}
        if goal.status == "completed":
            return {"status": "completed", "completed_at": goal.completed_at}

        # Pull progress events in chronological order
        events = self.conn.execute(
            """SELECT description, created_at FROM goal_events
               WHERE goal_id = ? AND event_type = 'progress'
               ORDER BY created_at ASC""",
            (goal_id,),
        ).fetchall()

        # Parse progress values from event descriptions like "Progress: 50%"
        checkpoints: list[tuple[datetime, float]] = []
        for ev in events:
            try:
                pct_str = ev["description"].split("Progress:")[1].split("%")[0].strip()
                pct = float(pct_str) / 100.0
                ts = datetime.fromisoformat(ev["created_at"])
                checkpoints.append((ts, pct))
            except (IndexError, ValueError):
                pass

        now_dt = datetime.now(timezone.utc)
        try:
            created_dt = datetime.fromisoformat(goal.created_at)
        except ValueError:
            created_dt = now_dt

        if len(checkpoints) < 2:
            # Use overall elapsed time as a single datapoint
            elapsed_days = max((now_dt - created_dt).total_seconds() / 86400, 0.01)
            current_progress = goal.progress
            velocity = current_progress / elapsed_days if elapsed_days > 0 else 0.0
        else:
            # Velocity from last two checkpoints
            t0, p0 = checkpoints[-2]
            t1, p1 = checkpoints[-1]
            delta_days = max((t1 - t0).total_seconds() / 86400, 0.01)
            velocity = (p1 - p0) / delta_days
            current_progress = p1

        remaining = max(0.0, 1.0 - current_progress)
        result: dict[str, Any] = {
            "current_progress": round(current_progress, 3),
            "velocity_per_day": round(velocity, 4),
            "remaining": round(remaining, 3),
        }

        if velocity > 0:
            days_to_done = remaining / velocity
            eta = now_dt + timedelta(days=days_to_done)
            result["estimated_completion"] = eta.isoformat()
            result["days_remaining"] = round(days_to_done, 1)
            if goal.deadline:
                try:
                    dl = datetime.fromisoformat(goal.deadline)
                    on_track = eta <= dl
                    result["on_track"] = on_track
                    result["deadline"] = goal.deadline
                    result["deadline_buffer_days"] = round((dl - eta).total_seconds() / 86400, 1)
                except ValueError:
                    pass
        else:
            result["estimated_completion"] = None
            result["days_remaining"] = None

        return result

    def get_velocity_report(self) -> list[dict[str, Any]]:
        """Return velocity estimates for all active goals."""
        active = self.get_active_goals(limit=100)
        return [
            {"goal_id": g.id, "title": g.title, **self.estimate_completion(g.id)}
            for g in active
        ]

    # ── Priority Scoring ─────────────────────────────────────────

    def update_priority_score(
        self,
        goal_id: str,
        importance: int | None = None,
        urgency: int | None = None,
    ) -> Optional[Goal]:
        """Recompute and persist the importance × urgency priority score."""
        goal = self.get_goal(goal_id)
        if not goal:
            return None
        imp = importance if importance is not None else goal.importance
        urg = urgency if urgency is not None else goal.urgency
        score = self.compute_priority_score(imp, urg)
        self.conn.execute(
            """UPDATE goals SET importance = ?, urgency = ?, priority_score = ?,
               updated_at = ? WHERE id = ?""",
            (imp, urg, score, _now_iso(), goal_id),
        )
        self._log_event(
            goal_id, "priority_scored",
            f"importance={imp}, urgency={urg} → score={score:.4f}",
        )
        self.conn.commit()
        return self.get_goal(goal_id)

    def get_prioritised_goals(self, limit: int = 20) -> list[Goal]:
        """Return active goals sorted by priority_score DESC (best first)."""
        rows = self.conn.execute(
            """SELECT * FROM goals WHERE status = 'active'
               ORDER BY priority_score DESC, priority ASC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [self._row_to_goal(r) for r in rows]

    # ── Structured Milestones ────────────────────────────────────

    def add_milestone(
        self,
        goal_id: str,
        title: str,
        description: str = "",
        order_index: int = 0,
        due_date: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Add a structured milestone record to a goal."""
        if not self.get_goal(goal_id):
            return None
        ms_id = f"ms_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        self.conn.execute(
            """INSERT INTO goal_milestones
               (id, goal_id, title, description, status, order_index, due_date, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?, ?, ?)""",
            (ms_id, goal_id, title[:300], description[:1000], order_index, due_date, now),
        )
        self._log_event(goal_id, "milestone_added", f"Milestone added: {title[:200]}")
        self.conn.commit()
        return {
            "id": ms_id, "goal_id": goal_id, "title": title,
            "status": "pending", "order_index": order_index, "due_date": due_date,
        }

    def complete_structured_milestone(
        self, goal_id: str, milestone_id: str
    ) -> Optional[dict[str, Any]]:
        """Mark a structured milestone as completed and recalculate progress."""
        now = _now_iso()
        cursor = self.conn.execute(
            """UPDATE goal_milestones SET status = 'completed', completed_at = ?
               WHERE id = ? AND goal_id = ? AND status = 'pending'""",
            (now, milestone_id, goal_id),
        )
        if cursor.rowcount == 0:
            return None

        # Recalculate progress from structured milestones
        total = self.conn.execute(
            "SELECT COUNT(*) as c FROM goal_milestones WHERE goal_id = ?", (goal_id,)
        ).fetchone()["c"]
        done = self.conn.execute(
            "SELECT COUNT(*) as c FROM goal_milestones WHERE goal_id = ? AND status = 'completed'",
            (goal_id,),
        ).fetchone()["c"]

        if total > 0:
            new_progress = done / total
            self.conn.execute(
                "UPDATE goals SET progress = ?, updated_at = ? WHERE id = ?",
                (new_progress, now, goal_id),
            )
        self._log_event(goal_id, "milestone_completed", f"Milestone {milestone_id} completed")
        self.conn.commit()
        return self.get_milestones(goal_id)

    def get_milestones(self, goal_id: str) -> list[dict[str, Any]]:
        """Return all structured milestones for a goal."""
        rows = self.conn.execute(
            """SELECT * FROM goal_milestones WHERE goal_id = ?
               ORDER BY order_index ASC, created_at ASC""",
            (goal_id,),
        ).fetchall()
        return [
            {
                "id": r["id"], "goal_id": r["goal_id"], "title": r["title"],
                "description": r["description"] or "", "status": r["status"],
                "order_index": r["order_index"], "due_date": r["due_date"],
                "completed_at": r["completed_at"], "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ── Conflict Detection ───────────────────────────────────────

    def detect_conflicts(self) -> list[dict[str, Any]]:
        """Identify active goals competing for the same resources."""
        active = self.get_active_goals(limit=100)
        conflicts: list[dict[str, Any]] = []
        seen: set[frozenset] = set()

        for i, g1 in enumerate(active):
            for g2 in active[i + 1:]:
                shared = set(g1.resources) & set(g2.resources)
                if not shared:
                    continue
                pair = frozenset((g1.id, g2.id))
                if pair in seen:
                    continue
                seen.add(pair)
                # Conflict severity: both high-priority and same resource → critical
                combined_score = g1.priority_score + g2.priority_score
                severity = (
                    "critical" if combined_score > 1.2
                    else "high" if combined_score > 0.8
                    else "medium"
                )
                conflicts.append({
                    "goal_a": {"id": g1.id, "title": g1.title, "priority_score": g1.priority_score},
                    "goal_b": {"id": g2.id, "title": g2.title, "priority_score": g2.priority_score},
                    "shared_resources": list(shared),
                    "severity": severity,
                    "recommendation": (
                        f"Consider sequencing '{g1.title}' and '{g2.title}' "
                        f"to avoid contention on: {', '.join(shared)}"
                    ),
                })

        # Also detect goals in the same category that are both high-priority
        cat_map: dict[str, list[Goal]] = {}
        for g in active:
            cat_map.setdefault(g.category, []).append(g)
        for cat, goals in cat_map.items():
            high = [g for g in goals if g.priority <= 2]
            if len(high) > 2:
                pair = frozenset(g.id for g in high)
                if pair not in seen:
                    seen.add(pair)
                    conflicts.append({
                        "goal_a": None,
                        "goal_b": None,
                        "group": [{"id": g.id, "title": g.title} for g in high],
                        "shared_resources": [f"category:{cat}"],
                        "severity": "medium",
                        "recommendation": (
                            f"{len(high)} critical goals in '{cat}' — "
                            "consider pausing lower-urgency items."
                        ),
                    })

        return conflicts

    # ── Suggestion Engine ────────────────────────────────────────

    async def suggest_goals(self, context: str = "") -> list[dict[str, Any]]:
        """Use LLM to propose new goals based on capabilities, gaps and context."""
        if not self._llm:
            return self._offline_goal_suggestions()

        active_titles = [g.title for g in self.get_active_goals(limit=10)]
        completed_rows = self.conn.execute(
            """SELECT title FROM goals WHERE status = 'completed'
               ORDER BY completed_at DESC LIMIT 10"""
        ).fetchall()
        completed_titles = [r["title"] for r in completed_rows]

        prompt = (
            "You are a strategic AI advisor. Based on the active and completed goals below, "
            "suggest 3–5 new goals that address capability gaps, emerging opportunities, "
            "or logical next steps.\n\n"
            f"ACTIVE GOALS:\n{json.dumps(active_titles, indent=2)}\n\n"
            f"RECENTLY COMPLETED:\n{json.dumps(completed_titles, indent=2)}\n\n"
            + (f"ADDITIONAL CONTEXT:\n{context}\n\n" if context else "")
            + "Return ONLY valid JSON (no markdown):\n"
            '{"suggestions": [{"title": "...", "description": "...", "category": "...", '
            '"importance": 5, "urgency": 5, "rationale": "..."}]}'
        )

        try:
            response = await self._llm.complete(
                system="You suggest strategic goals. Be specific, actionable, and concise.",
                messages=[{"role": "user", "content": prompt}],
                model_tier="fast",
                max_tokens=1000,
            )
            raw = response.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            data = json.loads(raw)
            suggestions = data.get("suggestions", [])[:5]
            for s in suggestions:
                s["priority_score"] = self.compute_priority_score(
                    s.get("importance", 5), s.get("urgency", 5)
                )
            return suggestions
        except Exception as exc:
            logger.warning("Goal suggestion LLM call failed: %s", exc)
            return self._offline_goal_suggestions()

    def _offline_goal_suggestions(self) -> list[dict[str, Any]]:
        """Fallback suggestions based on active goal categories."""
        active = self.get_active_goals(limit=20)
        categories = {g.category for g in active}
        uncovered = {"trading", "learning", "automation", "health"} - categories
        suggestions = []
        for cat in list(uncovered)[:3]:
            suggestions.append({
                "title": f"Expand capabilities in {cat}",
                "description": f"Identify and pursue one high-impact {cat} goal.",
                "category": cat,
                "importance": 5,
                "urgency": 5,
                "rationale": f"No active goals in '{cat}' — potential gap detected.",
                "priority_score": self.compute_priority_score(5, 5),
            })
        return suggestions

    # ── Goal Retrospective ───────────────────────────────────────

    async def run_retrospective(self, goal_id: str) -> Optional[dict[str, Any]]:
        """Auto-analyse a completed goal and extract lessons."""
        goal = self.get_goal(goal_id)
        if not goal or goal.status not in ("completed", "abandoned"):
            return None

        # Gather timeline data
        events = self.get_goal_events(goal_id, limit=50)
        milestones = self.get_milestones(goal_id)
        estimation = self.estimate_completion(goal_id)

        try:
            created_dt = datetime.fromisoformat(goal.created_at)
            ended_dt = datetime.fromisoformat(goal.completed_at or _now_iso())
            duration_days = (ended_dt - created_dt).total_seconds() / 86400
        except ValueError:
            duration_days = 0.0

        # Velocity
        velocity_avg = estimation.get("velocity_per_day", 0.0) or 0.0

        # Use LLM for rich retrospective if available
        if self._llm:
            retro = await self._llm_retrospective(goal, events, milestones, duration_days)
        else:
            retro = self._offline_retrospective(goal, events, duration_days)

        retro_id = f"retro_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        self.conn.execute(
            """INSERT INTO goal_retrospectives
               (id, goal_id, duration_days, completion_accuracy,
                lessons, successes, obstacles, velocity_avg, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                retro_id, goal_id,
                round(duration_days, 2),
                retro.get("completion_accuracy", 0.0),
                json.dumps(retro.get("lessons", [])),
                json.dumps(retro.get("successes", [])),
                json.dumps(retro.get("obstacles", [])),
                round(velocity_avg, 4),
                now,
            ),
        )
        self._log_event(goal_id, "retrospective", f"Retrospective completed ({duration_days:.1f}d)")
        self.conn.commit()

        # Store lessons in memory engine if available
        if self._memory and retro.get("lessons"):
            for lesson in retro["lessons"][:3]:
                try:
                    self._memory.store(
                        content=f"[Goal Lesson] {goal.title}: {lesson}",
                        tags=["goal", "lesson", goal.category],
                        source="goal_retrospective",
                        confidence=0.8,
                    )
                except Exception:
                    pass

        return {
            "retrospective_id": retro_id,
            "goal_id": goal_id,
            "title": goal.title,
            "duration_days": round(duration_days, 2),
            "velocity_avg": round(velocity_avg, 4),
            **retro,
        }

    async def _llm_retrospective(
        self,
        goal: Goal,
        events: list[dict[str, Any]],
        milestones: list[dict[str, Any]],
        duration_days: float,
    ) -> dict[str, Any]:
        prompt = (
            f"Analyse this completed goal and produce a structured retrospective.\n\n"
            f"GOAL: {goal.title}\n"
            f"DESCRIPTION: {goal.description}\n"
            f"CATEGORY: {goal.category}\n"
            f"STATUS: {goal.status}\n"
            f"DURATION: {duration_days:.1f} days\n"
            f"FINAL PROGRESS: {goal.progress:.0%}\n\n"
            f"KEY EVENTS (latest 10):\n"
            + "\n".join(f"- [{e['event_type']}] {e['description']}" for e in events[:10])
            + "\n\nReturn ONLY valid JSON (no markdown):\n"
            '{"lessons": ["..."], "successes": ["..."], "obstacles": ["..."], '
            '"completion_accuracy": 0.8, "summary": "..."}'
        )
        try:
            response = await self._llm.complete(
                system="You analyse completed goals and extract actionable lessons.",
                messages=[{"role": "user", "content": prompt}],
                model_tier="fast",
                max_tokens=800,
            )
            raw = response.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            return json.loads(raw)
        except Exception as exc:
            logger.warning("LLM retrospective failed: %s", exc)
            return self._offline_retrospective(goal, events, duration_days)

    def _offline_retrospective(
        self,
        goal: Goal,
        events: list[dict[str, Any]],
        duration_days: float,
    ) -> dict[str, Any]:
        lessons: list[str] = []
        obstacles: list[str] = []
        successes: list[str] = []

        if goal.status == "abandoned":
            obstacles.append("Goal was abandoned before completion.")
            lessons.append("Review scope and resources before starting similar goals.")
        else:
            successes.append(f"Goal completed in {duration_days:.1f} days.")
            if goal.tasks_completed > 0:
                successes.append(f"Completed {goal.tasks_completed}/{goal.tasks_generated} tasks.")

        stall_events = [e for e in events if "stall" in e.get("event_type", "").lower()]
        if stall_events:
            obstacles.append(f"Goal stalled {len(stall_events)} time(s).")
            lessons.append("Break future goals into smaller chunks to avoid stalling.")

        accuracy = goal.progress if goal.status == "completed" else 0.0
        return {
            "lessons": lessons, "successes": successes, "obstacles": obstacles,
            "completion_accuracy": round(accuracy, 3),
            "summary": f"Goal '{goal.title}' — {goal.status} after {duration_days:.1f}d.",
        }

    def get_retrospectives(self, goal_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        """Retrieve retrospective records."""
        if goal_id:
            rows = self.conn.execute(
                "SELECT * FROM goal_retrospectives WHERE goal_id = ? ORDER BY created_at DESC LIMIT ?",
                (goal_id, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM goal_retrospectives ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        def _loads(val: Any) -> list:
            try:
                return json.loads(val or "[]")
            except (json.JSONDecodeError, TypeError):
                return []

        return [
            {
                "id": r["id"], "goal_id": r["goal_id"],
                "duration_days": r["duration_days"],
                "completion_accuracy": r["completion_accuracy"],
                "velocity_avg": r["velocity_avg"],
                "lessons": _loads(r["lessons"]),
                "successes": _loads(r["successes"]),
                "obstacles": _loads(r["obstacles"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    # ── Helpers ───────────────────────────────────────────────────

    def _log_event(self, goal_id: str, event_type: str, description: str) -> None:
        self.conn.execute(
            "INSERT INTO goal_events (id, goal_id, event_type, description, created_at) VALUES (?, ?, ?, ?, ?)",
            (f"ge_{uuid.uuid4().hex[:12]}", goal_id, event_type, description[:500], _now_iso()),
        )

    def _row_to_goal(self, row: sqlite3.Row) -> Goal:
        def _load_json_list(key: str) -> list:
            try:
                return json.loads(row[key] or "[]")
            except (json.JSONDecodeError, TypeError, IndexError):
                return []

        def _load_json_dict(key: str) -> dict:
            try:
                return json.loads(row[key] or "{}")
            except (json.JSONDecodeError, TypeError, IndexError):
                return {}

        # Safely read v1.1 columns (may be absent in old rows)
        def _safe_int(key: str, default: int) -> int:
            try:
                v = row[key]
                return int(v) if v is not None else default
            except (IndexError, TypeError):
                return default

        def _safe_float(key: str, default: float) -> float:
            try:
                v = row[key]
                return float(v) if v is not None else default
            except (IndexError, TypeError):
                return default

        return Goal(
            id=row["id"], title=row["title"],
            description=row["description"] or "",
            priority=row["priority"], status=row["status"],
            source=row["source"] or "user",
            category=row["category"] or "general",
            progress=row["progress"] or 0.0,
            milestones=tuple(_load_json_list("milestones")),
            completed_milestones=tuple(_load_json_list("completed_milestones")),
            tasks_generated=row["tasks_generated"] or 0,
            tasks_completed=row["tasks_completed"] or 0,
            deadline=row["deadline"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            completed_at=row["completed_at"],
            metadata=_load_json_dict("metadata"),
            depends_on=tuple(_load_json_list("depends_on")),
            importance=_safe_int("importance", 5),
            urgency=_safe_int("urgency", 5),
            resources=tuple(_load_json_list("resources")),
            priority_score=_safe_float("priority_score", 0.0),
        )
