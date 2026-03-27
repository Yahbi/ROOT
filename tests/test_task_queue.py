"""Tests for the Persistent Task Queue — enqueue, dequeue, crash recovery."""

from __future__ import annotations

import tempfile
from unittest.mock import patch

import pytest

from backend.core.task_queue import TaskQueue, TASK_QUEUE_DB


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
