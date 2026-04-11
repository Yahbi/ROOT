"""Tests for Multi-Provider LLM Router."""

import time
from unittest.mock import patch

import pytest

from backend.services.llm import LLMUnavailableError
from backend.services.llm_router import (
    BACKGROUND_METHODS,
    CIRCUIT_OPEN_SECONDS,
    MAX_FAILURES_BEFORE_OPEN,
    MultiProviderLLMRouter,
    ProviderHealth,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class MockLLMService:
    """Minimal mock LLM service with async complete()."""

    def __init__(self, name: str = "mock", response: str = "ok"):
        self.provider = name
        self._response = response
        self.call_count = 0

    async def complete(self, **kwargs) -> str:
        self.call_count += 1
        return self._response


class FailingLLMService:
    """Mock LLM service that always raises LLMUnavailableError."""

    def __init__(self, name: str = "failing", error_msg: str = "service down"):
        self.provider = name
        self._error_msg = error_msg

    async def complete(self, **kwargs) -> str:
        raise LLMUnavailableError(self._error_msg)


class RateLimitLLMService:
    """Mock LLM service that raises a rate-limit error."""

    def __init__(self, name: str = "rate_limited"):
        self.provider = name

    async def complete(self, **kwargs) -> str:
        raise LLMUnavailableError("429 Too Many Requests")


# ===========================================================================
# ProviderHealth tests
# ===========================================================================

class TestProviderHealth:

    def test_is_available_default(self):
        h = ProviderHealth("test")
        assert h.is_available is True

    def test_record_success_resets_failures(self):
        h = ProviderHealth("test")
        h._failures = 2
        h._circuit_open = True
        h.record_success()
        assert h._failures == 0
        assert h._circuit_open is False
        assert h._total_successes == 1

    def test_record_failure_increments(self):
        h = ProviderHealth("test")
        h.record_failure()
        assert h._failures == 1
        assert h._total_failures == 1
        assert h._total_calls == 1

    def test_circuit_opens_after_max_failures(self):
        h = ProviderHealth("test")
        for _ in range(MAX_FAILURES_BEFORE_OPEN):
            h.record_failure()
        assert h._circuit_open is True
        assert h.is_available is False

    def test_circuit_closes_after_cooldown(self):
        h = ProviderHealth("test")
        for _ in range(MAX_FAILURES_BEFORE_OPEN):
            h.record_failure()
        assert h.is_available is False

        # Simulate cooldown elapsed
        h._last_failure = time.time() - CIRCUIT_OPEN_SECONDS - 1
        assert h.is_available is True

    def test_rate_limit_until_blocks_availability(self):
        h = ProviderHealth("test")
        h._rate_limited_until = time.time() + 60
        assert h.is_available is False

    def test_rate_limit_until_expired_allows_availability(self):
        h = ProviderHealth("test")
        h._rate_limited_until = time.time() - 1
        assert h.is_available is True

    def test_record_failure_with_rate_limit_sets_backoff(self):
        h = ProviderHealth("test")
        h.record_failure(is_rate_limit=True)
        assert h._rate_limited_until > time.time()

    def test_stats_returns_correct_structure(self):
        h = ProviderHealth("test_provider")
        h.record_success()
        h.record_failure()
        stats = h.stats()
        assert stats["name"] == "test_provider"
        assert "available" in stats
        assert "circuit_open" in stats
        assert "consecutive_failures" in stats
        assert stats["total_calls"] == 2
        assert stats["total_successes"] == 1
        assert stats["total_failures"] == 1


# ===========================================================================
# MultiProviderLLMRouter tests
# ===========================================================================

class TestMultiProviderLLMRouter:

    def test_add_provider(self):
        router = MultiProviderLLMRouter()
        svc = MockLLMService("alpha")
        router.add_provider("alpha", svc)
        assert "alpha" in router._providers
        assert "alpha" in router._health

    def test_remove_provider(self):
        svc = MockLLMService("alpha")
        router = MultiProviderLLMRouter(providers={"alpha": svc})
        router.remove_provider("alpha")
        assert "alpha" not in router._providers
        assert "alpha" not in router._health

    def test_remove_nonexistent_provider_no_error(self):
        router = MultiProviderLLMRouter()
        router.remove_provider("nonexistent")  # should not raise

    @pytest.mark.asyncio
    async def test_complete_calls_first_available_provider(self):
        svc_a = MockLLMService("a", response="response_a")
        svc_b = MockLLMService("b", response="response_b")
        router = MultiProviderLLMRouter(
            providers={"a": svc_a, "b": svc_b},
            priority=["a", "b"],
        )
        result = await router.complete(messages=[{"role": "user", "content": "hi"}])
        assert result == "response_a"
        assert svc_a.call_count == 1
        assert svc_b.call_count == 0

    @pytest.mark.asyncio
    async def test_failover_on_unavailable_error(self):
        svc_fail = FailingLLMService("fail")
        svc_ok = MockLLMService("ok", response="fallback_response")
        router = MultiProviderLLMRouter(
            providers={"fail": svc_fail, "ok": svc_ok},
            priority=["fail", "ok"],
        )
        result = await router.complete(messages=[{"role": "user", "content": "hi"}])
        assert result == "fallback_response"
        assert router._failovers == 1

    @pytest.mark.asyncio
    async def test_all_providers_fail_returns_empty_string(self):
        svc1 = FailingLLMService("a")
        svc2 = FailingLLMService("b")
        router = MultiProviderLLMRouter(
            providers={"a": svc1, "b": svc2},
            priority=["a", "b"],
        )
        result = await router.complete(messages=[{"role": "user", "content": "hi"}])
        assert result == ""

    @pytest.mark.asyncio
    async def test_rate_limit_detection_429(self):
        router = MultiProviderLLMRouter()
        err = LLMUnavailableError("429 Too Many Requests")
        assert router._is_rate_limit_error(err) is True

    @pytest.mark.asyncio
    async def test_rate_limit_detection_rate_limit_phrase(self):
        router = MultiProviderLLMRouter()
        assert router._is_rate_limit_error(Exception("rate limit exceeded")) is True

    @pytest.mark.asyncio
    async def test_rate_limit_detection_too_many_requests(self):
        router = MultiProviderLLMRouter()
        assert router._is_rate_limit_error(Exception("too many requests")) is True

    @pytest.mark.asyncio
    async def test_rate_limit_detection_normal_error(self):
        router = MultiProviderLLMRouter()
        assert router._is_rate_limit_error(Exception("connection refused")) is False

    @pytest.mark.asyncio
    async def test_background_priority_used_for_background_methods(self):
        svc_cheap = MockLLMService("ollama", response="cheap_response")
        svc_expensive = MockLLMService("anthropic", response="expensive_response")
        router = MultiProviderLLMRouter(
            providers={"ollama": svc_cheap, "anthropic": svc_expensive},
            priority=["anthropic", "ollama"],
            background_priority=["ollama", "anthropic"],
        )
        # Use a background method
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            method="routing",
        )
        assert result == "cheap_response"
        assert svc_cheap.call_count == 1
        assert svc_expensive.call_count == 0

    @pytest.mark.asyncio
    async def test_non_background_method_uses_default_priority(self):
        svc_cheap = MockLLMService("ollama", response="cheap_response")
        svc_expensive = MockLLMService("anthropic", response="expensive_response")
        router = MultiProviderLLMRouter(
            providers={"ollama": svc_cheap, "anthropic": svc_expensive},
            priority=["anthropic", "ollama"],
            background_priority=["ollama", "anthropic"],
        )
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            method="complete",
        )
        assert result == "expensive_response"
        assert svc_expensive.call_count == 1

    def test_stats_returns_correct_structure(self):
        svc = MockLLMService("alpha")
        router = MultiProviderLLMRouter(
            providers={"alpha": svc},
            priority=["alpha"],
        )
        stats = router.stats()
        assert "total_calls" in stats
        assert "failovers" in stats
        assert "failover_rate" in stats
        assert "active_provider" in stats
        assert "providers" in stats
        assert "priority" in stats
        assert "background_priority" in stats
        assert "registered" in stats
        assert stats["active_provider"] == "alpha"
        assert "alpha" in stats["providers"]

    def test_provider_property_returns_first_available(self):
        svc = MockLLMService("alpha")
        router = MultiProviderLLMRouter(
            providers={"alpha": svc},
            priority=["alpha"],
        )
        assert router.provider == "alpha"

    def test_provider_property_returns_offline_when_none_available(self):
        router = MultiProviderLLMRouter(providers={}, priority=["alpha"])
        assert router.provider == "offline"

    @pytest.mark.asyncio
    async def test_background_flag_uses_background_priority(self):
        svc_cheap = MockLLMService("ollama", response="cheap_response")
        svc_expensive = MockLLMService("anthropic", response="expensive_response")
        router = MultiProviderLLMRouter(
            providers={"ollama": svc_cheap, "anthropic": svc_expensive},
            priority=["anthropic", "ollama"],
            background_priority=["ollama", "anthropic"],
        )
        # Normal method but background=True should use background priority
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            method="complete",
            background=True,
        )
        assert result == "cheap_response"
        assert svc_cheap.call_count == 1
        assert svc_expensive.call_count == 0

    @pytest.mark.asyncio
    async def test_background_false_uses_default_priority(self):
        svc_cheap = MockLLMService("ollama", response="cheap_response")
        svc_expensive = MockLLMService("anthropic", response="expensive_response")
        router = MultiProviderLLMRouter(
            providers={"ollama": svc_cheap, "anthropic": svc_expensive},
            priority=["anthropic", "ollama"],
            background_priority=["ollama", "anthropic"],
        )
        result = await router.complete(
            messages=[{"role": "user", "content": "hi"}],
            method="complete",
            background=False,
        )
        assert result == "expensive_response"
        assert svc_expensive.call_count == 1

    @pytest.mark.asyncio
    async def test_complete_with_tools_background_flag(self):
        class MockToolService:
            def __init__(self, name, response="ok"):
                self.provider = name
                self._response = response
                self.call_count = 0

            async def complete_with_tools(self, **kwargs):
                self.call_count += 1
                return self._response, []

        svc_cheap = MockToolService("ollama", response="cheap")
        svc_expensive = MockToolService("anthropic", response="expensive")
        router = MultiProviderLLMRouter(
            providers={"ollama": svc_cheap, "anthropic": svc_expensive},
            priority=["anthropic", "ollama"],
            background_priority=["ollama", "anthropic"],
        )
        text, tools = await router.complete_with_tools(
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            background=True,
        )
        assert text == "cheap"
        assert svc_cheap.call_count == 1
        assert svc_expensive.call_count == 0

    @pytest.mark.asyncio
    async def test_rate_limit_error_triggers_backoff_on_health(self):
        svc_rl = RateLimitLLMService("rl")
        svc_ok = MockLLMService("ok", response="ok")
        router = MultiProviderLLMRouter(
            providers={"rl": svc_rl, "ok": svc_ok},
            priority=["rl", "ok"],
        )
        result = await router.complete(messages=[{"role": "user", "content": "hi"}])
        assert result == "ok"
        # The rate-limited provider should be marked
        health = router._health["rl"]
        assert health._rate_limited_until > time.time()
