"""Tests for the Experiment Lab — continuous experimentation engine."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from backend.core.experiment_lab import ExperimentLab, ExperimentStatus


@pytest.fixture
def lab(tmp_path):
    with patch("backend.core.experiment_lab.EXPERIMENT_DB", tmp_path / "experiments.db"):
        engine = ExperimentLab()
        engine.start()
        yield engine
        engine.stop()


class TestPropose:
    def test_propose_returns_experiment(self, lab: ExperimentLab):
        exp = lab.propose(
            title="Test SaaS idea",
            hypothesis="Users will pay for AI writing tool",
            category="saas",
        )
        assert exp.id.startswith("exp_")
        assert exp.status == ExperimentStatus.PROPOSED
        assert exp.category.value == "saas"

    def test_propose_with_details(self, lab: ExperimentLab):
        exp = lab.propose(
            title="Pricing test",
            hypothesis="$29/mo converts better than $49/mo",
            category="pricing",
            design="A/B test on landing page",
            success_criteria="Conversion rate > 5%",
            confidence=0.7,
        )
        assert exp.design == "A/B test on landing page"
        assert exp.confidence == 0.7


class TestLifecycle:
    def test_start_experiment(self, lab: ExperimentLab):
        exp = lab.propose(title="t", hypothesis="h", category="saas")
        assert lab.start_experiment(exp.id) is True
        running = lab.get_running()
        assert len(running) == 1

    def test_start_nonexistent_fails(self, lab: ExperimentLab):
        assert lab.start_experiment("nonexistent") is False

    def test_complete_success(self, lab: ExperimentLab):
        exp = lab.propose(title="t", hypothesis="h", category="trading")
        lab.start_experiment(exp.id)
        result = lab.complete_experiment(
            exp.id, result="5% conversion", success=True,
            metrics={"conversion": 0.05}, lesson_learned="Price sensitivity is key",
        )
        assert result is not None
        assert result.status == ExperimentStatus.COMPLETED

    def test_complete_failure(self, lab: ExperimentLab):
        exp = lab.propose(title="t", hypothesis="h", category="marketing")
        lab.start_experiment(exp.id)
        result = lab.complete_experiment(
            exp.id, result="No signups", success=False,
            lesson_learned="Wrong audience",
        )
        assert result is not None
        assert result.status == ExperimentStatus.FAILED

    def test_scale_experiment(self, lab: ExperimentLab):
        exp = lab.propose(title="t", hypothesis="h", category="saas")
        lab.start_experiment(exp.id)
        lab.complete_experiment(exp.id, result="Great", success=True)
        assert lab.scale_experiment(exp.id) is True
        scaled = lab.get_scaled()
        assert len(scaled) == 1


class TestQueries:
    def test_get_by_category(self, lab: ExperimentLab):
        lab.propose(title="t1", hypothesis="h1", category="saas")
        lab.propose(title="t2", hypothesis="h2", category="trading")
        results = lab.get_by_category("saas")
        assert len(results) == 1

    def test_stats(self, lab: ExperimentLab):
        lab.propose(title="t1", hypothesis="h1", category="saas")
        exp = lab.propose(title="t2", hypothesis="h2", category="trading")
        lab.start_experiment(exp.id)
        stats = lab.stats()
        assert stats["total_experiments"] == 2
        assert stats["by_status"]["proposed"] == 1
        assert stats["by_status"]["running"] == 1
