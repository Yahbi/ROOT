"""Tests for AgentCollaboration — delegate, pipeline, fanout, council patterns."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.core.agent_collab import (
    AgentCollaboration,
    CollabPattern,
    CollabStep,
    CollabWorkflow,
    WorkflowStatus,
)


# ── Enum Tests ───────────────────────────────────────────────


class TestCollabPattern:
    def test_values(self):
        assert CollabPattern.DELEGATE == "delegate"
        assert CollabPattern.PIPELINE == "pipeline"
        assert CollabPattern.FANOUT == "fanout"
        assert CollabPattern.COUNCIL == "council"

    def test_is_str_enum(self):
        assert isinstance(CollabPattern.DELEGATE, str)


class TestWorkflowStatus:
    def test_values(self):
        assert WorkflowStatus.PENDING == "pending"
        assert WorkflowStatus.RUNNING == "running"
        assert WorkflowStatus.COMPLETED == "completed"
        assert WorkflowStatus.FAILED == "failed"

    def test_is_str_enum(self):
        assert isinstance(WorkflowStatus.PENDING, str)


# ── Dataclass Tests ──────────────────────────────────────────


class TestCollabStep:
    def test_defaults(self):
        step = CollabStep(agent_id="coder", task="write code")
        assert step.result is None
        assert step.status == "pending"
        assert step.duration_seconds == 0.0

    def test_frozen(self):
        step = CollabStep(agent_id="coder", task="write code")
        with pytest.raises(AttributeError):
            step.status = "completed"


class TestCollabWorkflow:
    def test_defaults(self):
        wf = CollabWorkflow(
            id="wf_1",
            pattern=CollabPattern.DELEGATE,
            initiator="root",
            goal="do something",
        )
        assert wf.steps == ()
        assert wf.status == WorkflowStatus.PENDING
        assert wf.final_result is None
        assert wf.created_at is not None
        assert wf.completed_at is None

    def test_frozen(self):
        wf = CollabWorkflow(
            id="wf_1",
            pattern=CollabPattern.DELEGATE,
            initiator="root",
            goal="do something",
        )
        with pytest.raises(AttributeError):
            wf.status = WorkflowStatus.RUNNING


# ── Fixtures ─────────────────────────────────────────────────


@pytest.fixture
def mock_orchestrator():
    orch = AsyncMock()
    result = MagicMock()
    result.tasks = []
    result.success_count = 0
    orch.execute_parallel = AsyncMock(return_value=result)
    return orch


@pytest.fixture
def mock_registry():
    registry = MagicMock()
    connector = AsyncMock()
    connector.send_task = AsyncMock(return_value={"result": "done"})
    registry.get_connector.return_value = connector
    return registry


@pytest.fixture
def collab(mock_orchestrator, mock_registry):
    return AgentCollaboration(
        orchestrator=mock_orchestrator,
        bus=None,
        registry=mock_registry,
    )


# ── Delegate Tests ───────────────────────────────────────────


class TestDelegate:
    @pytest.mark.asyncio
    async def test_successful_delegation(self, collab, mock_registry):
        wf = await collab.delegate(
            from_agent="root",
            to_agent="coder",
            task="write a function",
        )

        assert wf.pattern == CollabPattern.DELEGATE
        assert wf.initiator == "root"
        assert wf.status == WorkflowStatus.COMPLETED
        assert wf.final_result == "done"
        assert len(wf.steps) == 1
        assert wf.steps[0].agent_id == "coder"
        assert wf.steps[0].status == "completed"
        assert wf.completed_at is not None

        mock_registry.get_connector.assert_called_with("coder")

    @pytest.mark.asyncio
    async def test_delegation_with_error(self, collab, mock_registry):
        connector = AsyncMock()
        connector.send_task = AsyncMock(return_value={"error": "agent offline"})
        mock_registry.get_connector.return_value = connector

        wf = await collab.delegate(
            from_agent="root",
            to_agent="coder",
            task="write code",
        )

        assert wf.status == WorkflowStatus.FAILED
        assert wf.steps[0].status == "failed"

    @pytest.mark.asyncio
    async def test_delegation_stored_in_history(self, collab):
        await collab.delegate(
            from_agent="root",
            to_agent="coder",
            task="task1",
        )

        history = collab.get_history()
        assert len(history) == 1
        assert history[0].goal == "task1"


# ── Pipeline Tests ───────────────────────────────────────────


class TestPipeline:
    @pytest.mark.asyncio
    async def test_multi_step_pipeline(self, collab, mock_registry):
        connector = AsyncMock()
        call_count = 0

        async def side_effect(task):
            nonlocal call_count
            call_count += 1
            return {"result": f"step_{call_count}_output"}

        connector.send_task = AsyncMock(side_effect=side_effect)
        mock_registry.get_connector.return_value = connector

        steps = [
            {"agent_id": "researcher", "task": "find info"},
            {"agent_id": "analyst", "task": "analyze {prev_result}"},
            {"agent_id": "writer", "task": "summarize {prev_result}"},
        ]

        wf = await collab.pipeline(
            initiator="root",
            goal="research and summarize",
            steps=steps,
        )

        assert wf.pattern == CollabPattern.PIPELINE
        assert wf.status == WorkflowStatus.COMPLETED
        assert len(wf.steps) == 3
        assert wf.final_result == "step_3_output"

        # Second step should have had prev_result injected
        assert "step_1_output" in wf.steps[1].task

    @pytest.mark.asyncio
    async def test_pipeline_stops_on_failure(self, collab, mock_registry):
        connector = AsyncMock()
        call_count = 0

        async def side_effect(task):
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                return {"error": "failed at step 2"}
            return {"result": f"step_{call_count}_output"}

        connector.send_task = AsyncMock(side_effect=side_effect)
        mock_registry.get_connector.return_value = connector

        steps = [
            {"agent_id": "researcher", "task": "find info"},
            {"agent_id": "analyst", "task": "analyze"},
            {"agent_id": "writer", "task": "summarize"},
        ]

        wf = await collab.pipeline(
            initiator="root",
            goal="should fail midway",
            steps=steps,
        )

        assert wf.status == WorkflowStatus.FAILED
        assert len(wf.steps) == 2  # stopped after step 2
        assert wf.steps[1].status == "failed"

    @pytest.mark.asyncio
    async def test_pipeline_prev_result_appended_when_no_placeholder(
        self, collab, mock_registry
    ):
        """When task has no {prev_result} placeholder, context is appended."""
        connector = AsyncMock()
        call_count = 0

        async def side_effect(task):
            nonlocal call_count
            call_count += 1
            return {"result": f"output_{call_count}"}

        connector.send_task = AsyncMock(side_effect=side_effect)
        mock_registry.get_connector.return_value = connector

        steps = [
            {"agent_id": "a", "task": "first task"},
            {"agent_id": "b", "task": "second task without placeholder"},
        ]

        wf = await collab.pipeline(initiator="root", goal="test", steps=steps)

        assert "Context from previous step" in wf.steps[1].task
        assert "output_1" in wf.steps[1].task


# ── Fanout Tests ─────────────────────────────────────────────


class TestFanout:
    @pytest.mark.asyncio
    async def test_parallel_execution(self, collab, mock_orchestrator):
        task_a = MagicMock()
        task_a.agent_id = "researcher"
        task_a.result = "research output"
        task_a.error = None
        task_a.status = MagicMock(value="completed")

        task_b = MagicMock()
        task_b.agent_id = "analyst"
        task_b.result = "analysis output"
        task_b.error = None
        task_b.status = MagicMock(value="completed")

        orch_result = MagicMock()
        orch_result.tasks = [task_a, task_b]
        orch_result.success_count = 2
        mock_orchestrator.execute_parallel = AsyncMock(return_value=orch_result)

        wf = await collab.fanout(
            initiator="root",
            goal="gather intel",
            agents=["researcher", "analyst"],
            task="analyze market",
        )

        assert wf.pattern == CollabPattern.FANOUT
        assert wf.status == WorkflowStatus.COMPLETED
        assert len(wf.steps) == 2
        assert "research output" in wf.final_result
        assert "analysis output" in wf.final_result

        mock_orchestrator.execute_parallel.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fanout_all_fail(self, collab, mock_orchestrator):
        orch_result = MagicMock()
        orch_result.tasks = []
        orch_result.success_count = 0
        mock_orchestrator.execute_parallel = AsyncMock(return_value=orch_result)

        wf = await collab.fanout(
            initiator="root",
            goal="gather intel",
            agents=["a", "b"],
            task="do stuff",
        )

        assert wf.status == WorkflowStatus.FAILED

    @pytest.mark.asyncio
    async def test_fanout_with_merge_prompt(self, collab, mock_orchestrator, mock_registry):
        task_a = MagicMock()
        task_a.agent_id = "researcher"
        task_a.result = "research findings"
        task_a.error = None
        task_a.status = MagicMock(value="completed")

        orch_result = MagicMock()
        orch_result.tasks = [task_a]
        orch_result.success_count = 1
        mock_orchestrator.execute_parallel = AsyncMock(return_value=orch_result)

        # The merge step calls _execute_single which uses registry
        connector = AsyncMock()
        connector.send_task = AsyncMock(return_value={"result": "synthesized answer"})
        mock_registry.get_connector.return_value = connector

        wf = await collab.fanout(
            initiator="root",
            goal="merged analysis",
            agents=["researcher"],
            task="analyze",
            merge_prompt="Merge these results",
        )

        assert wf.status == WorkflowStatus.COMPLETED
        assert wf.final_result == "synthesized answer"


# ── Council Tests ────────────────────────────────────────────


class TestCouncil:
    @pytest.mark.asyncio
    async def test_council_delegates_to_fanout(self, collab, mock_orchestrator, mock_registry):
        task_a = MagicMock()
        task_a.agent_id = "analyst"
        task_a.result = "I recommend option A"
        task_a.error = None
        task_a.status = MagicMock(value="completed")

        task_b = MagicMock()
        task_b.agent_id = "researcher"
        task_b.result = "I recommend option B"
        task_b.error = None
        task_b.status = MagicMock(value="completed")

        orch_result = MagicMock()
        orch_result.tasks = [task_a, task_b]
        orch_result.success_count = 2
        mock_orchestrator.execute_parallel = AsyncMock(return_value=orch_result)

        connector = AsyncMock()
        connector.send_task = AsyncMock(return_value={"result": "final decision"})
        mock_registry.get_connector.return_value = connector

        wf = await collab.council(
            initiator="root",
            question="Which option is better?",
            agents=["analyst", "researcher"],
        )

        assert "Council decision" in wf.goal
        assert wf.status == WorkflowStatus.COMPLETED
        assert wf.final_result == "final decision"


# ── Stats & History Tests ────────────────────────────────────


class TestStatsAndHistory:
    @pytest.mark.asyncio
    async def test_stats_returns_pattern_counts(self, collab):
        await collab.delegate(from_agent="a", to_agent="b", task="t1")
        await collab.delegate(from_agent="a", to_agent="c", task="t2")

        s = collab.stats()
        assert s["total_workflows"] == 2
        assert s["by_pattern"]["delegate"] == 2
        assert s["by_pattern"]["pipeline"] == 0
        assert s["success_rate"] == 1.0

    @pytest.mark.asyncio
    async def test_get_history_respects_limit(self, collab):
        for i in range(5):
            await collab.delegate(from_agent="a", to_agent="b", task=f"task_{i}")

        history = collab.get_history(limit=3)
        assert len(history) == 3
        # Most recent first
        assert history[0].goal == "task_4"

    @pytest.mark.asyncio
    async def test_get_active_returns_running_only(self, collab):
        # After delegation completes, nothing should be active
        await collab.delegate(from_agent="a", to_agent="b", task="done")
        assert collab.get_active() == []

    def test_stats_empty(self, collab):
        s = collab.stats()
        assert s["total_workflows"] == 0
        assert s["active"] == 0
        assert s["success_rate"] == 0.0


# ── Agent-to-Domain Mapping ─────────────────────────────────


class TestAgentToDomain:
    def test_known_agents(self):
        assert AgentCollaboration._agent_to_domain("swarm") == "trading"
        assert AgentCollaboration._agent_to_domain("coder") == "code"
        assert AgentCollaboration._agent_to_domain("guardian") == "security"
        assert AgentCollaboration._agent_to_domain("root") == "system"
        assert AgentCollaboration._agent_to_domain("writer") == "writing"

    def test_unknown_agent_defaults_to_research(self):
        assert AgentCollaboration._agent_to_domain("unknown_agent") == "research"


# ── Network Enrichment ───────────────────────────────────────


class TestNetworkEnrichment:
    @pytest.mark.asyncio
    async def test_network_context_injected(self, mock_orchestrator, mock_registry):
        network = MagicMock()
        network.get_network_context.return_value = "[Network insight: market is up]"

        c = AgentCollaboration(
            orchestrator=mock_orchestrator,
            bus=None,
            registry=mock_registry,
            network=network,
        )

        connector = mock_registry.get_connector.return_value
        await c.delegate(from_agent="root", to_agent="analyst", task="analyze data")

        # The connector should have been called with enriched task
        sent_task = connector.send_task.call_args[0][0]
        assert "[Network insight: market is up]" in sent_task

    @pytest.mark.asyncio
    async def test_network_failure_does_not_break_execution(
        self, mock_orchestrator, mock_registry
    ):
        network = MagicMock()
        network.get_network_context.side_effect = RuntimeError("network down")

        c = AgentCollaboration(
            orchestrator=mock_orchestrator,
            bus=None,
            registry=mock_registry,
            network=network,
        )

        wf = await c.delegate(from_agent="root", to_agent="coder", task="write code")
        assert wf.status == WorkflowStatus.COMPLETED


# ── No Registry ─────────────────────────────────────────────


class TestNoRegistry:
    @pytest.mark.asyncio
    async def test_execute_single_returns_error_without_registry(self, mock_orchestrator):
        c = AgentCollaboration(
            orchestrator=mock_orchestrator,
            bus=None,
            registry=None,
        )

        wf = await c.delegate(from_agent="root", to_agent="coder", task="do something")
        assert wf.status == WorkflowStatus.FAILED
        assert "No registry" in wf.final_result

    @pytest.mark.asyncio
    async def test_execute_single_returns_error_no_connector(
        self, mock_orchestrator
    ):
        registry = MagicMock()
        registry.get_connector.return_value = None

        c = AgentCollaboration(
            orchestrator=mock_orchestrator,
            bus=None,
            registry=registry,
        )

        wf = await c.delegate(from_agent="root", to_agent="ghost", task="hello")
        assert wf.status == WorkflowStatus.FAILED
        assert "No connector" in wf.final_result
