"""Tests for Economic Router — smart tier selection, caching, budgets."""

from __future__ import annotations

import time

import pytest

from backend.core.economic_router import (
    BudgetConfig,
    CostBudget,
    EconomicRouter,
    ResponseCache,
    TaskProfile,
    classify_task,
)


# ── TaskProfile Classification ──────────────────────────────────


class TestClassifyTask:
    def test_trivial_greeting(self):
        p = classify_task("hello", method="complete", requested_tier="default")
        assert p.complexity == "trivial"
        assert p.recommended_tier == "fast"
        assert p.cacheable is True

    def test_trivial_thanks(self):
        p = classify_task("thanks for that", method="complete", requested_tier="default")
        assert p.complexity == "trivial"
        assert p.recommended_tier == "fast"

    def test_trivial_status(self):
        p = classify_task("status", method="complete", requested_tier="default")
        assert p.recommended_tier == "fast"

    def test_simple_summarize(self):
        p = classify_task("summarize this document for me please", method="complete", requested_tier="default")
        assert p.complexity == "simple"
        assert p.recommended_tier == "fast"

    def test_simple_translate(self):
        p = classify_task("translate this to French", method="complete", requested_tier="default")
        assert p.recommended_tier == "fast"

    def test_complex_analyze(self):
        p = classify_task("analyze the market trends for Q3 and provide a comprehensive report", method="complete", requested_tier="default")
        assert p.complexity == "complex"
        assert p.recommended_tier == "default"

    def test_complex_design(self):
        p = classify_task("design a microservice architecture for our payment system", method="complete", requested_tier="default")
        assert p.recommended_tier == "default"

    def test_critical_trade(self):
        p = classify_task("execute a trade on AAPL at $150", method="complete", requested_tier="default")
        assert p.complexity == "critical"
        assert p.cacheable is False

    def test_critical_deploy(self):
        p = classify_task("deploy this to production immediately", method="complete", requested_tier="default")
        assert p.complexity == "critical"
        assert p.cacheable is False

    def test_thinking_tier_preserved(self):
        p = classify_task("hello", method="complete", requested_tier="thinking")
        assert p.recommended_tier == "thinking"
        assert p.cacheable is False

    def test_protected_method_keeps_tier(self):
        p = classify_task("analyze something", method="thinking", requested_tier="default")
        assert p.recommended_tier == "default"
        assert p.cacheable is False

    def test_lightweight_method_uses_fast(self):
        p = classify_task("classify this text into categories", method="routing", requested_tier="default")
        assert p.recommended_tier == "fast"

    def test_short_prompt_uses_fast(self):
        p = classify_task("what is 2+2?", method="complete", requested_tier="default")
        assert p.recommended_tier == "fast"

    def test_moderate_short_default(self):
        # Under 300 chars, no complex keywords, default tier → fast
        p = classify_task("Tell me about the weather today in Paris", method="complete", requested_tier="default")
        assert p.recommended_tier == "fast"

    def test_returns_taskprofile(self):
        p = classify_task("hello", method="complete", requested_tier="default")
        assert isinstance(p, TaskProfile)
        assert isinstance(p.cache_ttl_seconds, int)


# ── Response Cache ──────────────────────────────────────────────


