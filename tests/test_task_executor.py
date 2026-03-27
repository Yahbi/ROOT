"""Tests for backend.core.task_executor — autonomous goal decomposition engine."""

from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError, replace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.task_executor import (
    AutonomousTask,
    SubtaskState,
    TaskExecutor,
    TaskPlan,
    _now_iso,
)


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def executor():
    return TaskExecutor()


def _make_subtask(
    *,
    id: str = "sub_0",
    index: int = 0,
    description: str = "do something",
    agent_id: str = "researcher",
    status: str = "pending",
    depends_on: tuple[str, ...] = (),
    result: str | None = None,
    error: str | None = None,
) -> SubtaskState:
    return SubtaskState(
        id=id,
        index=index,
        description=description,
        agent_id=agent_id,
        status=status,
        depends_on=depends_on,
        result=result,
        error=error,
    )


def _make_task(
    *,
    id: str = "atask_test123",
    goal: str = "test goal",
    status: str = "pending",
    subtasks: tuple[SubtaskState, ...] = (),
    plan: TaskPlan | None = None,
    final_result: str | None = None,
) -> AutonomousTask:
    return AutonomousTask(
        id=id,
        goal=goal,
        status=status,
        subtasks=subtasks,
        plan=plan,
        final_result=final_result,
    )


# ── 1. Dataclass Immutability & Defaults ──────────────────────────


class TestDataclasses:
    def test_subtask_state_defaults(self):
        s = SubtaskState(id="s1", index=0, description="desc", agent_id="researcher")
        assert s.status == "pending"
        assert s.tools_hint == ()
        assert s.depends_on == ()
        assert s.risk_level == "low"
        assert s.result is None
        assert s.error is None
        assert s.attempt == 0
        assert s.started_at is None
        assert s.completed_at is None

    def test_subtask_state_frozen(self):
        s = SubtaskState(id="s1", index=0, description="desc", agent_id="researcher")
        with pytest.raises(FrozenInstanceError):
            s.status = "running"  # type: ignore[misc]

    def test_task_plan_defaults(self):
        plan = TaskPlan(subtasks=(), reasoning="none")
        assert plan.estimated_duration_seconds == 120
        assert plan.subtasks == ()

    def test_task_plan_frozen(self):
        plan = TaskPlan(subtasks=(), reasoning="none")
        with pytest.raises(FrozenInstanceError):
            plan.reasoning = "changed"  # type: ignore[misc]

    def test_autonomous_task_defaults(self):
        t = AutonomousTask(id="t1", goal="goal")
        assert t.status == "pending"
        assert t.plan is None
        assert t.subtasks == ()
        assert t.final_result is None
        assert t.created_at  # non-empty ISO string
        assert t.started_at is None
        assert t.completed_at is None
        assert t.metadata == {}

    def test_autonomous_task_frozen(self):
        t = AutonomousTask(id="t1", goal="goal")
        with pytest.raises(FrozenInstanceError):
            t.status = "completed"  # type: ignore[misc]

    def test_autonomous_task_metadata_separate_instances(self):
        """Each instance should get its own metadata dict (default_factory)."""
        t1 = AutonomousTask(id="t1", goal="g1")
        t2 = AutonomousTask(id="t2", goal="g2")
        assert t1.metadata is not t2.metadata


# ── 2. Stats ──────────────────────────────────────────────────────


class TestStats:
    def test_stats_empty(self, executor: TaskExecutor):
        s = executor.stats()
        assert s == {"total_tasks": 0, "active": 0, "by_status": {}}

    def test_stats_populated(self, executor: TaskExecutor):
        executor._tasks["a"] = _make_task(id="a", status="pending")
        executor._tasks["b"] = _make_task(id="b", status="executing")
        executor._tasks["c"] = _make_task(id="c", status="completed")
        executor._tasks["d"] = _make_task(id="d", status="failed")

        s = executor.stats()
        assert s["total_tasks"] == 4
        assert s["active"] == 2  # pending + executing
        assert s["by_status"] == {
            "pending": 1,
            "executing": 1,
            "completed": 1,
            "failed": 1,
        }


# ── 3. get_all / get_active ──────────────────────────────────────


