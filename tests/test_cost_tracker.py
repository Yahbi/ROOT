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


class TestComputeCostWithCache:
    def test_cache_read_reduces_cost(self):
        # Without cache: 1000 input @ $3/M + 500 output @ $15/M
        cost_no_cache = compute_cost("claude-sonnet-4-20250514", 1000, 500)
        # With 800 tokens from cache read (90% cheaper)
        cost_with_cache = compute_cost(
            "claude-sonnet-4-20250514", 1000, 500,
            cache_read_tokens=800,
        )
        assert cost_with_cache < cost_no_cache

    def test_cache_creation_costs_more_than_regular(self):
        # Cache creation has 25% premium
        cost_no_cache = compute_cost("claude-sonnet-4-20250514", 1000, 500)
        cost_with_write = compute_cost(
            "claude-sonnet-4-20250514", 1000, 500,
            cache_creation_tokens=800,
        )
        # Cache write is 25% MORE than regular for the cached portion
        assert cost_with_write > cost_no_cache

    def test_zero_cache_tokens_same_as_original(self):
        cost1 = compute_cost("claude-sonnet-4-20250514", 1000, 500)
        cost2 = compute_cost("claude-sonnet-4-20250514", 1000, 500,
                             cache_read_tokens=0, cache_creation_tokens=0)
        assert abs(cost1 - cost2) < 1e-10

    def test_unknown_model_uses_fallback_cache_rates(self):
        # Unknown model should use 0.1x and 1.25x of default input price
        cost = compute_cost(
            "unknown-model", 1000, 0,
            cache_read_tokens=1000,
        )
        # All 1000 input tokens are cache reads, none are regular
        # cache_read_price = 3.00 * 0.1 = 0.30 per M tokens
        expected = 1000 * 0.30 / 1e6
        assert abs(cost - expected) < 1e-10


class TestRecordWithCache:
    def test_record_with_cache_tokens(self, tracker):
        cost = tracker.record(
            provider="anthropic", model="claude-sonnet-4-20250514",
            input_tokens=1000, output_tokens=500,
            cache_read_tokens=800, cache_creation_tokens=0,
        )
        assert cost > 0
        row = tracker.conn.execute("SELECT * FROM llm_calls").fetchone()
        assert row["cache_read_tokens"] == 800
        assert row["cache_creation_tokens"] == 0

    def test_record_without_cache_tokens_defaults_zero(self, tracker):
        tracker.record(
            provider="anthropic", model="claude-sonnet-4-20250514",
            input_tokens=1000, output_tokens=500,
        )
        row = tracker.conn.execute("SELECT * FROM llm_calls").fetchone()
        assert row["cache_read_tokens"] == 0
        assert row["cache_creation_tokens"] == 0


class TestCacheSavings:
    def test_empty_cache_savings(self, tracker):
        savings = tracker.cache_savings()
        assert savings["cache_read_tokens"] == 0
        assert savings["cache_creation_tokens"] == 0
        assert savings["estimated_savings_usd"] == 0

    def test_cache_savings_with_data(self, tracker):
        tracker.record(
            provider="anthropic", model="claude-sonnet-4-20250514",
            input_tokens=10000, output_tokens=500,
            cache_read_tokens=8000, cache_creation_tokens=2000,
        )
        savings = tracker.cache_savings()
        assert savings["cache_read_tokens"] == 8000
        assert savings["cache_creation_tokens"] == 2000
        assert savings["estimated_savings_usd"] > 0


