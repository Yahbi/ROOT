"""
Persistent Task Queue — SQLite-backed task persistence with advanced features.

Tasks survive server restarts. On startup, incomplete tasks are resumed.
Autonomous goals, scheduled jobs, and recurring tasks all persist here.

Features:
- Priority levels: CRITICAL(1), HIGH(2), MEDIUM(5), LOW(9)
- Exponential backoff retry with configurable base delay
- Timeout detection for stalled running tasks
- Task dependencies (task waits until all deps complete)
- Progress tracking (0-100%)
- Dead letter queue for permanently failed tasks
- Rich statistics: avg execution time, success rate, queue depth, throughput

Tables:
- queued_tasks: High-level goals with status, priority, schedule
- task_runs: Execution attempts with results and timing
- dead_letter_queue: Permanently failed tasks moved out of main queue
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from backend.config import ROOT_DIR

logger = logging.getLogger("root.task_queue")

# ── Priority level constants ──────────────────────────────────────

PRIORITY_CRITICAL = 1   # System-critical; processed before all others
PRIORITY_HIGH     = 2   # Important user-facing or time-sensitive work
PRIORITY_MEDIUM   = 5   # Default; normal autonomous tasks
PRIORITY_LOW      = 9   # Background housekeeping, non-urgent work


def priority_from_name(name: str) -> int:
    """Return the integer priority for a named level (case-insensitive).

    Accepts: 'critical', 'high', 'medium', 'low'.
    Raises ValueError for unknown names.
    """
    _map = {
        "critical": PRIORITY_CRITICAL,
        "high":     PRIORITY_HIGH,
        "medium":   PRIORITY_MEDIUM,
        "low":      PRIORITY_LOW,
    }
    try:
        return _map[name.lower()]
    except KeyError:
        raise ValueError(
            f"Unknown priority name '{name}'. "
            f"Valid names: {list(_map)}"
        )


def _next_cron_run(cron_expr: str) -> Optional[str]:
    """Compute the next run time from a simple cron expression.

    Supports: '*/N * * * *' (every N minutes), '0 */N * * *' (every N hours),
    '0 0 * * *' (daily), '0 0 * * 0' (weekly). Returns ISO timestamp or None.
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return None

    now = datetime.now(timezone.utc)
    minute_part, hour_part, _dom, _month, dow_part = parts

    try:
        if minute_part.startswith("*/"):
            interval_min = int(minute_part[2:])
            from datetime import timedelta
            return (now + timedelta(minutes=interval_min)).isoformat()

        if hour_part.startswith("*/"):
            interval_hr = int(hour_part[2:])
            from datetime import timedelta
            next_time = now.replace(minute=int(minute_part), second=0, microsecond=0)
            next_time = next_time + timedelta(hours=interval_hr)
            if next_time <= now:
                next_time = next_time + timedelta(hours=interval_hr)
            return next_time.isoformat()

        # Daily: '0 0 * * *'
        if _dom == "*" and _month == "*" and dow_part == "*":
            from datetime import timedelta
            next_time = now.replace(
                hour=int(hour_part), minute=int(minute_part),
                second=0, microsecond=0,
            )
            if next_time <= now:
                next_time = next_time + timedelta(days=1)
            return next_time.isoformat()

        # Weekly: '0 0 * * 0' (dow 0=Sunday)
        if _dom == "*" and _month == "*" and dow_part.isdigit():
            from datetime import timedelta
            target_dow = int(dow_part)
            days_ahead = (target_dow - now.weekday()) % 7 or 7
            next_time = (now + timedelta(days=days_ahead)).replace(
                hour=int(hour_part), minute=int(minute_part),
                second=0, microsecond=0,
            )
            return next_time.isoformat()

    except (ValueError, TypeError):
        return None

    return None

TASK_QUEUE_DB = ROOT_DIR / "data" / "task_queue.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Data Models (immutable) ──────────────────────────────────────


@dataclass(frozen=True)
class QueuedTask:
    """A persistent task in the queue."""
    id: str
    goal: str
    priority: int = PRIORITY_MEDIUM  # use PRIORITY_* constants or 1–9
    status: str = "pending"  # pending | scheduled | running | completed | failed | cancelled
    source: str = "user"  # user | autonomous | proactive | scheduled | goal_engine
    schedule_cron: Optional[str] = None  # cron expression for recurring tasks
    next_run_at: Optional[str] = None
    max_retries: int = 2
    retry_count: int = 0
    # Exponential backoff: base delay doubles on each retry attempt
    retry_delay_seconds: float = 5.0   # base delay between retries (doubles each time)
    next_retry_at: Optional[str] = None  # ISO timestamp; None = ready immediately
    # Timeout: tasks running longer than this are considered stalled
    timeout_seconds: Optional[float] = None  # None = no timeout enforced
    # Dependencies: list of task IDs that must complete before this task runs
    depends_on: list[str] = field(default_factory=list)
    # Progress: 0–100 (caller updates via update_progress)
    progress: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass(frozen=True)