class TestResponseCache:
    def test_put_and_get(self):
        cache = ResponseCache(max_size=10)
        cache.put("sys", [{"role": "user", "content": "hi"}], "fast", "hello!", ttl_seconds=60)
        result = cache.get("sys", [{"role": "user", "content": "hi"}], "fast")
        assert result == "hello!"

    def test_miss_returns_none(self):
        cache = ResponseCache(max_size=10)
        result = cache.get("sys", [{"role": "user", "content": "hi"}], "fast")
        assert result is None

    def test_different_tier_is_miss(self):
        cache = ResponseCache(max_size=10)
        cache.put("sys", [{"role": "user", "content": "hi"}], "fast", "hello!")
        result = cache.get("sys", [{"role": "user", "content": "hi"}], "default")
        assert result is None

    def test_expired_entry_returns_none(self):
        cache = ResponseCache(max_size=10)
        cache.put("sys", [{"role": "user", "content": "hi"}], "fast", "hello!", ttl_seconds=0)
        # TTL=0 means expired immediately
        time.sleep(0.01)
        result = cache.get("sys", [{"role": "user", "content": "hi"}], "fast")
        assert result is None

    def test_evicts_oldest_when_full(self):
        cache = ResponseCache(max_size=2)
        cache.put("s", [{"role": "user", "content": "a"}], "fast", "resp_a")
        cache.put("s", [{"role": "user", "content": "b"}], "fast", "resp_b")
        cache.put("s", [{"role": "user", "content": "c"}], "fast", "resp_c")
        # "a" should be evicted
        assert cache.get("s", [{"role": "user", "content": "a"}], "fast") is None
        assert cache.get("s", [{"role": "user", "content": "b"}], "fast") == "resp_b"
        assert cache.get("s", [{"role": "user", "content": "c"}], "fast") == "resp_c"

    def test_invalidate(self):
        cache = ResponseCache(max_size=10)
        cache.put("sys", [{"role": "user", "content": "hi"}], "fast", "hello!")
        cache.invalidate("sys", [{"role": "user", "content": "hi"}], "fast")
        assert cache.get("sys", [{"role": "user", "content": "hi"}], "fast") is None

    def test_clear(self):
        cache = ResponseCache(max_size=10)
        cache.put("s", [{"role": "user", "content": "a"}], "fast", "resp_a")
        cache.put("s", [{"role": "user", "content": "b"}], "fast", "resp_b")
        cache.clear()
        assert cache.stats()["size"] == 0

    def test_stats_hit_miss(self):
        cache = ResponseCache(max_size=10)
        cache.put("s", [{"role": "user", "content": "a"}], "fast", "resp_a")
        cache.get("s", [{"role": "user", "content": "a"}], "fast")  # hit
        cache.get("s", [{"role": "user", "content": "b"}], "fast")  # miss
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_saved_usd_tracked(self):
        cache = ResponseCache(max_size=10)
        cache.put("s", [{"role": "user", "content": "a"}], "fast", "resp", estimated_cost=0.05)
        cache.get("s", [{"role": "user", "content": "a"}], "fast")
        assert cache.stats()["total_saved_usd"] == 0.05


# ── Cost Budget ──────────────────────────────────────────────────


class TestCostBudget:
    def test_no_tracker_allowed(self):
        budget = CostBudget()
        result = budget.check_budget(None)
        assert result["allowed"] is True

    def test_under_budget_ok(self):
        class FakeTracker:
            def summary(self):
                return {
                    "daily": {"cost_usd": 1.0},
                    "weekly": {"cost_usd": 5.0},
                    "monthly": {"cost_usd": 20.0},
                }
        budget = CostBudget(BudgetConfig(daily_limit_usd=50, weekly_limit_usd=200, monthly_limit_usd=500))
        result = budget.check_budget(FakeTracker())
        assert result["status"] == "ok"
        assert result["allowed"] is True

    def test_warning_at_threshold(self):
        class FakeTracker:
            def summary(self):
                return {
                    "daily": {"cost_usd": 42.0},
                    "weekly": {"cost_usd": 100.0},
                    "monthly": {"cost_usd": 200.0},
                }
        budget = CostBudget(BudgetConfig(daily_limit_usd=50, warning_threshold=0.8))
        result = budget.check_budget(FakeTracker())
        assert result["status"] == "warning"
        assert len(result["warnings"]) > 0

    def test_over_budget_soft_cap_allowed(self):
        class FakeTracker:
            def summary(self):
                return {
                    "daily": {"cost_usd": 55.0},
                    "weekly": {"cost_usd": 210.0},
                    "monthly": {"cost_usd": 200.0},
                }
        budget = CostBudget(BudgetConfig(daily_limit_usd=50, hard_cap=False))
        result = budget.check_budget(FakeTracker())
        assert result["status"] == "over_budget"
        assert result["allowed"] is True  # soft cap

    def test_over_budget_hard_cap_blocked(self):
        class FakeTracker:
            def summary(self):
                return {
                    "daily": {"cost_usd": 55.0},
                    "weekly": {"cost_usd": 210.0},
                    "monthly": {"cost_usd": 200.0},
                }
        budget = CostBudget(BudgetConfig(daily_limit_usd=50, hard_cap=True))
        result = budget.check_budget(FakeTracker())
        assert result["allowed"] is False

    def test_recommend_tier_under_budget(self):
        class FakeTracker:
            def summary(self):
                return {
                    "daily": {"cost_usd": 5.0},
                    "weekly": {"cost_usd": 20.0},
                    "monthly": {"cost_usd": 50.0},
                }
        budget = CostBudget(BudgetConfig(daily_limit_usd=50, weekly_limit_usd=200, monthly_limit_usd=500))
        assert budget.recommend_tier("thinking", FakeTracker()) == "thinking"
        assert budget.recommend_tier("default", FakeTracker()) == "default"

    def test_recommend_tier_high_pressure_downgrades(self):
        class FakeTracker:
            def summary(self):
                return {
                    "daily": {"cost_usd": 45.0},
                    "weekly": {"cost_usd": 180.0},
                    "monthly": {"cost_usd": 450.0},
                }
        budget = CostBudget(BudgetConfig(daily_limit_usd=50, weekly_limit_usd=200, monthly_limit_usd=500))
        assert budget.recommend_tier("thinking", FakeTracker()) == "default"
        assert budget.recommend_tier("default", FakeTracker()) == "fast"
        assert budget.recommend_tier("fast", FakeTracker()) == "fast"


