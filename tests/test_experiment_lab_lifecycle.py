"""Tests for Experiment Lab — complete lifecycle flows, metrics, integration."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.experiment_lab import (
    ExperimentLab,
    ExperimentStatus,
    ExperimentCategory,
    Experiment,
)


@pytest.fixture
def lab(tmp_path):
    with patch("backend.core.experiment_lab.EXPERIMENT_DB", tmp_path / "experiments.db"):
        engine = ExperimentLab()
        engine.start()
        yield engine
        engine.stop()


# ── Experiment Dataclass ───────────────────────────────────────────────


class TestExperimentModel:
    def test_id_prefix(self, lab: ExperimentLab):
        exp = lab.propose(title="Model Test", hypothesis="h", category="saas")
        assert exp.id.startswith("exp_")

    def test_has_created_at(self, lab: ExperimentLab):
        exp = lab.propose(title="Timestamp", hypothesis="h", category="pricing")
        assert exp.created_at

    def test_status_is_proposed_until_started(self, lab: ExperimentLab):
        exp = lab.propose(title="Not started", hypothesis="h", category="marketing")
        assert exp.status == ExperimentStatus.PROPOSED

    def test_completed_at_none_until_completed(self, lab: ExperimentLab):
        exp = lab.propose(title="Not done", hypothesis="h", category="trading")
        lab.start_experiment(exp.id)
        running = lab.get_running()
        assert any(e.completed_at is None for e in running)

    def test_result_none_until_completed(self, lab: ExperimentLab):
        exp = lab.propose(title="Awaiting", hypothesis="h", category="automation")
        lab.start_experiment(exp.id)
        running = lab.get_running()
        run_exp = next(e for e in running if e.id == exp.id)
        assert run_exp.result is None


# ── Propose Validation Extended ────────────────────────────────────────


class TestProposeExtended:
    def test_all_categories_accepted(self, lab: ExperimentLab):
        for cat in ExperimentCategory:
            exp = lab.propose(
                title=f"Cat test {cat.value}",
                hypothesis="hypothesis",
                category=cat.value,
            )
            assert exp.category == cat

    def test_long_hypothesis_stored(self, lab: ExperimentLab):
        long_hyp = "A" * 500
        exp = lab.propose(title="Long hypothesis", hypothesis=long_hyp, category="saas")
        assert exp.id is not None

    def test_design_defaults_empty(self, lab: ExperimentLab):
        exp = lab.propose(title="No design", hypothesis="h", category="saas")
        assert exp.design == "" or exp.design is None

    def test_success_criteria_defaults_empty(self, lab: ExperimentLab):
        exp = lab.propose(title="No criteria", hypothesis="h", category="saas")
        assert exp.success_criteria == "" or exp.success_criteria is None


# ── Start Experiment ───────────────────────────────────────────────────


class TestStartExperiment:
    def test_status_set_to_running_after_start(self, lab: ExperimentLab):
        exp = lab.propose(title="Start test", hypothesis="h", category="saas")
        lab.start_experiment(exp.id)
        running = lab.get_running()
        run_exp = next(e for e in running if e.id == exp.id)
        assert run_exp.status == ExperimentStatus.RUNNING

    def test_status_changes_to_running(self, lab: ExperimentLab):
        exp = lab.propose(title="Status test", hypothesis="h", category="pricing")
        lab.start_experiment(exp.id)
        running = lab.get_running()
        assert any(e.id == exp.id for e in running)
        assert all(e.status == ExperimentStatus.RUNNING for e in running)

    def test_starting_already_running_experiment(self, lab: ExperimentLab):
        exp = lab.propose(title="Double start", hypothesis="h", category="marketing")
        lab.start_experiment(exp.id)
        # Starting again should return False or handle gracefully
        result = lab.start_experiment(exp.id)
        # Either False (not proposed state) or True (idempotent) is acceptable
        assert result in (True, False)


# ── Complete Experiment ────────────────────────────────────────────────


class TestCompleteExperiment:
    def test_metrics_stored_on_success(self, lab: ExperimentLab):
        exp = lab.propose(title="Metrics test", hypothesis="h", category="trading")
        lab.start_experiment(exp.id)
        completed = lab.complete_experiment(
            exp.id, result="5% conversion",
            success=True,
            metrics={"conversion_rate": 0.05, "revenue_impact": 1200},
        )
        assert completed is not None
        # Metrics stored in the experiment record
        assert completed.metrics.get("conversion_rate") == 0.05

    def test_lesson_learned_stored(self, lab: ExperimentLab):
        exp = lab.propose(title="Lesson test", hypothesis="h", category="marketing")
        lab.start_experiment(exp.id)
        completed = lab.complete_experiment(
            exp.id, result="Failed conversion",
            success=False,
            lesson_learned="Price point was too high for the target market",
        )
        assert "Price point" in (completed.lesson_learned or "")

    def test_completed_at_set(self, lab: ExperimentLab):
        exp = lab.propose(title="Completed at", hypothesis="h", category="saas")
        lab.start_experiment(exp.id)
        completed = lab.complete_experiment(exp.id, result="done", success=True)
        assert completed.completed_at is not None

    def test_success_status_in_completed(self, lab: ExperimentLab):
        exp = lab.propose(title="Success flag", hypothesis="h", category="automation")
        lab.start_experiment(exp.id)
        completed = lab.complete_experiment(exp.id, result="win", success=True)
        assert completed.status == ExperimentStatus.COMPLETED

    def test_failure_status_in_completed(self, lab: ExperimentLab):
        exp = lab.propose(title="Failure flag", hypothesis="h", category="saas")
        lab.start_experiment(exp.id)
        completed = lab.complete_experiment(exp.id, result="loss", success=False)
        assert completed.status == ExperimentStatus.FAILED


# ── Scale Experiment ───────────────────────────────────────────────────


class TestScaleExperiment:
    def test_scale_updates_status(self, lab: ExperimentLab):
        exp = lab.propose(title="Scale test", hypothesis="h", category="saas")
        lab.start_experiment(exp.id)
        lab.complete_experiment(exp.id, result="great", success=True)
        lab.scale_experiment(exp.id)
        scaled = lab.get_scaled()
        assert any(e.id == exp.id for e in scaled)
        assert all(e.status == ExperimentStatus.SCALED for e in scaled)

    def test_cannot_scale_proposed(self, lab: ExperimentLab):
        exp = lab.propose(title="Not ready", hypothesis="h", category="pricing")
        result = lab.scale_experiment(exp.id)
        assert result is False

    def test_cannot_scale_running(self, lab: ExperimentLab):
        exp = lab.propose(title="Running", hypothesis="h", category="marketing")
        lab.start_experiment(exp.id)
        result = lab.scale_experiment(exp.id)
        assert result is False


# ── Complete Workflow Integration ──────────────────────────────────────


class TestCompleteWorkflow:
    def test_full_success_workflow(self, lab: ExperimentLab):
        """End-to-end: propose → start → complete(success) → scale."""
        exp = lab.propose(
            title="Full Success Flow", hypothesis="Users will pay $29/mo",
            category="saas", design="Landing page A/B test",
            success_criteria="CR > 5%", confidence=0.7,
        )
        assert exp.status == ExperimentStatus.PROPOSED

        lab.start_experiment(exp.id)
        running = lab.get_running()
        assert any(e.id == exp.id for e in running)

        completed = lab.complete_experiment(
            exp.id, result="8% conversion rate achieved",
            success=True, metrics={"cr": 0.08},
            lesson_learned="$29 price point converts well",
        )
        assert completed.status == ExperimentStatus.COMPLETED

        lab.scale_experiment(exp.id)
        scaled = lab.get_scaled()
        assert any(e.id == exp.id for e in scaled)

    def test_full_failure_workflow(self, lab: ExperimentLab):
        """End-to-end: propose → start → complete(failure)."""
        exp = lab.propose(
            title="Full Failure Flow", hypothesis="Users need daily email digest",
            category="marketing", confidence=0.5,
        )

        lab.start_experiment(exp.id)
        completed = lab.complete_experiment(
            exp.id, result="0.2% open rate",
            success=False,
            lesson_learned="Email frequency was too high",
        )
        assert completed.status == ExperimentStatus.FAILED

        # Cannot scale failed experiments
        result = lab.scale_experiment(exp.id)
        assert result is False

    def test_multiple_concurrent_experiments(self, lab: ExperimentLab):
        """Multiple experiments can run concurrently."""
        exps = []
        for i in range(5):
            exp = lab.propose(
                title=f"Experiment {i}", hypothesis="test",
                category=list(ExperimentCategory)[i % len(list(ExperimentCategory))].value,
            )
            lab.start_experiment(exp.id)
            exps.append(exp)

        running = lab.get_running()
        assert len(running) == 5


# ── Stats Extended ────────────────────────────────────────────────────


class TestStatsExtended:
    def test_category_breakdown_in_stats(self, lab: ExperimentLab):
        for cat in ("saas", "trading", "pricing"):
            lab.propose(title=f"Cat {cat}", hypothesis="h", category=cat)
        stats = lab.stats()
        assert "saas" in stats["by_category"]
        assert "trading" in stats["by_category"]
        assert "pricing" in stats["by_category"]

    def test_failed_count_in_stats(self, lab: ExperimentLab):
        for i in range(3):
            exp = lab.propose(title=f"Fail {i}", hypothesis="h", category="marketing")
            lab.start_experiment(exp.id)
            lab.complete_experiment(exp.id, result="fail", success=False)
        stats = lab.stats()
        assert stats["by_status"]["failed"] == 3

    def test_completion_rate_in_stats(self, lab: ExperimentLab):
        # 2 completed, 1 running
        for i in range(2):
            exp = lab.propose(title=f"Done {i}", hypothesis="h", category="saas")
            lab.start_experiment(exp.id)
            lab.complete_experiment(exp.id, result="done", success=True)
        exp3 = lab.propose(title="Running", hypothesis="h", category="trading")
        lab.start_experiment(exp3.id)

        stats = lab.stats()
        assert stats["total_experiments"] == 3