class TestGetAllAndActive:
    def test_get_all_empty(self, executor: TaskExecutor):
        assert executor.get_all() == []

    def test_get_all_respects_limit(self, executor: TaskExecutor):
        for i in range(10):
            executor._tasks[f"t{i}"] = _make_task(id=f"t{i}", status="completed")
        assert len(executor.get_all(limit=3)) == 3

    def test_get_active_filters_correctly(self, executor: TaskExecutor):
        executor._tasks["a"] = _make_task(id="a", status="pending")
        executor._tasks["b"] = _make_task(id="b", status="planning")
        executor._tasks["c"] = _make_task(id="c", status="executing")
        executor._tasks["d"] = _make_task(id="d", status="completed")
        executor._tasks["e"] = _make_task(id="e", status="failed")
        executor._tasks["f"] = _make_task(id="f", status="cancelled")

        active = executor.get_active()
        active_ids = {t.id for t in active}
        assert active_ids == {"a", "b", "c"}


# ── 4. Decompose without LLM ─────────────────────────────────────


class TestDecompose:
    @pytest.mark.asyncio
    async def test_decompose_no_llm_fallback(self, executor: TaskExecutor):
        task = _make_task(goal="Research quantum computing")
        plan = await executor._decompose(task)

        assert isinstance(plan, TaskPlan)
        assert len(plan.subtasks) == 1
        assert plan.subtasks[0].agent_id == "researcher"
        assert plan.subtasks[0].description == "Research quantum computing"
        assert "No LLM" in plan.reasoning


# ── 5–7. Resolve Order ───────────────────────────────────────────


class TestResolveOrder:
    def test_resolve_order_no_deps(self, executor: TaskExecutor):
        """All subtasks with no dependencies should be in a single batch."""
        subtasks = (
            _make_subtask(id="s0", index=0),
            _make_subtask(id="s1", index=1),
            _make_subtask(id="s2", index=2),
        )
        batches = executor._resolve_order(subtasks)
        assert len(batches) == 1
        assert len(batches[0]) == 3

    def test_resolve_order_sequential_deps(self, executor: TaskExecutor):
        """Each subtask depends on the previous → one subtask per batch."""
        subtasks = (
            _make_subtask(id="s0", index=0),
            _make_subtask(id="s1", index=1, depends_on=("s0",)),
            _make_subtask(id="s2", index=2, depends_on=("s1",)),
        )
        batches = executor._resolve_order(subtasks)
        assert len(batches) == 3
        assert [b[0].id for b in batches] == ["s0", "s1", "s2"]

    def test_resolve_order_empty(self, executor: TaskExecutor):
        assert executor._resolve_order(()) == []

    def test_resolve_order_diamond_dependency(self, executor: TaskExecutor):
        """Diamond: s0 → s1, s0 → s2, s1+s2 → s3."""
        subtasks = (
            _make_subtask(id="s0", index=0),
            _make_subtask(id="s1", index=1, depends_on=("s0",)),
            _make_subtask(id="s2", index=2, depends_on=("s0",)),
            _make_subtask(id="s3", index=3, depends_on=("s1", "s2")),
        )
        batches = executor._resolve_order(subtasks)
        assert len(batches) == 3
        # batch 0: s0, batch 1: s1+s2, batch 2: s3
        assert batches[0][0].id == "s0"
        batch1_ids = {s.id for s in batches[1]}
        assert batch1_ids == {"s1", "s2"}
        assert batches[2][0].id == "s3"


# ── 8–9. Cancel ──────────────────────────────────────────────────


class TestCancel:
    @pytest.mark.asyncio
    async def test_cancel_marks_task_and_subtasks(self, executor: TaskExecutor):
        subtasks = (
            _make_subtask(id="s0", index=0, status="completed", result="done"),
            _make_subtask(id="s1", index=1, status="running"),
            _make_subtask(id="s2", index=2, status="pending"),
        )
        task = _make_task(id="atask_cancel", status="executing", subtasks=subtasks)
        executor._tasks[task.id] = task

        result = await executor.cancel(task.id)

        assert result is not None
        assert result.status == "cancelled"
        assert result.completed_at is not None
        # Completed subtask stays completed
        assert result.subtasks[0].status == "completed"
        # Running and pending become cancelled
        assert result.subtasks[1].status == "cancelled"
        assert result.subtasks[2].status == "cancelled"

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_returns_none(self, executor: TaskExecutor):
        result = await executor.cancel("atask_doesnotexist")
        assert result is None

    @pytest.mark.asyncio
    async def test_cancel_already_completed_returns_task(self, executor: TaskExecutor):
        task = _make_task(id="atask_done", status="completed")
        executor._tasks[task.id] = task
        result = await executor.cancel(task.id)
        # Returns the task but does not change status
        assert result is not None
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_cancel_cancels_asyncio_task(self, executor: TaskExecutor):
        mock_atask = MagicMock()
        executor._tasks["atask_x"] = _make_task(id="atask_x", status="executing")
        executor._async_tasks["atask_x"] = mock_atask

        await executor.cancel("atask_x")
        mock_atask.cancel.assert_called_once()
        assert "atask_x" not in executor._async_tasks


