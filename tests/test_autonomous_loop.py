"""Tests for backend.core.autonomous_loop — self-improving intelligence cycle."""

from __future__ import annotations

import dataclasses
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.autonomous_loop import AutonomousLoop, Experiment


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def auto_loop():
    """Bare AutonomousLoop with no dependencies injected."""
    return AutonomousLoop()


@pytest.fixture
def mock_memory():
    mem = MagicMock()
    mem.count.return_value = 50
    mem.store.return_value = None
    mem.search.return_value = []
    return mem


@pytest.fixture
def mock_skills():
    skills = MagicMock()
    skills.list_all.return_value = ["skill_a", "skill_b"]
    return skills


@pytest.fixture
def mock_self_dev():
    dev = MagicMock()
    dev.assess.return_value = {
        "maturity_level": "intermediate",
        "maturity_score": 0.6,
        "capability_gaps": ["gap_alpha", "gap_beta"],
        "evolution_count": 5,
    }
    dev.propose_improvement.return_value = None
    return dev


@pytest.fixture
def mock_collab():
    collab = AsyncMock()
    result = MagicMock()
    result.final_result = "A useful piece of knowledge that is long enough to pass validation"
    collab.delegate.return_value = result
    return collab


@pytest.fixture
def mock_goal_engine():
    ge = MagicMock()
    ge.stats.return_value = {
        "by_status": {"active": 3},
        "avg_active_progress": 0.45,
    }
    ge.assess_all_goals = AsyncMock(return_value={"updates": []})
    ge.decompose_goal = AsyncMock(return_value=["task_1", "task_2"])
    return ge


@pytest.fixture
def mock_task_queue():
    tq = MagicMock()
    tq.stats.return_value = {"by_status": {"pending": 7}}
    return tq


@pytest.fixture
def mock_learning():
    learn = MagicMock()
    learn.get_experiment_weight.return_value = 0.8
    learn.get_insights.return_value = {"misrouted_count": 0}
    learn.record_experiment_outcome.return_value = None
    return learn


@pytest.fixture
def mock_bus():
    # Bus has a mix of sync (create_message) and async (publish) methods.
    # MagicMock as base + explicit AsyncMock for publish keeps both correct.
    bus = MagicMock()
    msg = MagicMock()
    bus.create_message.return_value = msg
    bus.publish = AsyncMock(return_value=None)
    return bus


@pytest.fixture
def wired_loop(
    mock_memory,
    mock_skills,
    mock_self_dev,
    mock_collab,
    mock_goal_engine,
    mock_task_queue,
    mock_learning,
    mock_bus,
):
    """AutonomousLoop with all dependencies injected."""
    return AutonomousLoop(
        memory=mock_memory,
        skills=mock_skills,
        self_dev=mock_self_dev,
        collab=mock_collab,
        goal_engine=mock_goal_engine,
        task_queue=mock_task_queue,
        learning=mock_learning,
        bus=mock_bus,
    )


# ── 1. Experiment dataclass ──────────────────────────────────────