class TaskRun:
    """A single execution attempt of a queued task."""
    id: str
    task_id: str
    attempt: int
    status: str  # running | completed | failed
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: str = field(default_factory=_now_iso)
    completed_at: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class DeadLetterTask:
    """A task that exhausted all retries and was moved to the dead letter queue."""
    id: str
    original_task_id: str
    goal: str
    priority: int
    source: str
    retry_count: int
    last_error: Optional[str]
    metadata: dict[str, Any]
    created_at: str       # when original task was created
    failed_at: str        # when it was moved to the DLQ
    requeue_count: int = 0  # how many times it has been requeued from the DLQ


# ── Task Queue ────────────────────────────────────────────────────


class TaskQueue:
    """SQLite-backed persistent task queue with crash recovery."""

    MAX_QUEUE_SIZE = 1000

    def __init__(self) -> None:
        self._conn: Optional[sqlite3.Connection] = None

    # ── Lifecycle ─────────────────────────────────────────────────

    def start(self) -> None:
        """Initialize the task queue database."""
        TASK_QUEUE_DB.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(TASK_QUEUE_DB), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()
        recovered = self._recover_interrupted()
        logger.info("TaskQueue started (db=%s, recovered=%d)", TASK_QUEUE_DB, recovered)

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
            raise RuntimeError("TaskQueue not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS queued_tasks (
                id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                priority INTEGER DEFAULT 5,
                status TEXT DEFAULT 'pending',
                source TEXT DEFAULT 'user',
                schedule_cron TEXT,
                next_run_at TEXT,
                max_retries INTEGER DEFAULT 2,
                retry_count INTEGER DEFAULT 0,
                retry_delay_seconds REAL DEFAULT 5.0,
                next_retry_at TEXT,
                timeout_seconds REAL,
                depends_on TEXT DEFAULT '[]',
                progress INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}',
                result TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT
            );

            CREATE TABLE IF NOT EXISTS task_runs (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                attempt INTEGER DEFAULT 1,
                status TEXT NOT NULL,
                result TEXT,
                error TEXT,
                started_at TEXT NOT NULL,
                completed_at TEXT,
                duration_seconds REAL DEFAULT 0,
                FOREIGN KEY (task_id) REFERENCES queued_tasks(id)
            );

            CREATE TABLE IF NOT EXISTS dead_letter_queue (
                id TEXT PRIMARY KEY,
                original_task_id TEXT NOT NULL,
                goal TEXT NOT NULL,
                priority INTEGER DEFAULT 5,
                source TEXT DEFAULT 'user',
                retry_count INTEGER DEFAULT 0,
                last_error TEXT,
                metadata TEXT DEFAULT '{}',
                created_at TEXT NOT NULL,
                failed_at TEXT NOT NULL,
                requeue_count INTEGER DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_tasks_status
                ON queued_tasks(status);
            CREATE INDEX IF NOT EXISTS idx_tasks_priority
                ON queued_tasks(priority, created_at);
            CREATE INDEX IF NOT EXISTS idx_tasks_next_run
                ON queued_tasks(next_run_at);
            CREATE INDEX IF NOT EXISTS idx_tasks_next_retry
                ON queued_tasks(next_retry_at);
            CREATE INDEX IF NOT EXISTS idx_runs_task
                ON task_runs(task_id);
            CREATE INDEX IF NOT EXISTS idx_dlq_failed
                ON dead_letter_queue(failed_at);
        """)
        self._migrate_tables()

    def _migrate_tables(self) -> None:
        """Add new columns to existing databases (non-destructive migrations)."""
        existing: set[str] = set()
        for row in self.conn.execute("PRAGMA table_info(queued_tasks)"):
            existing.add(row["name"])

        migrations = [
            ("retry_delay_seconds", "REAL DEFAULT 5.0"),
            ("next_retry_at",       "TEXT"),
            ("timeout_seconds",     "REAL"),
            ("depends_on",          "TEXT DEFAULT '[]'"),
            ("progress",            "INTEGER DEFAULT 0"),
        ]
        for col, col_def in migrations:
            if col not in existing:
                self.conn.execute(
                    f"ALTER TABLE queued_tasks ADD COLUMN {col} {col_def}"
                )
                logger.debug("Migrated queued_tasks: added column %s", col)

        self.conn.commit()

    def _recover_interrupted(self) -> int:
        """Mark any 'running' tasks from a previous crash as 'pending' for retry."""
        cursor = self.conn.execute(
            "UPDATE queued_tasks SET status = 'pending' WHERE status = 'running'"
        )
        self.conn.commit()
        return cursor.rowcount

    # ── Enqueue / Dequeue ─────────────────────────────────────────

    def enqueue(
        self,
        goal: str,
        priority: int = PRIORITY_MEDIUM,
        source: str = "user",
        schedule_cron: Optional[str] = None,
        next_run_at: Optional[str] = None,
        max_retries: int = 2,
        retry_delay_seconds: float = 5.0,
        timeout_seconds: Optional[float] = None,
        depends_on: Optional[list[str]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> QueuedTask:
        """Add a task to the persistent queue.

        Args:
            goal: The task goal description.
            priority: Integer priority (use PRIORITY_* constants). Lower = higher priority.
            source: Originating component (user, autonomous, proactive, etc.).
            schedule_cron: Cron expression for recurring tasks.
            next_run_at: ISO timestamp for scheduled first run.
            max_retries: Maximum retry attempts before moving to dead letter queue.
            retry_delay_seconds: Base delay between retries; doubles on each attempt (exponential backoff).
            timeout_seconds: Max seconds a task may be in 'running' state; None disables timeout.
            depends_on: List of task IDs that must complete before this task is dequeued.
            metadata: Arbitrary key-value pairs stored alongside the task.
        """
        task_id = f"qt_{uuid.uuid4().hex[:12]}"
        now = _now_iso()
        meta_json = json.dumps(metadata or {})
        deps_json = json.dumps(depends_on or [])

        self.conn.execute(
            """INSERT INTO queued_tasks
               (id, goal, priority, status, source, schedule_cron, next_run_at,
                max_retries, retry_count, retry_delay_seconds, timeout_seconds,
                depends_on, progress, metadata, created_at)
               VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, 0, ?, ?, ?, 0, ?, ?)""",
            (task_id, goal[:5000], priority, source, schedule_cron,
             next_run_at, max_retries, retry_delay_seconds, timeout_seconds,
             deps_json, meta_json, now),
        )
        self.conn.commit()

        # Trim old completed tasks if queue gets too large
        total = self.conn.execute("SELECT COUNT(*) as c FROM queued_tasks").fetchone()["c"]
        if total > self.MAX_QUEUE_SIZE:
            self.conn.execute(
                """DELETE FROM queued_tasks WHERE id IN (
                    SELECT id FROM queued_tasks
                    WHERE status IN ('completed', 'cancelled')
                    ORDER BY completed_at ASC
                    LIMIT ?
                )""",
                (total - self.MAX_QUEUE_SIZE,),
            )
            self.conn.commit()

        return QueuedTask(
            id=task_id, goal=goal[:5000], priority=priority,
            source=source, schedule_cron=schedule_cron,
            next_run_at=next_run_at, max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            timeout_seconds=timeout_seconds,
            depends_on=depends_on or [],
            metadata=metadata or {}, created_at=now,
        )

    def dequeue(self, limit: int = 5) -> list[QueuedTask]:
        """Get the next runnable pending tasks ordered by priority.

        A task is runnable when:
        1. Its status is 'pending'.
        2. Its next_retry_at is NULL or in the past (exponential backoff gate).
        3. All tasks listed in depends_on have status = 'completed'.

        Tasks whose dependencies are not yet met are silently skipped.
        """
        now = _now_iso()
        rows = self.conn.execute(
            """SELECT * FROM queued_tasks
               WHERE status = 'pending'
               AND (next_retry_at IS NULL OR next_retry_at <= ?)
               ORDER BY priority ASC, created_at ASC
               LIMIT ?""",
            (now, limit * 4),   # fetch extra; dependency filter may reduce the set
        ).fetchall()

        result: list[QueuedTask] = []
        for row in rows:
            task = self._row_to_task(row)
            if self._dependencies_met(task):
                result.append(task)
                if len(result) >= limit:
                    break
        return result

    def _dependencies_met(self, task: QueuedTask) -> bool:
        """Return True if all dependency tasks have completed successfully."""
        if not task.depends_on:
            return True
        for dep_id in task.depends_on:
            dep_row = self.conn.execute(
                "SELECT status FROM queued_tasks WHERE id = ?", (dep_id,)
            ).fetchone()
            if dep_row is None or dep_row["status"] != "completed":
                return False
        return True

    def get_due_scheduled(self) -> list[QueuedTask]:
        """Get scheduled tasks that are due to run."""
        now = _now_iso()
        rows = self.conn.execute(
            """SELECT * FROM queued_tasks
               WHERE status = 'scheduled'
               AND next_run_at IS NOT NULL
               AND next_run_at <= ?
               ORDER BY priority ASC""",
            (now,),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    # ── Status Updates ────────────────────────────────────────────

    def mark_running(self, task_id: str) -> Optional[TaskRun]:
        """Mark a task as running and create a run record."""
        task = self.get_task(task_id)
        if not task:
            return None

        now = _now_iso()
        run_id = f"run_{uuid.uuid4().hex[:12]}"

        with self.conn:
            self.conn.execute(
                "UPDATE queued_tasks SET status = 'running', started_at = ? WHERE id = ?",
                (now, task_id),
            )
            self.conn.execute(
                """INSERT INTO task_runs (id, task_id, attempt, status, started_at)
                   VALUES (?, ?, ?, 'running', ?)""",
                (run_id, task_id, task.retry_count + 1, now),
            )

        return TaskRun(id=run_id, task_id=task_id,
                       attempt=task.retry_count + 1, status="running",
                       started_at=now)

    def mark_completed(self, task_id: str, run_id: str, result: str) -> None:
        """Mark a task and its run as completed."""
        now = _now_iso()

        # Calculate duration outside transaction (read-only)
        run = self.conn.execute(
            "SELECT started_at FROM task_runs WHERE id = ?", (run_id,)
        ).fetchone()
        duration = 0.0
        if run and run["started_at"]:
            try:
                start = datetime.fromisoformat(run["started_at"])
                duration = (datetime.now(timezone.utc) - start).total_seconds()
            except (ValueError, TypeError):
                logger.debug("(ValueError, TypeError) suppressed", exc_info=True)
        with self.conn:
            self.conn.execute(
                """UPDATE queued_tasks SET status = 'completed', result = ?,
                   completed_at = ? WHERE id = ?""",
                (result[:5000], now, task_id),
            )
            self.conn.execute(
                """UPDATE task_runs SET status = 'completed', result = ?,
                   completed_at = ?, duration_seconds = ? WHERE id = ?""",
                (result[:5000], now, duration, run_id),
            )

    def mark_failed(self, task_id: str, run_id: str, error: str) -> bool:
        """Mark a run as failed. Returns True if task will be retried.

        On retry the task is rescheduled with exponential backoff:
            next_retry_at = now + retry_delay_seconds * 2^(retry_count)

        When max_retries is exhausted the task moves to the dead letter queue.
        """
        now = _now_iso()
        task = self.get_task(task_id)
        if not task:
            return False

        new_retry_count = task.retry_count + 1
        should_retry = new_retry_count < task.max_retries

        # Compute exponential backoff timestamp for the next attempt
        backoff_delay = task.retry_delay_seconds * (2 ** task.retry_count)
        next_retry_at = (
            datetime.now(timezone.utc) + timedelta(seconds=backoff_delay)
        ).isoformat()

        with self.conn:
            self.conn.execute(
                """UPDATE task_runs SET status = 'failed', error = ?,
                   completed_at = ? WHERE id = ?""",
                (error[:2000], now, run_id),
            )
            if should_retry:
                self.conn.execute(
                    """UPDATE queued_tasks SET status = 'pending',
                       retry_count = ?, error = ?, next_retry_at = ? WHERE id = ?""",
                    (new_retry_count, error[:2000], next_retry_at, task_id),
                )
                logger.info(
                    "Task %s failed (attempt %d/%d); retry after %s",
                    task_id, new_retry_count, task.max_retries, next_retry_at,
                )
            else:
                self.conn.execute(
                    """UPDATE queued_tasks SET status = 'failed',
                       retry_count = ?, error = ?, completed_at = ? WHERE id = ?""",
                    (new_retry_count, error[:2000], now, task_id),
                )
                # Move to dead letter queue
                self._move_to_dlq(task, error[:2000], now)
                logger.warning(
                    "Task %s permanently failed after %d retries; moved to DLQ",
                    task_id, new_retry_count,
                )

        return should_retry

    def _move_to_dlq(self, task: QueuedTask, last_error: Optional[str], failed_at: str) -> None:
        """Insert a permanently-failed task into the dead letter queue."""
        dlq_id = f"dlq_{uuid.uuid4().hex[:12]}"
        self.conn.execute(
            """INSERT INTO dead_letter_queue
               (id, original_task_id, goal, priority, source,
                retry_count, last_error, metadata, created_at, failed_at, requeue_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)""",
            (
                dlq_id,
                task.id,
                task.goal[:5000],
                task.priority,
                task.source,
                task.retry_count,
                last_error,
                json.dumps(task.metadata),
                task.created_at,
                failed_at,
            ),
        )

    def cancel(self, task_id: str) -> bool:
        """Cancel a pending or running task."""
        cursor = self.conn.execute(
            """UPDATE queued_tasks SET status = 'cancelled', completed_at = ?
               WHERE id = ? AND status IN ('pending', 'running', 'scheduled')""",
            (_now_iso(), task_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    # ── Queries ───────────────────────────────────────────────────

    def get_task(self, task_id: str) -> Optional[QueuedTask]:
        row = self.conn.execute(
            "SELECT * FROM queued_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return self._row_to_task(row) if row else None

    def get_runs(self, task_id: str) -> list[TaskRun]:
        rows = self.conn.execute(
            "SELECT * FROM task_runs WHERE task_id = ? ORDER BY attempt", (task_id,)
        ).fetchall()
        return [
            TaskRun(
                id=r["id"], task_id=r["task_id"], attempt=r["attempt"],
                status=r["status"], result=r["result"], error=r["error"],
                started_at=r["started_at"], completed_at=r["completed_at"],
                duration_seconds=r["duration_seconds"] or 0.0,
            )
            for r in rows
        ]

    def get_pending(self, limit: int = 20) -> list[QueuedTask]:
        rows = self.conn.execute(
            """SELECT * FROM queued_tasks WHERE status IN ('pending', 'scheduled')
               ORDER BY priority ASC, created_at ASC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_active(self) -> list[QueuedTask]:
        rows = self.conn.execute(
            "SELECT * FROM queued_tasks WHERE status = 'running'"
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def get_recent(self, limit: int = 20) -> list[QueuedTask]:
        rows = self.conn.execute(
            "SELECT * FROM queued_tasks ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    def update_progress(self, task_id: str, progress: int) -> bool:
        """Set task progress (0–100). Returns False if task not found.

        Progress is clamped to [0, 100]. Useful for long-running tasks
        to surface partial completion state to callers.
        """
        clamped = max(0, min(100, progress))
        cursor = self.conn.execute(
            "UPDATE queued_tasks SET progress = ? WHERE id = ? AND status = 'running'",
            (clamped, task_id),
        )
        self.conn.commit()
        return cursor.rowcount > 0

    def detect_timed_out(self) -> list[QueuedTask]:
        """Return running tasks that have exceeded their timeout_seconds limit.

        Call from a background loop; then fail each returned task via mark_failed().
        Only tasks with a non-NULL timeout_seconds are considered.
        """
        now = datetime.now(timezone.utc)
        rows = self.conn.execute(
            """SELECT * FROM queued_tasks
               WHERE status = 'running'
               AND timeout_seconds IS NOT NULL
               AND started_at IS NOT NULL"""
        ).fetchall()

        timed_out: list[QueuedTask] = []
        for row in rows:
            try:
                started = datetime.fromisoformat(row["started_at"])
                elapsed = (now - started).total_seconds()
                if elapsed > row["timeout_seconds"]:
                    timed_out.append(self._row_to_task(row))
            except (ValueError, TypeError):
                continue
        return timed_out

    def stats(self) -> dict[str, Any]:
        """Return queue statistics: status breakdown, avg execution time, success rate, queue depth.

        Metrics:
        - total_tasks: all tasks ever enqueued (excluding purged)
        - by_status: count per status bucket
        - total_runs: total execution attempts across all tasks
        - queue_depth: tasks currently pending (ready to run)
        - running_count: tasks currently executing
        - avg_execution_seconds: mean duration of completed runs (last 500)
        - success_rate: fraction of completed tasks vs (completed + failed)
        - dlq_size: number of tasks in the dead letter queue
        - priority_breakdown: pending task counts by priority level
        - backoff_waiting: pending tasks gated by next_retry_at (not yet runnable)
        - dependency_blocked: pending tasks with unmet dependencies
        """
        now = _now_iso()

        # Status counts
        status_rows = self.conn.execute(
            "SELECT status, COUNT(*) as cnt FROM queued_tasks GROUP BY status"
        ).fetchall()
        by_status: dict[str, int] = {r["status"]: r["cnt"] for r in status_rows}

        total_tasks = sum(by_status.values())
        queue_depth = by_status.get("pending", 0)
        running_count = by_status.get("running", 0)

        # Average execution time (completed runs only, cap at 500 for performance)
        avg_row = self.conn.execute(
            """SELECT AVG(duration_seconds) as avg_dur
               FROM (
                   SELECT duration_seconds FROM task_runs
                   WHERE status = 'completed' AND duration_seconds > 0
                   ORDER BY started_at DESC LIMIT 500
               )"""
        ).fetchone()
        avg_exec = round(avg_row["avg_dur"] or 0.0, 3)

        # Success rate: completed / (completed + failed)
        completed = by_status.get("completed", 0)
        failed = by_status.get("failed", 0)
        denom = completed + failed
        success_rate = round(completed / denom, 4) if denom > 0 else None

        # Dead letter queue size
        dlq_row = self.conn.execute(
            "SELECT COUNT(*) as c FROM dead_letter_queue"
        ).fetchone()
        dlq_size = dlq_row["c"]

        # Total runs
        total_runs = self.conn.execute(
            "SELECT COUNT(*) as c FROM task_runs"
        ).fetchone()["c"]

        # Priority breakdown for pending tasks
        priority_rows = self.conn.execute(
            """SELECT priority, COUNT(*) as cnt FROM queued_tasks
               WHERE status = 'pending' GROUP BY priority ORDER BY priority"""
        ).fetchall()
        priority_labels = {
            PRIORITY_CRITICAL: "critical",
            PRIORITY_HIGH:     "high",
            PRIORITY_MEDIUM:   "medium",
            PRIORITY_LOW:      "low",
        }
        priority_breakdown: dict[str, int] = {}
        for pr in priority_rows:
            label = priority_labels.get(pr["priority"], str(pr["priority"]))
            priority_breakdown[label] = pr["cnt"]

        # Backoff-waiting: pending tasks not yet runnable due to next_retry_at
        backoff_row = self.conn.execute(
            """SELECT COUNT(*) as c FROM queued_tasks
               WHERE status = 'pending'
               AND next_retry_at IS NOT NULL AND next_retry_at > ?""",
            (now,),
        ).fetchone()
        backoff_waiting = backoff_row["c"]

        # Dependency-blocked estimate: pending tasks with non-empty depends_on
        dep_rows = self.conn.execute(
            """SELECT depends_on FROM queued_tasks WHERE status = 'pending'"""
        ).fetchall()
        dependency_blocked = sum(
            1 for r in dep_rows
            if r["depends_on"] and r["depends_on"] not in ("[]", "", None)
            and not self._all_deps_complete_raw(r["depends_on"])
        )

        return {
            "total_tasks":             total_tasks,
            "by_status":               by_status,
            "total_runs":              total_runs,
            "queue_depth":             queue_depth,
            "running_count":           running_count,
            "avg_execution_seconds":   avg_exec,
            "success_rate":            success_rate,
            "dlq_size":                dlq_size,
            "priority_breakdown":      priority_breakdown,
            "backoff_waiting":         backoff_waiting,
            "dependency_blocked":      dependency_blocked,
        }

    def _all_deps_complete_raw(self, deps_json: str) -> bool:
        """Return True if all task IDs in the JSON list have completed. Helper for stats."""
        try:
            dep_ids: list[str] = json.loads(deps_json)
        except (json.JSONDecodeError, TypeError):
            return True
        if not dep_ids:
            return True
        for dep_id in dep_ids:
            row = self.conn.execute(
                "SELECT status FROM queued_tasks WHERE id = ?", (dep_id,)
            ).fetchone()
            if row is None or row["status"] != "completed":
                return False
        return True

    # ── Dead Letter Queue ─────────────────────────────────────────

    def get_dead_letter(self, limit: int = 50) -> list[DeadLetterTask]:
        """Return entries from the dead letter queue, newest first."""
        rows = self.conn.execute(
            """SELECT * FROM dead_letter_queue ORDER BY failed_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [self._row_to_dlq(r) for r in rows]

    def requeue_dead(self, dlq_id: str, max_retries: int = 3) -> Optional[QueuedTask]:
        """Re-enqueue a dead letter task for another execution attempt.

        The original task is retained in the DLQ with requeue_count incremented.
        A fresh QueuedTask is created with retry_count reset to 0.

        Returns the new QueuedTask or None if dlq_id not found.
        """
        row = self.conn.execute(
            "SELECT * FROM dead_letter_queue WHERE id = ?", (dlq_id,)
        ).fetchone()
        if not row:
            return None

        try:
            meta: dict[str, Any] = json.loads(row["metadata"] or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}

        new_task = self.enqueue(
            goal=row["goal"],
            priority=row["priority"],
            source=row["source"],
            max_retries=max_retries,
            metadata={**meta, "requeued_from_dlq": dlq_id},
        )

        self.conn.execute(
            "UPDATE dead_letter_queue SET requeue_count = requeue_count + 1 WHERE id = ?",
            (dlq_id,),
        )
        self.conn.commit()

        logger.info("DLQ entry %s requeued as task %s", dlq_id, new_task.id)
        return new_task

    def purge_dead_letter(self, older_than_days: int = 90) -> int:
        """Delete DLQ entries older than N days. Returns count deleted."""
        cutoff = (datetime.now(timezone.utc) - timedelta(days=older_than_days)).isoformat()
        cursor = self.conn.execute(
            "DELETE FROM dead_letter_queue WHERE failed_at < ?", (cutoff,)
        )
        self.conn.commit()
        return cursor.rowcount

    def _row_to_dlq(self, row: sqlite3.Row) -> DeadLetterTask:
        try:
            meta: dict[str, Any] = json.loads(row["metadata"] or "{}")
        except (json.JSONDecodeError, TypeError):
            meta = {}
        return DeadLetterTask(
            id=row["id"],
            original_task_id=row["original_task_id"],
            goal=row["goal"],
            priority=row["priority"],
            source=row["source"] or "user",
            retry_count=row["retry_count"],
            last_error=row["last_error"],
            metadata=meta,
            created_at=row["created_at"],
            failed_at=row["failed_at"],
            requeue_count=row["requeue_count"] or 0,
        )

    # ── Scheduling ─────────────────────────────────────────────────

    def reschedule(self, task_id: str) -> Optional[QueuedTask]:
        """Re-enqueue a recurring task with the next cron-computed run time.

        After a cron-based task completes, call this to schedule the next run.
        Returns a new QueuedTask if rescheduled, or None if not recurring.
        """
        task = self.get_task(task_id)
        if not task or not task.schedule_cron:
            return None

        next_run = _next_cron_run(task.schedule_cron)
        if not next_run:
            logger.warning("Invalid cron expression '%s' for task %s", task.schedule_cron, task_id)
            return None

        return self.enqueue(
            goal=task.goal,
            priority=task.priority,
            source=task.source,
            schedule_cron=task.schedule_cron,
            next_run_at=next_run,
            max_retries=task.max_retries,
            metadata=task.metadata,
        )

    def activate_scheduled(self) -> list[QueuedTask]:
        """Move due scheduled tasks to 'pending' so they can be dequeued.

        Call this periodically (e.g. every minute) from a background loop.
        """
        now = _now_iso()
        self.conn.execute(
            """UPDATE queued_tasks SET status = 'pending'
               WHERE status = 'scheduled'
               AND next_run_at IS NOT NULL
               AND next_run_at <= ?""",
            (now,),
        )
        self.conn.commit()
        return self.get_due_scheduled()

    # ── Metadata & Source Queries ─────────────────────────────────

    def update_metadata(self, task_id: str, updates: dict[str, Any]) -> bool:
        """Merge new keys into a task's metadata dict."""
        task = self.get_task(task_id)
        if not task:
            return False

        merged = {**task.metadata, **updates}
        self.conn.execute(
            "UPDATE queued_tasks SET metadata = ? WHERE id = ?",
            (json.dumps(merged), task_id),
        )
        self.conn.commit()
        return True

    def get_by_source(self, source: str, limit: int = 50) -> list[QueuedTask]:
        """Get tasks by their originating source (goal_engine, trigger, etc.)."""
        rows = self.conn.execute(
            """SELECT * FROM queued_tasks WHERE source = ?
               ORDER BY created_at DESC LIMIT ?""",
            (source, limit),
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    _HISTORY_ALLOWED_STATUSES = frozenset({
        "pending", "scheduled", "running", "completed", "failed", "cancelled",
    })
    _HISTORY_ALLOWED_SOURCES = frozenset({
        "user", "autonomous", "proactive", "scheduled", "goal_engine",
    })

    def get_history(
        self,
        status: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 50,
    ) -> list[QueuedTask]:
        """Query completed/failed tasks for reporting and digest generation."""
        conditions = []
        params: list[Any] = []

        if status:
            if status not in self._HISTORY_ALLOWED_STATUSES:
                raise ValueError(f"Disallowed status filter: {status}")
            conditions.append("status = ?")
            params.append(status)
        else:
            conditions.append("status IN ('completed', 'failed', 'cancelled')")

        if source:
            if source not in self._HISTORY_ALLOWED_SOURCES:
                raise ValueError(f"Disallowed source filter: {source}")
            conditions.append("source = ?")
            params.append(source)

        where = " AND ".join(conditions)
        params.append(limit)

        rows = self.conn.execute(
            f"SELECT * FROM queued_tasks WHERE {where} ORDER BY completed_at DESC LIMIT ?",
            params,
        ).fetchall()
        return [self._row_to_task(r) for r in rows]

    # ── Maintenance ──────────────────────────────────────────────

    def purge(self, older_than_days: int = 30) -> int:
        """Delete completed/cancelled tasks and their runs older than N days.

        Returns the number of tasks deleted.
        """
        cutoff = datetime.now(timezone.utc)
        cutoff_iso = cutoff.isoformat().replace(
            cutoff.isoformat()[-6:], ""
        )  # rough cutoff
        from datetime import timedelta
        cutoff = cutoff - timedelta(days=older_than_days)
        cutoff_iso = cutoff.isoformat()

        # Delete orphaned runs first
        self.conn.execute(
            """DELETE FROM task_runs WHERE task_id IN (
                SELECT id FROM queued_tasks
                WHERE status IN ('completed', 'cancelled', 'failed')
                AND completed_at IS NOT NULL
                AND completed_at < ?
            )""",
            (cutoff_iso,),
        )

        cursor = self.conn.execute(
            """DELETE FROM queued_tasks
               WHERE status IN ('completed', 'cancelled', 'failed')
               AND completed_at IS NOT NULL
               AND completed_at < ?""",
            (cutoff_iso,),
        )
        self.conn.commit()
        deleted = cursor.rowcount
        if deleted:
            logger.info("Purged %d old tasks (older than %d days)", deleted, older_than_days)
        return deleted

    # ── Executor Bridge ──────────────────────────────────────────

    async def drain_to_executor(self, executor: Any, limit: int = 5) -> int:
        """Pull pending tasks from the queue and submit them to the TaskExecutor.

        This bridges persistent storage → in-memory execution. Call from a
        background loop to continuously process queued tasks.

        Returns the number of tasks submitted.
        """
        pending = self.dequeue(limit=limit)
        submitted = 0

        for queued_task in pending:
            run = self.mark_running(queued_task.id)
            if not run:
                continue

            try:
                atask = await executor.submit(
                    goal=queued_task.goal,
                    metadata={
                        **queued_task.metadata,
                        "queue_task_id": queued_task.id,
                        "queue_run_id": run.id,
                    },
                )
                self.update_metadata(queued_task.id, {"executor_task_id": atask.id})
                submitted = submitted + 1
                logger.info(
                    "Queued task %s → executor %s",
                    queued_task.id, atask.id,
                )
            except Exception as exc:
                error_msg = str(exc)[:500]
                should_retry = self.mark_failed(queued_task.id, run.id, error_msg)
                logger.warning(
                    "Failed to submit queued task %s: %s (retry=%s)",
                    queued_task.id, error_msg, should_retry,
                )

        return submitted

    async def sync_from_executor(self, executor: Any) -> int:
        """Sync completed executor tasks back to the persistent queue.

        Checks all running queue tasks to see if their executor counterpart
        has finished, and updates the queue accordingly.

        Returns the number of tasks synced.
        """
        active = self.get_active()
        synced = 0

        for queued_task in active:
            executor_id = queued_task.metadata.get("executor_task_id")
            run_id = queued_task.metadata.get("queue_run_id")
            if not executor_id or not run_id:
                continue

            etask = executor.get_task(executor_id)
            if not etask:
                continue

            if etask.status == "completed":
                result = etask.final_result or "Completed"
                self.mark_completed(queued_task.id, run_id, result)
                # Reschedule if recurring
                if queued_task.schedule_cron:
                    self.reschedule(queued_task.id)
                synced += 1

            elif etask.status == "failed":
                error = etask.final_result or "Execution failed"
                self.mark_failed(queued_task.id, run_id, error)
                synced += 1

        return synced

    # ── Helpers ───────────────────────────────────────────────────

    def _row_to_task(self, row: sqlite3.Row) -> QueuedTask:
        meta: dict[str, Any] = {}
        try:
            meta = json.loads(row["metadata"] or "{}")
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Failed to parse task metadata: %s", e)

        depends_on: list[str] = []
        try:
            raw_deps = row["depends_on"]
            if raw_deps:
                depends_on = json.loads(raw_deps)
        except (json.JSONDecodeError, TypeError):
            logger.debug("(json.JSONDecodeError, TypeError) suppressed", exc_info=True)
        return QueuedTask(
            id=row["id"],
            goal=row["goal"],
            priority=row["priority"],
            status=row["status"],
            source=row["source"] or "user",
            schedule_cron=row["schedule_cron"],
            next_run_at=row["next_run_at"],
            max_retries=row["max_retries"],
            retry_count=row["retry_count"],
            retry_delay_seconds=row["retry_delay_seconds"] or 5.0,
            next_retry_at=row["next_retry_at"],
            timeout_seconds=row["timeout_seconds"],
            depends_on=depends_on,
            progress=row["progress"] or 0,
            metadata=meta,
            result=row["result"],
            error=row["error"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
        )