# ── 10. Max Active Limit ─────────────────────────────────────────


class TestMaxActive:
    @pytest.mark.asyncio
    async def test_submit_raises_when_max_active_reached(self, executor: TaskExecutor):
        for i in range(TaskExecutor.MAX_ACTIVE):
            executor._tasks[f"t{i}"] = _make_task(id=f"t{i}", status="executing")

        with pytest.raises(RuntimeError, match="Max.*concurrent tasks"):
            await executor.submit("one more goal")


# ── 11. Finalize without LLM ─────────────────────────────────────


class TestFinalize:
    @pytest.mark.asyncio
    async def test_finalize_no_llm_concatenates(self, executor: TaskExecutor):
        subtasks = (
            _make_subtask(id="s0", index=0, status="completed", result="Result A", agent_id="coder"),
            _make_subtask(id="s1", index=1, status="completed", result="Result B", agent_id="researcher"),
        )
        task = _make_task(goal="multi-step goal", status="executing", subtasks=subtasks)

        finalized = await executor._finalize(task)

        assert finalized.status == "completed"
        assert "[coder] Result A" in finalized.final_result
        assert "[researcher] Result B" in finalized.final_result
        assert finalized.completed_at is not None

    @pytest.mark.asyncio
    async def test_finalize_no_completed_subtasks(self, executor: TaskExecutor):
        subtasks = (
            _make_subtask(id="s0", index=0, status="failed", error="boom"),
        )
        task = _make_task(goal="will fail", status="executing", subtasks=subtasks)

        finalized = await executor._finalize(task)

        assert finalized.status == "failed"
        assert finalized.final_result == "No subtasks completed successfully."

    @pytest.mark.asyncio
    async def test_finalize_stores_memory_when_available(self):
        mock_memory = MagicMock()
        executor = TaskExecutor(memory=mock_memory)

        subtasks = (
            _make_subtask(id="s0", index=0, status="completed", result="done"),
        )
        task = _make_task(goal="memorize this", status="executing", subtasks=subtasks)

        await executor._finalize(task)
        mock_memory.store.assert_called_once()


# ── 12. Execute Subtask without Collaboration Engine ──────────────


class TestExecuteSubtask:
    @pytest.mark.asyncio
    async def test_execute_subtask_no_collab_fallback(self, executor: TaskExecutor):
        """Without collab engine, returns a fallback message and succeeds."""
        task = _make_task(goal="test")
        subtask = _make_subtask(description="analyze data", agent_id="analyst")

        result = await executor._execute_subtask(task, subtask)

        assert result.status == "completed"
        assert "[No collaboration engine]" in result.result
        assert "analyst" in result.result
        assert result.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_subtask_with_collab_success(self):
        mock_collab = AsyncMock()
        mock_wf = MagicMock()
        mock_wf.final_result = "Collaboration result here"
        mock_wf.status.value = "completed"
        mock_collab.delegate.return_value = mock_wf

        executor = TaskExecutor(collab=mock_collab)
        task = _make_task(goal="test")
        subtask = _make_subtask(description="code something", agent_id="coder")

        result = await executor._execute_subtask(task, subtask)

        assert result.status == "completed"
        assert result.result == "Collaboration result here"
        mock_collab.delegate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_subtask_with_collab_failure(self):
        mock_collab = AsyncMock()
        mock_wf = MagicMock()
        mock_wf.final_result = "error details"
        mock_wf.status.value = "failed"
        mock_collab.delegate.return_value = mock_wf

        executor = TaskExecutor(collab=mock_collab)
        task = _make_task(goal="test")
        subtask = _make_subtask(description="will fail", agent_id="coder")

        result = await executor._execute_subtask(task, subtask)
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_execute_subtask_timeout(self):
        mock_collab = AsyncMock()
        mock_collab.delegate.side_effect = asyncio.TimeoutError()

        executor = TaskExecutor(collab=mock_collab)
        task = _make_task(goal="test")
        subtask = _make_subtask(description="slow task", agent_id="researcher")

        result = await executor._execute_subtask(task, subtask)
        assert result.status == "failed"
        assert "Timeout" in result.error

    @pytest.mark.asyncio
    async def test_execute_subtask_exception(self):
        mock_collab = AsyncMock()
        mock_collab.delegate.side_effect = ValueError("unexpected")

        executor = TaskExecutor(collab=mock_collab)
        task = _make_task(goal="test")
        subtask = _make_subtask(description="error task", agent_id="researcher")

        result = await executor._execute_subtask(task, subtask)
        assert result.status == "failed"
        assert "unexpected" in result.error