class TestExperimentDataclass:
    def test_immutability(self):
        exp = Experiment(
            id="exp_001",
            area="knowledge",
            hypothesis="test hypothesis",
            approach="test approach",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            exp.status = "running"  # type: ignore[misc]

    def test_defaults(self):
        exp = Experiment(
            id="exp_002",
            area="skills",
            hypothesis="h",
            approach="a",
        )
        assert exp.status == "proposed"
        assert exp.baseline_metric is None
        assert exp.result_metric is None
        assert exp.outcome is None
        assert exp.completed_at is None
        assert exp.created_at  # non-empty ISO string

    def test_explicit_values_preserved(self):
        exp = Experiment(
            id="exp_003",
            area="memory",
            hypothesis="h",
            approach="a",
            status="kept",
            baseline_metric=0.5,
            result_metric=0.9,
            outcome="great",
            completed_at="2025-01-01T00:00:00+00:00",
        )
        assert exp.status == "kept"
        assert exp.baseline_metric == 0.5
        assert exp.result_metric == 0.9
        assert exp.outcome == "great"


# ── 2. Initialization ───────────────────────────────────────────


class TestInitialization:
    def test_default_state(self, auto_loop: AutonomousLoop):
        assert auto_loop._experiments == []
        assert auto_loop._cycle_count == 0
        assert auto_loop._running is False
        assert auto_loop._task is None

    def test_dependency_injection(self, wired_loop: AutonomousLoop):
        assert wired_loop._memory is not None
        assert wired_loop._skills is not None
        assert wired_loop._self_dev is not None
        assert wired_loop._collab is not None
        assert wired_loop._goal_engine is not None
        assert wired_loop._task_queue is not None
        assert wired_loop._learning is not None
        assert wired_loop._bus is not None

    def test_constants(self):
        assert AutonomousLoop.MAX_EXPERIMENTS_PER_CYCLE == 3
        assert AutonomousLoop.CYCLE_INTERVAL == 1800


# ── 3. Stats ─────────────────────────────────────────────────────


class TestStats:
    def test_stats_empty(self, auto_loop: AutonomousLoop):
        s = auto_loop.stats()
        assert s["running"] is False
        assert s["cycles_completed"] == 0
        assert s["total_experiments"] == 0
        assert s["kept"] == 0
        assert s["discarded"] == 0
        assert all(v == 0 for v in s["by_area"].values())

    def test_stats_with_experiments(self, auto_loop: AutonomousLoop):
        auto_loop._experiments = [
            Experiment(id="e1", area="knowledge", hypothesis="h", approach="a", status="kept"),
            Experiment(id="e2", area="knowledge", hypothesis="h", approach="a", status="discarded"),
            Experiment(id="e3", area="skills", hypothesis="h", approach="a", status="kept"),
        ]
        auto_loop._cycle_count = 2
        auto_loop._running = True

        s = auto_loop.stats()
        assert s["running"] is True
        assert s["cycles_completed"] == 2
        assert s["total_experiments"] == 3
        assert s["kept"] == 2
        assert s["discarded"] == 1
        assert s["by_area"]["knowledge"] == 2
        assert s["by_area"]["skills"] == 1
        assert s["by_area"]["memory"] == 0


# ── 4. Get experiments ───────────────────────────────────────────


class TestGetExperiments:
    def test_empty(self, auto_loop: AutonomousLoop):
        assert auto_loop.get_experiments() == []

    def test_returns_dict_format(self, auto_loop: AutonomousLoop):
        auto_loop._experiments = [
            Experiment(id="e1", area="knowledge", hypothesis="h1", approach="a1", status="kept", outcome="ok"),
        ]
        result = auto_loop.get_experiments()
        assert len(result) == 1
        assert result[0]["id"] == "e1"
        assert result[0]["area"] == "knowledge"
        assert result[0]["hypothesis"] == "h1"
        assert result[0]["status"] == "kept"
        assert result[0]["outcome"] == "ok"

    def test_limit_and_ordering(self, auto_loop: AutonomousLoop):
        auto_loop._experiments = [
            Experiment(id=f"e{i}", area="knowledge", hypothesis="h", approach="a")
            for i in range(10)
        ]
        result = auto_loop.get_experiments(limit=3)
        assert len(result) == 3
        # Most recent first (reversed)
        assert result[0]["id"] == "e9"
        assert result[1]["id"] == "e8"
        assert result[2]["id"] == "e7"


# ── 5. Assess ────────────────────────────────────────────────────


class TestAssess:
    @pytest.mark.asyncio
    async def test_assess_with_all_deps(
        self, wired_loop, mock_self_dev, mock_memory, mock_skills, mock_goal_engine, mock_task_queue
    ):
        assessment = await wired_loop._assess()

        assert assessment["maturity"] == "intermediate"
        assert assessment["maturity_score"] == 0.6
        assert assessment["gaps"] == ["gap_alpha", "gap_beta"]
        assert assessment["evolution_count"] == 5
        assert assessment["memory_count"] == 50
        assert assessment["skill_count"] == 2
        assert assessment["active_goals"] == 3
        assert assessment["avg_goal_progress"] == 0.45
        assert assessment["stalled_goals"] == []
        assert assessment["pending_tasks"] == 7

    @pytest.mark.asyncio
    async def test_assess_no_deps(self, auto_loop: AutonomousLoop):
        assessment = await auto_loop._assess()
        assert assessment == {}

    @pytest.mark.asyncio
    async def test_assess_stalled_goals(self, wired_loop, mock_goal_engine):
        mock_goal_engine.assess_all_goals.return_value = {
            "updates": [
                {"title": "Stalled Goal 1", "status": "stalled"},
                {"title": "Active Goal", "status": "on_track"},
            ]
        }
        assessment = await wired_loop._assess()
        assert len(assessment["stalled_goals"]) == 1
        assert assessment["stalled_goals"][0]["title"] == "Stalled Goal 1"


# ── 6. Propose (template-based, no LLM) ─────────────────────────


class TestPropose:
    @pytest.mark.asyncio
    async def test_propose_without_llm(self, auto_loop: AutonomousLoop):
        assessment = {"gaps": ["web_search"], "memory_count": 10}
        experiments = await auto_loop._propose(assessment)

        assert len(experiments) >= 2  # at least knowledge + 1 gap
        areas = [e.area for e in experiments]
        assert "knowledge" in areas
        assert "skills" in areas

    @pytest.mark.asyncio
    async def test_propose_includes_memory_when_large(self, auto_loop: AutonomousLoop):
        assessment = {"gaps": [], "memory_count": 300}
        experiments = await auto_loop._propose(assessment)

        areas = [e.area for e in experiments]
        assert "memory" in areas

    @pytest.mark.asyncio
    async def test_propose_no_memory_when_small(self, auto_loop: AutonomousLoop):
        assessment = {"gaps": [], "memory_count": 50}
        experiments = await auto_loop._propose(assessment)

        areas = [e.area for e in experiments]
        assert "memory" not in areas


# ── 7. Propose weighting ─────────────────────────────────────────


class TestProposeWeighting:
    @pytest.mark.asyncio
    async def test_candidates_sorted_by_weight(self, mock_learning):
        loop = AutonomousLoop(learning=mock_learning)

        # Return different weights per area
        def weight_fn(area: str) -> float:
            return {"knowledge": 0.3, "skills": 0.9}.get(area, 0.5)

        mock_learning.get_experiment_weight.side_effect = weight_fn

        assessment = {"gaps": ["gap1"], "memory_count": 10}
        experiments = await loop._propose(assessment)

        # skills should come before knowledge due to higher weight
        areas = [e.area for e in experiments]
        skills_idx = areas.index("skills")
        knowledge_idx = areas.index("knowledge")
        assert skills_idx < knowledge_idx

    def test_get_area_weight_no_learning(self, auto_loop: AutonomousLoop):
        assert auto_loop._get_area_weight("knowledge") == 0.5

    def test_get_area_weight_with_learning(self, mock_learning):
        loop = AutonomousLoop(learning=mock_learning)
        mock_learning.get_experiment_weight.return_value = 0.8
        assert loop._get_area_weight("skills") == 0.8
        mock_learning.get_experiment_weight.assert_called_with("skills")


# ── 8. Run experiment — knowledge ────────────────────────────────


class TestRunExperimentKnowledge:
    @pytest.mark.asyncio
    async def test_knowledge_success(self, wired_loop, mock_collab, mock_memory):
        exp = Experiment(
            id="exp_k1", area="knowledge", hypothesis="test", approach="approach"
        )
        result = await wired_loop._run_experiment(exp)

        assert result is not None
        assert result.status == "kept"
        assert result.completed_at is not None
        mock_collab.delegate.assert_called_once()
        # Successful knowledge experiment stores a memory entry
        mock_memory.store.assert_called()

    @pytest.mark.asyncio
    async def test_knowledge_short_result_discarded(self, wired_loop, mock_collab):
        mock_collab.delegate.return_value.final_result = "short"
        exp = Experiment(
            id="exp_k2", area="knowledge", hypothesis="test", approach="approach"
        )
        result = await wired_loop._run_experiment(exp)
        assert result is not None
        assert result.status == "discarded"


# ── 9. Run experiment — skills ───────────────────────────────────


class TestRunExperimentSkills:
    @pytest.mark.asyncio
    async def test_skills_success(self, wired_loop, mock_self_dev):
        exp = Experiment(
            id="exp_s1", area="skills", hypothesis="test skill", approach="create a skill"
        )
        result = await wired_loop._run_experiment(exp)

        assert result is not None
        assert result.status == "kept"
        mock_self_dev.propose_improvement.assert_called_once_with(
            area="skills",
            description="create a skill",
            rationale="test skill",
        )


# ── 10. Run experiment — memory ──────────────────────────────────


class TestRunExperimentMemory:
    @pytest.mark.asyncio
    async def test_memory_pruning(self, wired_loop, mock_memory):
        # Return some low-confidence memories
        low_mem = MagicMock()
        low_mem.confidence = 0.1
        high_mem = MagicMock()
        high_mem.confidence = 0.8
        mock_memory.search.return_value = [low_mem, high_mem]

        exp = Experiment(
            id="exp_m1", area="memory", hypothesis="prune low conf", approach="prune"
        )
        result = await wired_loop._run_experiment(exp)

        assert result is not None
        assert result.status == "kept"
        assert "1 low-confidence" in result.outcome
        mock_memory.search.assert_called_once()


# ── 11. Run experiment — no handler ──────────────────────────────


class TestRunExperimentNoHandler:
    @pytest.mark.asyncio
    async def test_unknown_area_discarded(self, auto_loop: AutonomousLoop):
        exp = Experiment(
            id="exp_u1", area="unknown_area", hypothesis="h", approach="a"
        )
        result = await auto_loop._run_experiment(exp)

        assert result is not None
        assert result.status == "discarded"
        assert "No handler" in result.outcome

    @pytest.mark.asyncio
    async def test_knowledge_without_collab_discarded(self, auto_loop: AutonomousLoop):
        exp = Experiment(
            id="exp_u2", area="knowledge", hypothesis="h", approach="a"
        )
        result = await auto_loop._run_experiment(exp)
        assert result is not None
        assert result.status == "discarded"


# ── 12. Learn ────────────────────────────────────────────────────


class TestLearn:
    @pytest.mark.asyncio
    async def test_learn_stores_memory(self, wired_loop, mock_memory):
        cycle_results = {
            "cycle": 1,
            "experiments_run": 2,
            "kept": 1,
            "discarded": 1,
        }
        await wired_loop._learn(cycle_results)

        mock_memory.store.assert_called_once()
        stored_entry = mock_memory.store.call_args[0][0]
        assert "cycle #1" in stored_entry.content
        assert "2 experiments run" in stored_entry.content
        assert stored_entry.confidence == 0.8
        assert "autonomous" in stored_entry.tags
        assert stored_entry.source == "autonomous_loop"

    @pytest.mark.asyncio
    async def test_learn_no_memory_noop(self, auto_loop: AutonomousLoop):
        # Should not raise when memory is None
        await auto_loop._learn({"cycle": 1, "experiments_run": 0, "kept": 0, "discarded": 0})


# ── 13. Run cycle (full) ────────────────────────────────────────


class TestRunCycle:
    @pytest.mark.asyncio
    async def test_full_cycle(self, wired_loop, mock_bus):
        results = await wired_loop.run_cycle()

        assert results["cycle"] == 1
        assert results["experiments_proposed"] > 0
        assert results["experiments_run"] > 0
        assert results["kept"] + results["discarded"] == results["experiments_run"]
        assert wired_loop._cycle_count == 1

        # Bus should be notified
        mock_bus.create_message.assert_called_once()
        mock_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_cycle_increments_count(self, wired_loop):
        await wired_loop.run_cycle()
        await wired_loop.run_cycle()
        assert wired_loop._cycle_count == 2

    @pytest.mark.asyncio
    async def test_cycle_respects_max_experiments(self, wired_loop, mock_self_dev):
        # Produce many gaps to generate many proposals
        mock_self_dev.assess.return_value = {
            "maturity_level": "intermediate",
            "maturity_score": 0.6,
            "capability_gaps": [f"gap_{i}" for i in range(20)],
            "evolution_count": 5,
        }
        results = await wired_loop.run_cycle()
        assert results["experiments_run"] <= AutonomousLoop.MAX_EXPERIMENTS_PER_CYCLE


# ── 14. Stop ─────────────────────────────────────────────────────


class TestStop:
    def test_stop_sets_running_false(self, auto_loop: AutonomousLoop):
        auto_loop._running = True
        auto_loop.stop()
        assert auto_loop._running is False

    def test_stop_cancels_task(self, auto_loop: AutonomousLoop):
        mock_task = MagicMock()
        auto_loop._task = mock_task
        auto_loop._running = True

        auto_loop.stop()

        assert auto_loop._running is False
        mock_task.cancel.assert_called_once()

    def test_stop_without_task(self, auto_loop: AutonomousLoop):
        auto_loop._running = True
        auto_loop._task = None
        auto_loop.stop()  # Should not raise
        assert auto_loop._running is False


# ── 15. Experiment immutability in loop ──────────────────────────


class TestExperimentImmutabilityInLoop:
    @pytest.mark.asyncio
    async def test_run_experiment_creates_new_objects(self, wired_loop):
        """Verify _run_experiment creates new Experiment instances (immutable pattern)."""
        exp = Experiment(id="exp_imm", area="knowledge", hypothesis="h", approach="a")
        original_list = list(wired_loop._experiments)

        result = await wired_loop._run_experiment(exp)

        # Original experiment is unchanged (frozen)
        assert exp.status == "proposed"
        # Result is a new object
        assert result is not exp
        assert result.status in ("kept", "discarded")
        # Internal list was replaced, not mutated
        assert wired_loop._experiments is not original_list


# ── 16. Learning engine integration ─────────────────────────────


class TestLearningEngineIntegration:
    @pytest.mark.asyncio
    async def test_records_outcome_on_success(self, wired_loop, mock_learning, mock_self_dev):
        exp = Experiment(id="exp_le1", area="skills", hypothesis="h", approach="a")
        await wired_loop._run_experiment(exp)

        mock_learning.record_experiment_outcome.assert_called_once()
        call_kwargs = mock_learning.record_experiment_outcome.call_args[1]
        assert call_kwargs["area"] == "skills"
        assert call_kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_records_outcome_on_failure(self, mock_learning, mock_memory):
        loop = AutonomousLoop(learning=mock_learning, memory=mock_memory)
        exp = Experiment(id="exp_le2", area="unknown", hypothesis="h", approach="a")
        await loop._run_experiment(exp)

        mock_learning.record_experiment_outcome.assert_called_once()
        call_kwargs = mock_learning.record_experiment_outcome.call_args[1]
        assert call_kwargs["success"] is False

    @pytest.mark.asyncio
    async def test_learning_record_failure_does_not_crash(self, wired_loop, mock_learning):
        mock_learning.record_experiment_outcome.side_effect = RuntimeError("db error")
        exp = Experiment(id="exp_le3", area="skills", hypothesis="h", approach="a")
        # Should not raise
        result = await wired_loop._run_experiment(exp)
        assert result is not None
        assert result.status == "kept"
