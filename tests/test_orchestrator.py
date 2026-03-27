"""Tests for the Orchestrator — parallel task execution."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.core.orchestrator import Orchestrator, TaskStatus


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    connector = AsyncMock()
    connector.send_task = AsyncMock(return_value={
        "result": "Task completed successfully",
        "agent": "test",
    })
    registry.get_connector.return_value = connector
    return registry


class TestOrchestrator:
    @pytest.mark.asyncio
    async def test_execute_parallel(self, mock_registry):
        orch = Orchestrator(registry=mock_registry)
        result = await orch.execute_parallel([
            {"agent_id": "researcher", "task": "Research AI trends"},
            {"agent_id": "analyst", "task": "Analyze market data"},
        ])
        assert result.success_count == 2
        assert result.failure_count == 0
        assert len(result.tasks) == 2

    @pytest.mark.asyncio
    async def test_execute_with_timeout(self, mock_registry):
        async def slow_task(task):
            import asyncio
            await asyncio.sleep(10)

        connector = AsyncMock()
        connector.send_task = slow_task
        mock_registry.get_connector.return_value = connector

        orch = Orchestrator(registry=mock_registry)
        result = await orch.execute_parallel([
            {"agent_id": "test", "task": "Slow task", "timeout": 0.1},
        ])
        assert result.failure_count == 1
        assert result.tasks[0].status == TaskStatus.FAILED
        assert "timed out" in (result.tasks[0].error or "")

    @pytest.mark.asyncio
    async def test_history_bounded(self, mock_registry):
        orch = Orchestrator(registry=mock_registry)
        for i in range(110):
            await orch.execute_parallel([
                {"agent_id": "test", "task": f"Task {i}"},
            ])
        assert len(orch._history) <= 100