# ── 13. Submit Creates Task ───────────────────────────────────────


class TestSubmit:
    @pytest.mark.asyncio
    async def test_submit_creates_and_stores_task(self, executor: TaskExecutor):
        task = await executor.submit("build a website", metadata={"priority": "high"})

        assert task.id.startswith("atask_")
        assert task.goal == "build a website"
        assert task.status == "pending"
        assert task.metadata == {"priority": "high"}
        assert task.id in executor._tasks
        assert task.id in executor._async_tasks

        # Clean up: cancel the background task
        atask = executor._async_tasks.get(task.id)
        if atask:
            atask.cancel()
            try:
                await atask
            except (asyncio.CancelledError, Exception):
                pass

    @pytest.mark.asyncio
    async def test_submit_default_metadata(self, executor: TaskExecutor):
        task = await executor.submit("simple goal")
        assert task.metadata == {}

        atask = executor._async_tasks.get(task.id)
        if atask:
            atask.cancel()
            try:
                await atask
            except (asyncio.CancelledError, Exception):
                pass


# ── 14. Bus Publishing ────────────────────────────────────────────


class TestPublish:
    @pytest.mark.asyncio
    async def test_publish_with_bus(self):
        mock_bus = MagicMock()
        mock_bus.publish = AsyncMock()
        mock_msg = MagicMock()
        mock_bus.create_message.return_value = mock_msg

        executor = TaskExecutor(bus=mock_bus)
        task = _make_task(id="atask_pub", goal="test goal", status="executing")
        subtask = _make_subtask(id="s0", agent_id="researcher", status="running")

        await executor._publish(task, subtask, "subtask_started")

        mock_bus.create_message.assert_called_once()
        call_kwargs = mock_bus.create_message.call_args
        assert call_kwargs[1]["topic"] == "task.atask_pub.subtask_started"
        mock_bus.publish.assert_awaited_once_with(mock_msg)

    @pytest.mark.asyncio
    async def test_publish_without_bus_is_noop(self, executor: TaskExecutor):
        """No bus configured — _publish should silently do nothing."""
        task = _make_task()
        await executor._publish(task, None, "test_event")  # Should not raise

    @pytest.mark.asyncio
    async def test_publish_bus_error_swallowed(self):
        mock_bus = MagicMock()
        mock_bus.create_message.side_effect = RuntimeError("bus broken")

        executor = TaskExecutor(bus=mock_bus)
        task = _make_task()
        # Should not raise despite bus error
        await executor._publish(task, None, "test_event")


# ── 15. Learning Engine Integration ──────────────────────────────


class TestLearningIntegration:
    @pytest.mark.asyncio
    async def test_records_learning_on_success(self):
        mock_learning = MagicMock()
        executor = TaskExecutor(learning=mock_learning)

        task = _make_task(goal="learn test")
        subtask = _make_subtask(agent_id="coder")

        result = await executor._execute_subtask(task, subtask)

        assert result.status == "completed"
        mock_learning.record_agent_outcome.assert_called_once_with(
            agent_id="coder",
            task_description="do something",
            task_category="autonomous_task",
            status="completed",
        )

    @pytest.mark.asyncio
    async def test_learning_error_does_not_break_execution(self):
        mock_learning = MagicMock()
        mock_learning.record_agent_outcome.side_effect = RuntimeError("learning down")
        executor = TaskExecutor(learning=mock_learning)

        task = _make_task(goal="learn test")
        subtask = _make_subtask(agent_id="coder")

        result = await executor._execute_subtask(task, subtask)
        # Should still complete despite learning engine failure
        assert result.status == "completed"
