"""Tests for LLM Cost Tracker."""

from __future__ import annotations

import pytest

import backend.core.cost_tracker as ct_mod
from backend.core.cost_tracker import CostTracker, compute_cost


@pytest.fixture
def tracker(tmp_path, monkeypatch):
    monkeypatch.setattr(ct_mod, "COST_DB", tmp_path / "costs.db")
    t = CostTracker(db_path=tmp_path / "costs.db")
    t.start()
    yield t
    t.stop()


class TestComputeCost:
    def test_known_model(self):
        # claude-sonnet: $3/M input, $15/M output
        cost = compute_cost("claude-sonnet-4-20250514", 1000, 500)
        expected = 1000 * 3.0 / 1e6 + 500 * 15.0 / 1e6
        assert abs(cost - expected) < 1e-8

    def test_unknown_model_uses_default(self):
        cost = compute_cost("unknown-model", 1000, 500)
        expected = 1000 * 3.0 / 1e6 + 500 * 15.0 / 1e6
        assert abs(cost - expected) < 1e-8

    def test_zero_tokens(self):
        assert compute_cost("claude-sonnet-4-20250514", 0, 0) == 0.0

    def test_haiku_cheaper_than_sonnet(self):
        haiku = compute_cost("claude-haiku-4-5-20241022", 1000, 1000)
        sonnet = compute_cost("claude-sonnet-4-20250514", 1000, 1000)
        assert haiku < sonnet


class TestLifecycle:
    def test_start_creates_tables(self, tracker):
        tables = tracker.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        assert any(r["name"] == "llm_calls" for r in tables)

    def test_stop_closes_connection(self, tmp_path, monkeypatch):
        monkeypatch.setattr(ct_mod, "COST_DB", tmp_path / "costs.db")
        t = CostTracker(db_path=tmp_path / "costs.db")
        t.start()
        t.stop()
        assert t._conn is None

    def test_conn_raises_when_not_started(self):
        t = CostTracker()
        with pytest.raises(RuntimeError, match="not started"):
            _ = t.conn


class TestRecord:
    def test_record_returns_cost(self, tracker):
        cost = tracker.record(
            provider="anthropic", model="claude-sonnet-4-20250514",
            input_tokens=1000, output_tokens=500,
        )
        assert cost > 0

    def test_record_persists(self, tracker):
        tracker.record(
            provider="openai", model="gpt-4o",
            input_tokens=2000, output_tokens=1000,
            model_tier="default", caller_agent="researcher",
        )
        row = tracker.conn.execute("SELECT * FROM llm_calls").fetchone()
        assert row["provider"] == "openai"
        assert row["model"] == "gpt-4o"
        assert row["caller_agent"] == "researcher"
        assert row["input_tokens"] == 2000
        assert row["output_tokens"] == 1000
        assert row["total_tokens"] == 3000

    def test_record_multiple(self, tracker):
        for i in range(5):
            tracker.record(
                provider="anthropic", model="claude-sonnet-4-20250514",
                input_tokens=100 * (i + 1), output_tokens=50 * (i + 1),
            )
        count = tracker.conn.execute("SELECT COUNT(*) as c FROM llm_calls").fetchone()["c"]
        assert count == 5


class TestSummary:
    def test_empty_summary(self, tracker):
        s = tracker.summary()
        assert s["total_calls"] == 0
        assert s["total_cost_usd"] == 0
        assert s["daily"]["calls"] == 0
        assert s["weekly"]["calls"] == 0
        assert s["monthly"]["calls"] == 0

    def test_summary_with_data(self, tracker):
        tracker.record(provider="anthropic", model="claude-sonnet-4-20250514",
                       input_tokens=10000, output_tokens=5000)
        tracker.record(provider="openai", model="gpt-4o",
                       input_tokens=5000, output_tokens=2000)
        s = tracker.summary()
        assert s["total_calls"] == 2
        assert s["total_cost_usd"] > 0
        assert s["total_input_tokens"] == 15000
        assert s["total_output_tokens"] == 7000
        assert s["daily"]["calls"] == 2
        assert s["weekly"]["calls"] == 2
        assert s["monthly"]["calls"] == 2


class TestByAgent:
    def test_empty(self, tracker):
        assert tracker.by_agent() == []

    def test_grouped(self, tracker):
        tracker.record(provider="anthropic", model="claude-sonnet-4-20250514",
                       input_tokens=1000, output_tokens=500, caller_agent="astra")
        tracker.record(provider="anthropic", model="claude-sonnet-4-20250514",
                       input_tokens=2000, output_tokens=1000, caller_agent="astra")
        tracker.record(provider="anthropic", model="claude-sonnet-4-20250514",
                       input_tokens=500, output_tokens=200, caller_agent="miro")
        result = tracker.by_agent()
        assert len(result) == 2
        astra = next(r for r in result if r["agent"] == "astra")
        assert astra["calls"] == 2
        assert astra["input_tokens"] == 3000


class TestByModel:
    def test_empty(self, tracker):
        assert tracker.by_model() == []

    def test_grouped(self, tracker):
        tracker.record(provider="anthropic", model="claude-sonnet-4-20250514",
                       input_tokens=1000, output_tokens=500)
        tracker.record(provider="openai", model="gpt-4o",
                       input_tokens=1000, output_tokens=500)
        result = tracker.by_model()
        assert len(result) == 2
        models = {r["model"] for r in result}
        assert "claude-sonnet-4-20250514" in models
        assert "gpt-4o" in models


class TestDailyTrend:
    def test_empty(self, tracker):
        assert tracker.daily_trend() == []

    def test_with_data(self, tracker):
        tracker.record(provider="anthropic", model="claude-sonnet-4-20250514",
                       input_tokens=1000, output_tokens=500)
        trend = tracker.daily_trend(days=7)
        assert len(trend) == 1
        assert trend[0]["calls"] == 1
        assert trend[0]["cost_usd"] > 0


class TestStats:
    def test_stats_delegates_to_summary(self, tracker):
        tracker.record(provider="anthropic", model="claude-sonnet-4-20250514",
                       input_tokens=1000, output_tokens=500)
        stats = tracker.stats()
        assert stats["total_calls"] == 1
