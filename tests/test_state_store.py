"""Tests for the State Store — persistent runtime state."""

from __future__ import annotations

import pytest

from backend.core.state_store import StateStore


@pytest.fixture
def store(tmp_path):
    """Provide a StateStore with a temp database."""
    s = StateStore(db_path=tmp_path / "state.db")
    s.start()
    yield s
    s.stop()


class TestProactiveState:
    def test_save_and_load(self, store: StateStore):
        store.save_proactive_state(
            "health_monitor", run_count=5, error_count=1,
            last_run="2025-01-01T00:00:00Z", last_result="All healthy",
        )
        saved = store.load_proactive_state()
        assert "health_monitor" in saved
        assert saved["health_monitor"]["run_count"] == 5
        assert saved["health_monitor"]["error_count"] == 1
        assert saved["health_monitor"]["last_result"] == "All healthy"

    def test_update_existing(self, store: StateStore):
        store.save_proactive_state("action1", 1, 0, "t1", "ok")
        store.save_proactive_state("action1", 2, 0, "t2", "ok again")
        saved = store.load_proactive_state()
        assert saved["action1"]["run_count"] == 2

    def test_multiple_actions(self, store: StateStore):
        store.save_proactive_state("a", 1, 0, "t", "r")
        store.save_proactive_state("b", 2, 1, "t", "r")
        saved = store.load_proactive_state()
        assert len(saved) == 2


class TestExperiments:
    def test_save_and_load(self, store: StateStore):
        store.save_experiment(
            "exp1", area="routing", hypothesis="new routing improves accuracy",
            status="running",
        )
        experiments = store.load_experiments()
        assert len(experiments) >= 1
        assert experiments[0]["area"] == "routing"

    def test_update_experiment(self, store: StateStore):
        store.save_experiment(
            "exp1", area="routing", hypothesis="test",
            status="running",
        )
        store.save_experiment(
            "exp1", area="routing", hypothesis="test",
            status="completed", result="success",
        )
        experiments = store.load_experiments()
        assert experiments[0]["status"] == "completed"


class TestMeta:
    def test_set_and_get(self, store: StateStore):
        store.set_meta("cycle_count", "42")
        assert store.get_meta("cycle_count") == "42"

    def test_get_default(self, store: StateStore):
        assert store.get_meta("missing", "default") == "default"

    def test_overwrite(self, store: StateStore):
        store.set_meta("key", "v1")
        store.set_meta("key", "v2")
        assert store.get_meta("key") == "v2"


class TestPluginInvocations:
    def test_log_invocation(self, store: StateStore):
        store.log_plugin_invocation("test_plugin", "echo", True, 15)
        stats = store.get_plugin_stats()
        assert "echo" in stats

    def test_plugin_stats_aggregation(self, store: StateStore):
        store.log_plugin_invocation("test_plugin", "echo", True, 10)
        store.log_plugin_invocation("test_plugin", "echo", True, 20)
        store.log_plugin_invocation("test_plugin", "echo", False, 5)
        stats = store.get_plugin_stats()
        assert "echo" in stats
        assert stats["echo"]["total"] == 3
        assert stats["echo"]["success_rate"] == pytest.approx(2 / 3, abs=0.01)


class TestStats:
    def test_stats(self, store: StateStore):
        store.save_proactive_state("a", 1, 0, "t", "r")
        store.save_experiment("e1", area="test", hypothesis="test", status="completed")
        store.set_meta("k", "v")
        store.log_plugin_invocation("p", "t", True, 10)
        stats = store.stats()
        assert stats["proactive_actions_tracked"] >= 1
        assert stats["experiments_tracked"] >= 1
        assert stats["plugin_invocations_logged"] >= 1