class TestBudgetEnforcement:
    def test_within_budget_no_limits(self, tracker, monkeypatch):
        monkeypatch.setattr(ct_mod, "LLM_DAILY_BUDGET", 0.0)
        monkeypatch.setattr(ct_mod, "LLM_MONTHLY_BUDGET", 0.0)
        assert tracker.is_within_budget() is True

    def test_within_budget_under_limit(self, tracker, monkeypatch):
        monkeypatch.setattr(ct_mod, "LLM_DAILY_BUDGET", 10.0)
        monkeypatch.setattr(ct_mod, "LLM_MONTHLY_BUDGET", 100.0)
        tracker.record(
            provider="anthropic", model="claude-sonnet-4-20250514",
            input_tokens=1000, output_tokens=500,
        )
        assert tracker.is_within_budget() is True

    def test_exceeds_daily_budget(self, tracker, monkeypatch):
        monkeypatch.setattr(ct_mod, "LLM_DAILY_BUDGET", 0.001)
        monkeypatch.setattr(ct_mod, "LLM_MONTHLY_BUDGET", 100.0)
        tracker.record(
            provider="anthropic", model="claude-sonnet-4-20250514",
            input_tokens=100000, output_tokens=50000,
        )
        assert tracker.is_within_budget() is False

    def test_exceeds_monthly_budget(self, tracker, monkeypatch):
        monkeypatch.setattr(ct_mod, "LLM_DAILY_BUDGET", 1000.0)
        monkeypatch.setattr(ct_mod, "LLM_MONTHLY_BUDGET", 0.001)
        tracker.record(
            provider="anthropic", model="claude-sonnet-4-20250514",
            input_tokens=100000, output_tokens=50000,
        )
        assert tracker.is_within_budget() is False

    def test_get_remaining_budget_no_limits(self, tracker, monkeypatch):
        monkeypatch.setattr(ct_mod, "LLM_DAILY_BUDGET", 0.0)
        monkeypatch.setattr(ct_mod, "LLM_MONTHLY_BUDGET", 0.0)
        remaining = tracker.get_remaining_budget()
        assert remaining["daily_limit"] is None
        assert remaining["monthly_limit"] is None
        assert remaining["daily_remaining"] is None
        assert remaining["monthly_remaining"] is None
        assert remaining["within_budget"] is True

    def test_get_remaining_budget_with_limits(self, tracker, monkeypatch):
        monkeypatch.setattr(ct_mod, "LLM_DAILY_BUDGET", 10.0)
        monkeypatch.setattr(ct_mod, "LLM_MONTHLY_BUDGET", 100.0)
        tracker.record(
            provider="anthropic", model="claude-sonnet-4-20250514",
            input_tokens=1000, output_tokens=500,
        )
        remaining = tracker.get_remaining_budget()
        assert remaining["daily_limit"] == 10.0
        assert remaining["monthly_limit"] == 100.0
        assert remaining["daily_remaining"] is not None
        assert remaining["daily_remaining"] > 0
        assert remaining["monthly_remaining"] is not None
        assert remaining["monthly_remaining"] > 0
        assert remaining["within_budget"] is True

    def test_get_remaining_budget_over_daily(self, tracker, monkeypatch):
        monkeypatch.setattr(ct_mod, "LLM_DAILY_BUDGET", 0.001)
        monkeypatch.setattr(ct_mod, "LLM_MONTHLY_BUDGET", 100.0)
        tracker.record(
            provider="anthropic", model="claude-sonnet-4-20250514",
            input_tokens=100000, output_tokens=50000,
        )
        remaining = tracker.get_remaining_budget()
        assert remaining["daily_remaining"] < 0
        assert remaining["within_budget"] is False


class TestMigration:
    def test_migrate_adds_cache_columns(self, tmp_path, monkeypatch):
        """Ensure migration adds columns to an old-schema table."""
        monkeypatch.setattr(ct_mod, "COST_DB", tmp_path / "costs.db")
        import sqlite3
        db = tmp_path / "costs.db"
        conn = sqlite3.connect(str(db))
        # Create table WITHOUT cache columns (old schema)
        conn.execute("""
            CREATE TABLE llm_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                model_tier TEXT DEFAULT 'default',
                caller_agent TEXT DEFAULT 'root',
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                total_tokens INTEGER NOT NULL,
                cost_usd REAL NOT NULL,
                duration_ms INTEGER DEFAULT 0,
                method TEXT DEFAULT 'complete'
            )
        """)
        conn.commit()
        conn.close()

        t = ct_mod.CostTracker(db_path=db)
        t.start()
        # Should be able to record with cache tokens after migration
        t.record(
            provider="anthropic", model="claude-sonnet-4-20250514",
            input_tokens=1000, output_tokens=500,
            cache_read_tokens=800,
        )
        row = t.conn.execute("SELECT cache_read_tokens FROM llm_calls").fetchone()
        assert row["cache_read_tokens"] == 800
        t.stop()


class TestStats:
    def test_stats_delegates_to_summary(self, tracker):
        tracker.record(provider="anthropic", model="claude-sonnet-4-20250514",
                       input_tokens=1000, output_tokens=500)
        stats = tracker.stats()
        assert stats["total_calls"] == 1
