"""Tests for the Persistent Task Queue — enqueue, dequeue, crash recovery,
priority levels, exponential backoff, timeouts, dependencies, progress,
dead letter queue, and statistics.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from backend.core.task_queue import (
    PRIORITY_CRITICAL,
    PRIORITY_HIGH,
    PRIORITY_LOW,
    PRIORITY_MEDIUM,
    DeadLetterTask,
    TaskQueue,
    TASK_QUEUE_DB,
    priority_from_name,
)


@pytest.fixture
def task_queue(tmp_path):
    db_path = tmp_path / "test_task_queue.db"
    with patch("backend.core.task_queue.TASK_QUEUE_DB", db_path):
        tq = TaskQueue()
        tq.start()
        yield tq
        tq.stop()


class TestTaskQueueEnqueue:
    def test_enqueue_and_dequeue(self, task_queue):
        task = task_queue.enqueue(goal="Research AI trends", priority=3)
        assert task.id.startswith("qt_")
        assert task.status == "pending"
        assert task.goal == "Research AI trends"

        pending = task_queue.dequeue(limit=5)
        assert len(pending) == 1
        assert pending[0].id == task.id

    def test_priority_ordering(self, task_queue):
        task_queue.enqueue(goal="Low priority task", priority=9)
        task_queue.enqueue(goal="High priority task", priority=1)
        task_queue.enqueue(goal="Normal priority task", priority=5)

        pending = task_queue.dequeue(limit=10)
        assert pending[0].goal == "High priority task"
        assert pending[1].goal == "Normal priority task"
        assert pending[2].goal == "Low priority task"

    def test_stats(self, task_queue):
        task_queue.enqueue(goal="Task 1")
        task_queue.enqueue(goal="Task 2")
        stats = task_queue.stats()
        assert stats["total_tasks"] == 2
        assert stats["by_status"]["pending"] == 2


class TestTaskQueueLifecycle:
    def test_mark_running_and_completed(self, task_queue):
        task = task_queue.enqueue(goal="Do something important now")
        run = task_queue.mark_running(task.id)
        assert run is not None
        assert run.status == "running"

        task_queue.mark_completed(task.id, run.id, "Done successfully")
        updated = task_queue.get_task(task.id)
        assert updated.status == "completed"
        assert updated.result == "Done successfully"

    def test_mark_failed_with_retry(self, task_queue):
        task = task_queue.enqueue(goal="Might fail task here", max_retries=2)
        run = task_queue.mark_running(task.id)
        should_retry = task_queue.mark_failed(task.id, run.id, "Connection error")
        assert should_retry is True

        updated = task_queue.get_task(task.id)
        assert updated.status == "pending"
        assert updated.retry_count == 1

    def test_mark_failed_exhausted_retries(self, task_queue):
        task = task_queue.enqueue(goal="Will fail permanently here", max_retries=1)
        run = task_queue.mark_running(task.id)
        should_retry = task_queue.mark_failed(task.id, run.id, "Fatal error")
        assert should_retry is False

        updated = task_queue.get_task(task.id)
        assert updated.status == "failed"

    def test_cancel(self, task_queue):
        task = task_queue.enqueue(goal="Cancel me please now")
        assert task_queue.cancel(task.id) is True
        updated = task_queue.get_task(task.id)
        assert updated.status == "cancelled"


class TestCrashRecovery:
    def test_recover_interrupted(self, task_queue):
        task = task_queue.enqueue(goal="Will be interrupted by crash")
        task_queue.mark_running(task.id)

        # Simulate crash: directly set status to running in DB
        running = task_queue.get_task(task.id)
        assert running.status == "running"

        # Create a new TaskQueue (simulates restart)
        recovered = task_queue._recover_interrupted()
        updated = task_queue.get_task(task.id)
        assert updated.status == "pending"


# ── Priority levels ──────────────────────────────────────────────


class TestPriorityLevels:
    def test_priority_constants_order(self):
        assert PRIORITY_CRITICAL < PRIORITY_HIGH < PRIORITY_MEDIUM < PRIORITY_LOW

    def test_priority_from_name_valid(self):
        assert priority_from_name("critical") == PRIORITY_CRITICAL
        assert priority_from_name("HIGH") == PRIORITY_HIGH
        assert priority_from_name("Medium") == PRIORITY_MEDIUM
        assert priority_from_name("low") == PRIORITY_LOW

    def test_priority_from_name_invalid(self):
        with pytest.raises(ValueError, match="Unknown priority name"):
            priority_from_name("urgent")

    def test_enqueue_with_named_priority(self, task_queue):
        task = task_queue.enqueue(
            goal="Critical task", priority=priority_from_name("critical")
        )
        assert task.priority == PRIORITY_CRITICAL

    def test_dequeue_respects_priority_levels(self, task_queue):
        task_queue.enqueue(goal="low job", priority=PRIORITY_LOW)
        task_queue.enqueue(goal="critical job", priority=PRIORITY_CRITICAL)
        task_queue.enqueue(goal="high job", priority=PRIORITY_HIGH)

        pending = task_queue.dequeue(limit=10)
        goals = [t.goal for t in pending]
        assert goals.index("critical job") < goals.index("high job")
        assert goals.index("high job") < goals.index("low job")


# ── Exponential backoff ───────────────────────────────────────────


class TestExponentialBackoff:
    def test_first_retry_sets_next_retry_at(self, task_queue):
        task = task_queue.enqueue(goal="Flaky task", max_retries=3, retry_delay_seconds=10.0)
        run = task_queue.mark_running(task.id)
        task_queue.mark_failed(task.id, run.id, "transient error")

        updated = task_queue.get_task(task.id)
        assert updated.status == "pending"
        assert updated.next_retry_at is not None
        retry_time = datetime.fromisoformat(updated.next_retry_at)
        assert retry_time > datetime.now(timezone.utc)

    def test_backoff_delay_grows_exponentially(self, task_queue):
        task = task_queue.enqueue(goal="Exp backoff", max_retries=5, retry_delay_seconds=4.0)

        # First failure: delay = 4 * 2^0 = 4s
        run1 = task_queue.mark_running(task.id)
        task_queue.mark_failed(task.id, run1.id, "err1")
        t1 = task_queue.get_task(task.id)
        delay1 = datetime.fromisoformat(t1.next_retry_at) - datetime.now(timezone.utc)

        # Force next retry to be immediate, then fail again
        task_queue.conn.execute(
            "UPDATE queued_tasks SET next_retry_at = NULL WHERE id = ?", (task.id,)
        )
        task_queue.conn.commit()

        # Second failure: delay = 4 * 2^1 = 8s
        run2 = task_queue.mark_running(task.id)
        task_queue.mark_failed(task.id, run2.id, "err2")
        t2 = task_queue.get_task(task.id)
        delay2 = datetime.fromisoformat(t2.next_retry_at) - datetime.now(timezone.utc)

        assert delay2.total_seconds() > delay1.total_seconds()

    def test_tasks_gated_by_next_retry_at_not_dequeued(self, task_queue):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        task = task_queue.enqueue(goal="Backoff gated task")
        # Manually set a far-future next_retry_at
        task_queue.conn.execute(
            "UPDATE queued_tasks SET next_retry_at = ? WHERE id = ?",
            (future, task.id),
        )
        task_queue.conn.commit()

        pending = task_queue.dequeue(limit=10)
        assert all(t.id != task.id for t in pending)

    def test_task_dequeued_after_backoff_expires(self, task_queue):
        past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        task = task_queue.enqueue(goal="Ready after backoff")
        task_queue.conn.execute(
            "UPDATE queued_tasks SET next_retry_at = ? WHERE id = ?",
            (past, task.id),
        )
        task_queue.conn.commit()

        pending = task_queue.dequeue(limit=10)
        assert any(t.id == task.id for t in pending)


# ── Timeout handling ──────────────────────────────────────────────


class TestTimeoutHandling:
    def test_enqueue_stores_timeout(self, task_queue):
        task = task_queue.enqueue(goal="Timeout task", timeout_seconds=60.0)
        assert task.timeout_seconds == 60.0

    def test_no_timeout_by_default(self, task_queue):
        task = task_queue.enqueue(goal="No timeout task")
        assert task.timeout_seconds is None

    def test_detect_timed_out_returns_stalled_task(self, task_queue):
        task = task_queue.enqueue(goal="Stalled task", timeout_seconds=1.0)
        task_queue.mark_running(task.id)

        # Backdate started_at to simulate stall
        past_start = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        task_queue.conn.execute(
            "UPDATE queued_tasks SET started_at = ? WHERE id = ?",
            (past_start, task.id),
        )
        task_queue.conn.commit()

        timed_out = task_queue.detect_timed_out()
        ids = [t.id for t in timed_out]
        assert task.id in ids

    def test_not_timed_out_when_within_limit(self, task_queue):
        task = task_queue.enqueue(goal="Fresh running task", timeout_seconds=3600.0)
        task_queue.mark_running(task.id)

        timed_out = task_queue.detect_timed_out()
        assert all(t.id != task.id for t in timed_out)

    def test_no_timeout_tasks_not_detected(self, task_queue):
        task = task_queue.enqueue(goal="No timeout set")
        task_queue.mark_running(task.id)
        past_start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        task_queue.conn.execute(
            "UPDATE queued_tasks SET started_at = ? WHERE id = ?",
            (past_start, task.id),
        )
        task_queue.conn.commit()

        timed_out = task_queue.detect_timed_out()
        assert all(t.id != task.id for t in timed_out)


# ── Task dependencies ─────────────────────────────────────────────


class TestTaskDependencies:
    def test_enqueue_stores_depends_on(self, task_queue):
        dep = task_queue.enqueue(goal="Prerequisite task")
        task = task_queue.enqueue(goal="Dependent task", depends_on=[dep.id])
        assert task.depends_on == [dep.id]

    def test_dependent_task_not_dequeued_until_dep_completes(self, task_queue):
        dep = task_queue.enqueue(goal="Dep")
        task = task_queue.enqueue(goal="Downstream", depends_on=[dep.id])

        # dep is still pending — downstream should not appear
        pending = task_queue.dequeue(limit=10)
        ids = [t.id for t in pending]
        assert task.id not in ids

    def test_dependent_task_dequeued_after_dep_completes(self, task_queue):
        dep = task_queue.enqueue(goal="Dep2")
        run = task_queue.mark_running(dep.id)
        task_queue.mark_completed(dep.id, run.id, "done")

        task = task_queue.enqueue(goal="Downstream2", depends_on=[dep.id])
        pending = task_queue.dequeue(limit=10)
        ids = [t.id for t in pending]
        assert task.id in ids

    def test_no_depends_on_always_dequeued(self, task_queue):
        task = task_queue.enqueue(goal="Independent task")
        pending = task_queue.dequeue(limit=10)
        assert any(t.id == task.id for t in pending)

    def test_multiple_dependencies_all_must_complete(self, task_queue):
        dep1 = task_queue.enqueue(goal="Dep A")
        dep2 = task_queue.enqueue(goal="Dep B")
        task = task_queue.enqueue(goal="Needs both", depends_on=[dep1.id, dep2.id])

        # Complete only dep1
        run = task_queue.mark_running(dep1.id)
        task_queue.mark_completed(dep1.id, run.id, "done A")

        pending = task_queue.dequeue(limit=10)
        assert task.id not in [t.id for t in pending]

        # Complete dep2 too
        run2 = task_queue.mark_running(dep2.id)
        task_queue.mark_completed(dep2.id, run2.id, "done B")

        pending2 = task_queue.dequeue(limit=10)
        assert task.id in [t.id for t in pending2]


# ── Progress tracking ─────────────────────────────────────────────


class TestProgressTracking:
    def test_initial_progress_is_zero(self, task_queue):
        task = task_queue.enqueue(goal="Progress task")
        assert task.progress == 0

    def test_update_progress_running_task(self, task_queue):
        task = task_queue.enqueue(goal="Long task")
        task_queue.mark_running(task.id)
        result = task_queue.update_progress(task.id, 42)
        assert result is True

        updated = task_queue.get_task(task.id)
        assert updated.progress == 42

    def test_progress_clamped_to_0_100(self, task_queue):
        task = task_queue.enqueue(goal="Clamp test")
        task_queue.mark_running(task.id)
        task_queue.update_progress(task.id, 150)
        assert task_queue.get_task(task.id).progress == 100

        task_queue.update_progress(task.id, -10)
        assert task_queue.get_task(task.id).progress == 0

    def test_update_progress_returns_false_for_non_running(self, task_queue):
        task = task_queue.enqueue(goal="Pending task")
        result = task_queue.update_progress(task.id, 50)
        assert result is False

    def test_progress_survives_get_task(self, task_queue):
        task = task_queue.enqueue(goal="Persist progress")
        task_queue.mark_running(task.id)
        task_queue.update_progress(task.id, 75)
        fetched = task_queue.get_task(task.id)
        assert fetched.progress == 75


# ── Dead letter queue ─────────────────────────────────────────────


class TestDeadLetterQueue:
    def test_permanently_failed_task_moves_to_dlq(self, task_queue):
        task = task_queue.enqueue(goal="Will die", max_retries=1)
        run = task_queue.mark_running(task.id)
        task_queue.mark_failed(task.id, run.id, "fatal error")

        dlq = task_queue.get_dead_letter()
        assert len(dlq) == 1
        entry = dlq[0]
        assert isinstance(entry, DeadLetterTask)
        assert entry.original_task_id == task.id
        assert entry.goal == "Will die"
        assert "fatal error" in (entry.last_error or "")

    def test_retryable_failure_not_in_dlq(self, task_queue):
        task = task_queue.enqueue(goal="Retry task", max_retries=3)
        run = task_queue.mark_running(task.id)
        task_queue.mark_failed(task.id, run.id, "transient")

        dlq = task_queue.get_dead_letter()
        assert len(dlq) == 0

    def test_requeue_dead_creates_new_task(self, task_queue):
        task = task_queue.enqueue(goal="Requeue me", max_retries=1)
        run = task_queue.mark_running(task.id)
        task_queue.mark_failed(task.id, run.id, "err")

        dlq = task_queue.get_dead_letter()
        assert len(dlq) == 1
        new_task = task_queue.requeue_dead(dlq[0].id)

        assert new_task is not None
        assert new_task.id != task.id
        assert new_task.goal == "Requeue me"
        assert new_task.status == "pending"

    def test_requeue_increments_requeue_count(self, task_queue):
        task = task_queue.enqueue(goal="Count requeues", max_retries=1)
        run = task_queue.mark_running(task.id)
        task_queue.mark_failed(task.id, run.id, "err")

        dlq = task_queue.get_dead_letter()
        dlq_id = dlq[0].id
        task_queue.requeue_dead(dlq_id)
        task_queue.requeue_dead(dlq_id)

        updated_dlq = task_queue.get_dead_letter()
        entry = next(e for e in updated_dlq if e.id == dlq_id)
        assert entry.requeue_count == 2

    def test_requeue_dead_returns_none_for_invalid_id(self, task_queue):
        result = task_queue.requeue_dead("dlq_nonexistent")
        assert result is None

    def test_purge_dead_letter(self, task_queue):
        task = task_queue.enqueue(goal="Old dead task", max_retries=1)
        run = task_queue.mark_running(task.id)
        task_queue.mark_failed(task.id, run.id, "err")

        # Backdate the failed_at timestamp
        old_date = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        task_queue.conn.execute(
            "UPDATE dead_letter_queue SET failed_at = ?", (old_date,)
        )
        task_queue.conn.commit()

        deleted = task_queue.purge_dead_letter(older_than_days=90)
        assert deleted == 1
        assert len(task_queue.get_dead_letter()) == 0


# ── Task statistics ───────────────────────────────────────────────


class TestTaskStatistics:
    def test_stats_basic_shape(self, task_queue):
        s = task_queue.stats()
        required_keys = {
            "total_tasks", "by_status", "total_runs",
            "queue_depth", "running_count", "avg_execution_seconds",
            "success_rate", "dlq_size", "priority_breakdown",
            "backoff_waiting", "dependency_blocked",
        }
        assert required_keys.issubset(s.keys())

    def test_queue_depth_matches_pending_count(self, task_queue):
        task_queue.enqueue(goal="A")
        task_queue.enqueue(goal="B")
        s = task_queue.stats()
        assert s["queue_depth"] == 2
        assert s["total_tasks"] == 2

    def test_running_count(self, task_queue):
        task = task_queue.enqueue(goal="Running job")
        task_queue.mark_running(task.id)
        s = task_queue.stats()
        assert s["running_count"] == 1

    def test_success_rate_100_percent(self, task_queue):
        task = task_queue.enqueue(goal="Will succeed")
        run = task_queue.mark_running(task.id)
        task_queue.mark_completed(task.id, run.id, "ok")

        s = task_queue.stats()
        assert s["success_rate"] == 1.0

    def test_success_rate_50_percent(self, task_queue):
        t1 = task_queue.enqueue(goal="Success", max_retries=1)
        r1 = task_queue.mark_running(t1.id)
        task_queue.mark_completed(t1.id, r1.id, "ok")

        t2 = task_queue.enqueue(goal="Failure", max_retries=1)
        r2 = task_queue.mark_running(t2.id)
        task_queue.mark_failed(t2.id, r2.id, "err")

        s = task_queue.stats()
        assert s["success_rate"] == pytest.approx(0.5, abs=0.01)

    def test_success_rate_none_when_no_terminal_tasks(self, task_queue):
        task_queue.enqueue(goal="Still pending")
        s = task_queue.stats()
        assert s["success_rate"] is None

    def test_dlq_size_increments(self, task_queue):
        task = task_queue.enqueue(goal="DLQ task", max_retries=1)
        run = task_queue.mark_running(task.id)
        task_queue.mark_failed(task.id, run.id, "err")
        s = task_queue.stats()
        assert s["dlq_size"] == 1

    def test_priority_breakdown_in_stats(self, task_queue):
        task_queue.enqueue(goal="Crit", priority=PRIORITY_CRITICAL)
        task_queue.enqueue(goal="High", priority=PRIORITY_HIGH)
        task_queue.enqueue(goal="Med",  priority=PRIORITY_MEDIUM)
        s = task_queue.stats()
        pb = s["priority_breakdown"]
        assert pb.get("critical", 0) >= 1
        assert pb.get("high", 0) >= 1
        assert pb.get("medium", 0) >= 1

    def test_backoff_waiting_count(self, task_queue):
        task = task_queue.enqueue(goal="Backoff task")
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        task_queue.conn.execute(
            "UPDATE queued_tasks SET next_retry_at = ? WHERE id = ?",
            (future, task.id),
        )
        task_queue.conn.commit()
        s = task_queue.stats()
        assert s["backoff_waiting"] >= 1

    def test_avg_execution_seconds(self, task_queue):
        task = task_queue.enqueue(goal="Timed task")
        run = task_queue.mark_running(task.id)
        # Manually set a known duration
        task_queue.conn.execute(
            "UPDATE task_runs SET duration_seconds = 2.5 WHERE id = ?", (run.id,)
        )
        task_queue.conn.execute(
            "UPDATE task_runs SET status = 'completed' WHERE id = ?", (run.id,)
        )
        task_queue.conn.commit()
        s = task_queue.stats()
        assert s["avg_execution_seconds"] == pytest.approx(2.5, abs=0.01)
