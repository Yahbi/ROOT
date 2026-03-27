"""Tests for the Builder Agent — ROOT's self-improvement engine."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.core.builder_agent import BuilderAgent, BuildTask


@pytest.fixture
def mock_self_dev():
    """Provide a mock SelfDevEngine."""
    sd = MagicMock()
    sd.identify_gaps.return_value = []
    sd.assess.return_value = {"maturity_score": 0.8, "capability_gaps": []}
    sd.create_skill_from_pattern = MagicMock()
    sd.propose_improvement = MagicMock()
    return sd


@pytest.fixture
def mock_memory():
    """Provide a mock memory engine."""
    mem = MagicMock()
    mem.stats.return_value = {"total": 100, "by_type": {}}
    mem.store = MagicMock()
    mem.search = MagicMock(return_value=[])
    return mem


@pytest.fixture
def mock_skills():
    """Provide a mock skill engine."""
    return MagicMock()


@pytest.fixture
def builder(mock_memory, mock_skills, mock_self_dev, mock_llm):
    """Provide a BuilderAgent with mocked dependencies."""
    return BuilderAgent(
        memory=mock_memory,
        skills=mock_skills,
        self_dev=mock_self_dev,
        llm=mock_llm,
    )


@pytest.fixture
def builder_no_llm(mock_memory, mock_skills, mock_self_dev):
    """Provide a BuilderAgent without LLM (offline mode)."""
    return BuilderAgent(
        memory=mock_memory,
        skills=mock_skills,
        self_dev=mock_self_dev,
    )


# ── BuildTask dataclass ────────────────────────────────────────


class TestBuildTask:
    def test_frozen(self):
        t = BuildTask(id="t1", task_type="skill_create", description="test")
        with pytest.raises(AttributeError):
            t.status = "working"  # type: ignore[misc]

    def test_defaults(self):
        t = BuildTask(id="t1", task_type="skill_create", description="desc")
        assert t.status == "pending"
        assert t.result is None
        assert t.impact_score == 0.0
        assert t.completed_at is None
        assert t.created_at  # auto-populated


# ── State management ───────────────────────────────────────────


class TestState:
    def test_initial_state(self, builder: BuilderAgent):
        assert builder.is_running is False
        assert builder._cycle_count == 0

    def test_stop(self, builder: BuilderAgent):
        builder._running = True
        builder.stop()
        assert builder.is_running is False


# ── Gap analysis / identify improvements ───────────────────────


class TestIdentifyImprovements:
    def test_no_self_dev_returns_empty(self):
        agent = BuilderAgent()
        result = agent._identify_improvements()
        assert result == []

    def test_skill_gaps_create_tasks(self, builder: BuilderAgent, mock_self_dev):
        mock_self_dev.identify_gaps.return_value = [
            {"area": "skill_automation", "suggestion": "Create automation skill"},
        ]
        tasks = builder._identify_improvements()
        assert len(tasks) >= 1
        assert tasks[0].task_type == "skill_create"

    def test_memory_gaps_create_tasks(self, builder: BuilderAgent, mock_self_dev):
        mock_self_dev.identify_gaps.return_value = [
            {"area": "memory_fact", "suggestion": "Collect more facts"},
        ]
        tasks = builder._identify_improvements()
        assert any(t.task_type == "knowledge_expand" for t in tasks)

    def test_low_memory_count_triggers_task(self, builder: BuilderAgent, mock_memory):
        mock_memory.stats.return_value = {"total": 10}
        tasks = builder._identify_improvements()
        assert any("Memory count low" in t.description for t in tasks)

    def test_low_maturity_triggers_optimization(self, builder: BuilderAgent, mock_self_dev):
        mock_self_dev.identify_gaps.return_value = []
        mock_self_dev.assess.return_value = {"maturity_score": 0.3, "capability_gaps": []}
        tasks = builder._identify_improvements()
        assert any(t.task_type == "optimization" for t in tasks)

    def test_always_on_improvements_when_no_gaps(self, builder: BuilderAgent, mock_self_dev):
        mock_self_dev.identify_gaps.return_value = []
        mock_self_dev.assess.return_value = {"maturity_score": 0.9, "capability_gaps": []}
        # No gaps, high maturity — should still produce always-on tasks
        tasks = builder._identify_improvements()
        assert len(tasks) >= 1


# ── Run cycle ──────────────────────────────────────────────────


class TestRunCycle:
    @pytest.mark.asyncio
    async def test_run_cycle_no_improvements(self, builder: BuilderAgent, mock_self_dev):
        mock_self_dev.identify_gaps.return_value = []
        mock_self_dev.assess.return_value = {"maturity_score": 1.0, "capability_gaps": []}
        # Force no always-on by setting memory to None
        builder._memory = None
        await builder._run_cycle()
        assert builder._cycle_count == 1

    @pytest.mark.asyncio
    async def test_run_cycle_with_skill_gap(self, builder: BuilderAgent, mock_self_dev, mock_llm):
        mock_self_dev.identify_gaps.return_value = [
            {"area": "skill_trading", "suggestion": "Create trading skill"},
        ]
        mock_llm.complete = AsyncMock(return_value="# Trading Skill\n\nSteps...")
        await builder._run_cycle()
        assert builder._cycle_count == 1
        assert len(builder._task_history) >= 1

    @pytest.mark.asyncio
    async def test_run_cycle_failed_execution_propagates(self, builder: BuilderAgent, mock_self_dev, mock_llm):
        mock_self_dev.identify_gaps.return_value = [
            {"area": "skill_x", "suggestion": "test"},
        ]
        mock_llm.complete = AsyncMock(return_value="content")
        mock_self_dev.create_skill_from_pattern = MagicMock(side_effect=Exception("fail"))
        # Exception propagates from _run_cycle (caught by start_loop)
        with pytest.raises(Exception, match="fail"):
            await builder._run_cycle()


# ── Skill creation ─────────────────────────────────────────────


class TestCreateSkill:
    @pytest.mark.asyncio
    async def test_create_skill_with_llm(self, builder: BuilderAgent, mock_llm, mock_self_dev):
        mock_llm.complete = AsyncMock(return_value="# Skill Content")
        task = BuildTask(
            id="t1", task_type="skill_create",
            description="Create skill for 'trading': Build trading strategies",
        )
        result = await builder._create_skill_from_gap(task)
        assert result is not None
        assert "trading" in result
        mock_self_dev.create_skill_from_pattern.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_skill_offline_with_template(self, builder_no_llm, mock_self_dev):
        task = BuildTask(
            id="t1", task_type="skill_create",
            description="Create skill for 'automation': Automate tasks",
        )
        result = await builder_no_llm._create_skill_from_gap(task)
        assert result is not None
        assert "automation" in result
        mock_self_dev.create_skill_from_pattern.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_skill_offline_unknown_category(self, builder_no_llm, mock_self_dev):
        task = BuildTask(
            id="t1", task_type="skill_create",
            description="Create skill for 'exotic-thing': Something new",
        )
        result = await builder_no_llm._create_skill_from_gap(task)
        assert result is not None

    @pytest.mark.asyncio
    async def test_create_skill_no_self_dev(self, mock_llm):
        agent = BuilderAgent(llm=mock_llm)
        mock_llm.complete = AsyncMock(return_value="# Skill")
        task = BuildTask(id="t1", task_type="skill_create", description="test")
        result = await agent._create_skill_from_gap(task)
        assert result is None


# ── Knowledge expansion ────────────────────────────────────────


class TestExpandKnowledge:
    @pytest.mark.asyncio
    async def test_expand_with_llm(self, builder: BuilderAgent, mock_llm, mock_memory):
        llm_response = '[{"content": "fact 1", "type": "fact", "tags": ["t"]}, {"content": "fact 2", "type": "learning", "tags": []}]'
        mock_llm.complete = AsyncMock(return_value=llm_response)
        task = BuildTask(id="t1", task_type="knowledge_expand", description="Expand AI knowledge")
        result = await builder._expand_knowledge(task)
        assert result is not None
        assert "Stored 2" in result

    @pytest.mark.asyncio
    async def test_expand_no_memory_returns_none(self, mock_llm):
        agent = BuilderAgent(llm=mock_llm)
        task = BuildTask(id="t1", task_type="knowledge_expand", description="test")
        result = await agent._expand_knowledge(task)
        assert result is None

    @pytest.mark.asyncio
    async def test_expand_offline_proposes_improvement(self, builder_no_llm, mock_self_dev):
        task = BuildTask(id="t1", task_type="knowledge_expand", description="Learn more")
        result = await builder_no_llm._expand_knowledge(task)
        assert result == "Proposed knowledge expansion"
        mock_self_dev.propose_improvement.assert_called_once()

    @pytest.mark.asyncio
    async def test_expand_llm_invalid_json_fallback(self, builder: BuilderAgent, mock_llm, mock_self_dev):
        mock_llm.complete = AsyncMock(return_value="not json at all")
        task = BuildTask(id="t1", task_type="knowledge_expand", description="test")
        result = await builder._expand_knowledge(task)
        # Falls through to offline fallback
        assert result == "Proposed knowledge expansion"


# ── Optimize ───────────────────────────────────────────────────


class TestOptimize:
    @pytest.mark.asyncio
    async def test_optimize_no_self_dev(self):
        agent = BuilderAgent()
        task = BuildTask(id="t1", task_type="optimization", description="test")
        result = await agent._optimize(task)
        assert result is None

    @pytest.mark.asyncio
    async def test_optimize_creates_skills_for_gaps(self, builder: BuilderAgent, mock_self_dev, mock_llm):
        mock_self_dev.assess.return_value = {
            "capability_gaps": [
                {"area": "skill_security", "suggestion": "Create security skill"},
            ]
        }
        mock_llm.complete = AsyncMock(return_value="# Security Skill")
        task = BuildTask(id="t1", task_type="optimization", description="optimize")
        result = await builder._optimize(task)
        assert result is not None
        assert "created 1" in result


# ── run_once and history ───────────────────────────────────────


class TestRunOnce:
    @pytest.mark.asyncio
    async def test_run_once_returns_tasks(self, builder: BuilderAgent, mock_self_dev, mock_llm):
        mock_self_dev.identify_gaps.return_value = [
            {"area": "skill_data-analysis", "suggestion": "Add data analysis"},
        ]
        mock_llm.complete = AsyncMock(return_value="# Data Analysis")
        tasks = await builder.run_once()
        assert isinstance(tasks, list)


# ── Stats ──────────────────────────────────────────────────────


class TestStats:
    def test_stats_initial(self, builder: BuilderAgent):
        s = builder.stats()
        assert s["running"] is False
        assert s["cycles"] == 0
        assert s["total_tasks"] == 0
        assert s["success_rate"] == 0.0

    def test_stats_after_tasks(self, builder: BuilderAgent):
        builder._task_history.append(
            BuildTask(id="t1", task_type="skill_create", description="d", status="completed")
        )
        builder._task_history.append(
            BuildTask(id="t2", task_type="skill_create", description="d", status="failed")
        )
        s = builder.stats()
        assert s["total_tasks"] == 2
        assert s["completed"] == 1
        assert s["failed"] == 1
        assert s["success_rate"] == 50.0

    def test_history_returns_reversed(self, builder: BuilderAgent):
        builder._task_history = [
            BuildTask(id="t1", task_type="a", description="first"),
            BuildTask(id="t2", task_type="b", description="second"),
        ]
        history = builder.get_history()
        assert history[0].id == "t2"

    def test_history_limit(self, builder: BuilderAgent):
        for i in range(10):
            builder._task_history.append(
                BuildTask(id=f"t{i}", task_type="a", description=f"task {i}")
            )
        assert len(builder.get_history(limit=3)) == 3


# ── Task history bounding ──────────────────────────────────────


class TestTaskHistoryBounding:
    @pytest.mark.asyncio
    async def test_history_bounded_at_200(self, builder: BuilderAgent, mock_self_dev, mock_llm):
        builder._task_history = [
            BuildTask(id=f"t{i}", task_type="a", description="d", status="completed")
            for i in range(201)
        ]
        mock_self_dev.identify_gaps.return_value = [
            {"area": "skill_x", "suggestion": "test"},
        ]
        mock_llm.complete = AsyncMock(return_value="# Content")
        await builder._run_cycle()
        assert len(builder._task_history) <= 200