# ── Economic Router (Integration) ───────────────────────────────


class TestEconomicRouter:
    def test_optimize_trivial_downgrades(self):
        router = EconomicRouter()
        result = router.optimize_call(
            system="You are helpful.",
            messages=[{"role": "user", "content": "hello"}],
            requested_tier="default",
        )
        assert result["tier"] == "fast"
        assert result["original_tier"] == "default"
        assert result["allowed"] is True

    def test_optimize_returns_cached(self):
        router = EconomicRouter()
        # Prime the cache
        router.record_response(
            system="sys", messages=[{"role": "user", "content": "hi"}],
            tier="fast", response="cached hello", cache_ttl=300,
        )
        result = router.optimize_call(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            requested_tier="fast",
        )
        assert result["cached_response"] == "cached hello"

    def test_optimize_critical_not_cached(self):
        router = EconomicRouter()
        result = router.optimize_call(
            system="sys",
            messages=[{"role": "user", "content": "execute trade on AAPL"}],
            requested_tier="default",
        )
        assert result["cacheable"] is False
        assert result["cached_response"] is None

    def test_stats(self):
        router = EconomicRouter()
        router.optimize_call(
            system="sys",
            messages=[{"role": "user", "content": "hello"}],
            requested_tier="default",
        )
        stats = router.stats()
        assert stats["total_calls"] == 1
        assert "cache" in stats
        assert "budget" in stats

    def test_record_response_enables_cache(self):
        router = EconomicRouter()
        router.record_response(
            system="s", messages=[{"role": "user", "content": "q"}],
            tier="fast", response="answer", cache_ttl=60,
        )
        assert router.cache.get("s", [{"role": "user", "content": "q"}], "fast") == "answer"

    def test_downgrade_tracked(self):
        router = EconomicRouter()
        router.optimize_call(
            system="sys",
            messages=[{"role": "user", "content": "hi there"}],
            requested_tier="default",
        )
        assert router.stats()["tier_downgrades"] >= 1

    def test_budget_block_tracked(self):
        class FakeTracker:
            def summary(self):
                return {
                    "daily": {"cost_usd": 999.0},
                    "weekly": {"cost_usd": 999.0},
                    "monthly": {"cost_usd": 999.0},
                }
        from backend.core.economic_router import BudgetConfig
        router = EconomicRouter(
            cost_tracker=FakeTracker(),
            budget_config=BudgetConfig(daily_limit_usd=10, hard_cap=True),
        )
        result = router.optimize_call(
            system="sys",
            messages=[{"role": "user", "content": "analyze everything deeply"}],
            requested_tier="default",
        )
        assert result["allowed"] is False
        assert router.stats()["budget_blocks"] == 1
