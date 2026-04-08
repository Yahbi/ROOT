"""
Tests for enhanced LLM service features (v1.1):
- Response streaming with token usage emission
- Token counting / metadata via complete_with_metadata()
- Model fallback chain (Opus → Sonnet → Haiku)
- Built-in 5-minute prompt cache
- Health check
- Structured output (complete_json)
- Per-tier rate limiter stats
"""
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest

from backend.services.llm import (
    LLMService,
    LLMUnavailableError,
    _PromptCache,
    _TierRateLimiter,
    _FALLBACK_CHAIN,
    MODEL_TIERS,
    FAST_MODEL,
    DEFAULT_MODEL,
    THINKING_MODEL,
)
from backend.services.llm_openai import OpenAILLMService


# ── Helpers ────────────────────────────────────────────────────────

def _make_anthropic_response(text: str, input_tokens: int = 100, output_tokens: int = 50):
    """Build a mock Anthropic messages.create() response."""
    block = MagicMock()
    block.text = text
    block.type = "text"

    usage = MagicMock()
    usage.input_tokens = input_tokens
    usage.output_tokens = output_tokens
    usage.cache_read_input_tokens = 0
    usage.cache_creation_input_tokens = 0

    response = MagicMock()
    response.content = [block]
    response.usage = usage
    return response


def _make_openai_response(text: str, prompt_tokens: int = 100, completion_tokens: int = 50):
    """Build a mock OpenAI chat.completions.create() response."""
    message = MagicMock()
    message.content = text
    message.tool_calls = None

    choice = MagicMock()
    choice.message = message

    usage = MagicMock()
    usage.prompt_tokens = prompt_tokens
    usage.completion_tokens = completion_tokens

    response = MagicMock()
    response.choices = [choice]
    response.usage = usage
    return response


# ═══════════════════════════════════════════════════════════════════
# _PromptCache tests
# ═══════════════════════════════════════════════════════════════════

class TestPromptCache:

    @pytest.fixture(autouse=True)
    def _cache(self):
        self.cache = _PromptCache(ttl=300, max_size=10)

    @pytest.mark.asyncio
    async def test_miss_on_empty_cache(self):
        result = await self.cache.get("sys", [{"role": "user", "content": "hi"}], "default")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        msgs = [{"role": "user", "content": "hello"}]
        await self.cache.set("sys", msgs, "default", "response text")
        result = await self.cache.get("sys", msgs, "default")
        assert result == "response text"

    @pytest.mark.asyncio
    async def test_different_tiers_are_separate_entries(self):
        msgs = [{"role": "user", "content": "hello"}]
        await self.cache.set("sys", msgs, "fast", "fast response")
        result_default = await self.cache.get("sys", msgs, "default")
        result_fast = await self.cache.get("sys", msgs, "fast")
        assert result_default is None
        assert result_fast == "fast response"

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        cache = _PromptCache(ttl=0, max_size=10)  # 0s TTL = immediate expiry
        msgs = [{"role": "user", "content": "hi"}]
        await cache.set("", msgs, "default", "value")
        await asyncio.sleep(0.01)
        result = await cache.get("", msgs, "default")
        assert result is None

    @pytest.mark.asyncio
    async def test_empty_value_not_cached(self):
        msgs = [{"role": "user", "content": "hi"}]
        await self.cache.set("", msgs, "default", "")
        assert await self.cache.get("", msgs, "default") is None

    def test_stats_structure(self):
        stats = self.cache.stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "size" in stats
        assert "ttl_seconds" in stats


# ═══════════════════════════════════════════════════════════════════
# _TierRateLimiter tests
# ═══════════════════════════════════════════════════════════════════

class TestTierRateLimiter:

    @pytest.mark.asyncio
    async def test_acquire_under_limit_does_not_block(self):
        limiter = _TierRateLimiter({"fast": 10, "default": 5})
        start = time.monotonic()
        for _ in range(5):  # Under the 5 rpm limit for default
            await limiter.acquire("default")
        elapsed = time.monotonic() - start
        assert elapsed < 1.0  # Should complete quickly

    @pytest.mark.asyncio
    async def test_unknown_tier_uses_default_limit(self):
        limiter = _TierRateLimiter({"fast": 100})
        # "unknown" not in limits — defaults to 60 rpm, so single call is fine
        await limiter.acquire("unknown")

    def test_stats_structure(self):
        limiter = _TierRateLimiter({"fast": 120, "default": 60, "thinking": 5})
        stats = limiter.stats()
        assert "fast" in stats
        assert "default" in stats
        assert "thinking" in stats
        assert stats["thinking"]["rpm_limit"] == 5

    @pytest.mark.asyncio
    async def test_stats_current_usage_increments(self):
        limiter = _TierRateLimiter({"fast": 100})
        await limiter.acquire("fast")
        await limiter.acquire("fast")
        stats = limiter.stats()
        assert stats["fast"]["current_usage"] == 2


# ═══════════════════════════════════════════════════════════════════
# Fallback chain config tests
# ═══════════════════════════════════════════════════════════════════

class TestFallbackChain:

    def test_thinking_chain_order(self):
        assert _FALLBACK_CHAIN["thinking"] == ["thinking", "default", "fast"]

    def test_default_chain_order(self):
        assert _FALLBACK_CHAIN["default"] == ["default", "fast"]

    def test_fast_chain_is_single(self):
        assert _FALLBACK_CHAIN["fast"] == ["fast"]


# ═══════════════════════════════════════════════════════════════════
# LLMService — Anthropic
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def llm_service():
    """LLMService with mocked Anthropic client."""
    with patch("backend.services.llm.ANTHROPIC_API_KEY", "test-key"):
        with patch("backend.services.llm.anthropic.AsyncAnthropic") as mock_cls:
            svc = LLMService(api_key="test-key")
            svc._client = mock_cls.return_value
            yield svc


class TestLLMServiceComplete:

    @pytest.mark.asyncio
    async def test_complete_returns_text(self, llm_service):
        resp = _make_anthropic_response("hello world")
        llm_service._client.messages.create = AsyncMock(return_value=resp)
        # Patch via the service's own references to avoid module-level instance patching issues
        llm_service.rate_limiter.acquire = AsyncMock()
        llm_service.prompt_cache.get = AsyncMock(return_value=None)
        llm_service.prompt_cache.set = AsyncMock()
        result = await llm_service.complete(
            messages=[{"role": "user", "content": "hi"}],
        )
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_prompt_cache_hit_skips_api(self, llm_service):
        llm_service.rate_limiter.acquire = AsyncMock()
        llm_service.prompt_cache.get = AsyncMock(return_value="cached")
        result = await llm_service.complete(
            messages=[{"role": "user", "content": "hi"}],
        )
        # API should not have been called
        llm_service._client.messages.create.assert_not_called()
        assert result == "cached"

    @pytest.mark.asyncio
    async def test_use_cache_false_bypasses_cache(self, llm_service):
        resp = _make_anthropic_response("fresh response")
        llm_service._client.messages.create = AsyncMock(return_value=resp)
        llm_service.rate_limiter.acquire = AsyncMock()
        # Even if cache has a value, use_cache=False should call the API
        llm_service.prompt_cache.get = AsyncMock(return_value="cached")
        llm_service.prompt_cache.set = AsyncMock()
        result = await llm_service.complete(
            messages=[{"role": "user", "content": "hi"}],
            use_cache=False,
        )
        assert result == "fresh response"
        llm_service._client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self, llm_service):
        """When Opus fails after retries, it should fall back to Sonnet."""
        import anthropic as ant
        # First call (thinking tier) raises, second call (default tier) succeeds
        call_count = 0

        async def side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if kwargs.get("model") == THINKING_MODEL:
                raise ant.InternalServerError(
                    message="server error",
                    response=MagicMock(status_code=500, headers={}),
                    body={},
                )
            return _make_anthropic_response("fallback response")

        llm_service._client.messages.create = side_effect
        llm_service.rate_limiter.acquire = AsyncMock()
        llm_service.prompt_cache.get = AsyncMock(return_value=None)
        llm_service.prompt_cache.set = AsyncMock()
        with patch("backend.services.llm.asyncio.sleep", new_callable=AsyncMock):
            result = await llm_service.complete(
                messages=[{"role": "user", "content": "hi"}],
                model_tier="thinking",
            )
        assert result == "fallback response"

    @pytest.mark.asyncio
    async def test_no_fallback_when_disabled(self, llm_service):
        """With fallback=False, a single-tier failure raises LLMUnavailableError."""
        import anthropic as ant

        async def always_fail(**kwargs):
            raise ant.InternalServerError(
                message="server error",
                response=MagicMock(status_code=500, headers={}),
                body={},
            )

        llm_service._client.messages.create = always_fail
        llm_service.rate_limiter.acquire = AsyncMock()
        llm_service.prompt_cache.get = AsyncMock(return_value=None)
        llm_service.prompt_cache.set = AsyncMock()
        with patch("backend.services.llm.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(LLMUnavailableError):
                await llm_service.complete(
                    messages=[{"role": "user", "content": "hi"}],
                    model_tier="fast",
                    fallback=False,
                )


class TestLLMServiceMetadata:

    @pytest.mark.asyncio
    async def test_complete_with_metadata_returns_token_counts(self, llm_service):
        resp = _make_anthropic_response("hello", input_tokens=200, output_tokens=80)
        llm_service._client.messages.create = AsyncMock(return_value=resp)
        llm_service.rate_limiter.acquire = AsyncMock()
        text, meta = await llm_service.complete_with_metadata(
            messages=[{"role": "user", "content": "hi"}],
        )
        assert text == "hello"
        assert meta["input_tokens"] == 200
        assert meta["output_tokens"] == 80
        assert "model" in meta
        assert "tier" in meta


class TestLLMServiceCompleteJson:

    @pytest.mark.asyncio
    async def test_complete_json_parses_valid_json(self, llm_service):
        resp = _make_anthropic_response('{"key": "value", "count": 42}')
        llm_service._client.messages.create = AsyncMock(return_value=resp)
        # complete_json calls complete() with use_cache=False, only rate limiter fires
        llm_service.rate_limiter.acquire = AsyncMock()
        result = await llm_service.complete_json(
            messages=[{"role": "user", "content": "return json"}],
        )
        assert result == {"key": "value", "count": 42}

    @pytest.mark.asyncio
    async def test_complete_json_strips_markdown_fences(self, llm_service):
        resp = _make_anthropic_response('```json\n{"status": "ok"}\n```')
        llm_service._client.messages.create = AsyncMock(return_value=resp)
        llm_service.rate_limiter.acquire = AsyncMock()
        result = await llm_service.complete_json(
            messages=[{"role": "user", "content": "return json"}],
        )
        assert result == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_complete_json_returns_empty_on_persistent_failure(self, llm_service):
        # Always return invalid JSON
        resp = _make_anthropic_response("not json at all")
        # 3 retries × MAX_RETRIES (3) API calls → need the mock to return always
        llm_service._client.messages.create = AsyncMock(return_value=resp)
        llm_service.rate_limiter.acquire = AsyncMock()
        result = await llm_service.complete_json(
            messages=[{"role": "user", "content": "return json"}],
        )
        assert result == {}


class TestLLMServiceHealthCheck:

    @pytest.mark.asyncio
    async def test_health_check_success(self, llm_service):
        resp = _make_anthropic_response("pong")
        llm_service._client.messages.create = AsyncMock(return_value=resp)
        result = await llm_service.health_check()
        assert result["ok"] is True
        assert result["provider"] == "anthropic"
        assert "latency_ms" in result
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_health_check_failure(self, llm_service):
        llm_service._client.messages.create = AsyncMock(side_effect=Exception("connection refused"))
        result = await llm_service.health_check()
        assert result["ok"] is False
        assert result["error"] == "connection refused"
        assert result["provider"] == "anthropic"

    def test_rate_limit_stats(self, llm_service):
        stats = llm_service.rate_limit_stats()
        assert "thinking" in stats
        assert "default" in stats
        assert "fast" in stats

    def test_cache_stats(self, llm_service):
        stats = llm_service.cache_stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "size" in stats


# ═══════════════════════════════════════════════════════════════════
# LLMService — stream with usage emission
# ═══════════════════════════════════════════════════════════════════

class TestLLMServiceStream:

    @pytest.mark.asyncio
    async def test_stream_yields_chunks(self):
        """stream() yields text chunks from the Anthropic streaming API."""
        with patch("backend.services.llm.ANTHROPIC_API_KEY", "test-key"):
            with patch("backend.services.llm.anthropic.AsyncAnthropic") as mock_cls:
                svc = LLMService(api_key="test-key")

                # Mock the stream context manager
                chunks = ["Hello", " ", "world"]
                mock_stream = AsyncMock()
                mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
                mock_stream.__aexit__ = AsyncMock(return_value=False)
                mock_stream.text_stream = _async_iter(chunks)

                svc._client.messages.stream = MagicMock(return_value=mock_stream)

                with patch("backend.services.llm._rate_limiter.acquire", new_callable=AsyncMock):
                    collected = []
                    async for chunk in svc.stream(
                        messages=[{"role": "user", "content": "hi"}],
                    ):
                        collected.append(chunk)

                assert collected == chunks

    @pytest.mark.asyncio
    async def test_stream_with_emit_usage_yields_usage_sentinel(self):
        """With emit_usage=True, the final yielded item is the usage JSON sentinel."""
        with patch("backend.services.llm.ANTHROPIC_API_KEY", "test-key"):
            with patch("backend.services.llm.anthropic.AsyncAnthropic") as mock_cls:
                svc = LLMService(api_key="test-key")

                usage = MagicMock()
                usage.input_tokens = 10
                usage.output_tokens = 5
                usage.cache_read_input_tokens = 0
                usage.cache_creation_input_tokens = 0
                final_msg = MagicMock()
                final_msg.usage = usage
                final_msg.content = []

                mock_stream = AsyncMock()
                mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
                mock_stream.__aexit__ = AsyncMock(return_value=False)
                mock_stream.text_stream = _async_iter(["hi"])
                mock_stream.get_final_message = AsyncMock(return_value=final_msg)

                svc._client.messages.stream = MagicMock(return_value=mock_stream)

                with patch("backend.services.llm._rate_limiter.acquire", new_callable=AsyncMock):
                    collected = []
                    async for chunk in svc.stream(
                        messages=[{"role": "user", "content": "hi"}],
                        emit_usage=True,
                    ):
                        collected.append(chunk)

                assert collected[-1].startswith("__usage__:")
                usage_data = json.loads(collected[-1].replace("__usage__:", ""))
                assert usage_data["input_tokens"] == 10
                assert usage_data["output_tokens"] == 5


# ═══════════════════════════════════════════════════════════════════
# OpenAILLMService tests
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
def oai_service():
    """OpenAILLMService with mocked OpenAI client."""
    with patch("backend.services.llm_openai.OPENAI_API_KEY", "test-key"):
        with patch("backend.services.llm_openai.AsyncOpenAI") as mock_cls:
            svc = OpenAILLMService(api_key="test-key")
            svc._client = mock_cls.return_value
            yield svc


class TestOpenAILLMServiceComplete:

    @pytest.mark.asyncio
    async def test_complete_returns_text(self, oai_service):
        resp = _make_openai_response("hello openai")
        oai_service._client.chat.completions.create = AsyncMock(return_value=resp)
        # Patch the rate limiter and cache via the service's own references
        oai_service.rate_limiter.acquire = AsyncMock()
        oai_service.prompt_cache.get = AsyncMock(return_value=None)
        oai_service.prompt_cache.set = AsyncMock()
        result = await oai_service.complete(
            messages=[{"role": "user", "content": "hi"}],
        )
        assert result == "hello openai"

    @pytest.mark.asyncio
    async def test_prompt_cache_hit_skips_api(self, oai_service):
        oai_service.rate_limiter.acquire = AsyncMock()
        oai_service.prompt_cache.get = AsyncMock(return_value="cached_oai")
        result = await oai_service.complete(
            messages=[{"role": "user", "content": "hi"}],
        )
        oai_service._client.chat.completions.create.assert_not_called()
        assert result == "cached_oai"

    @pytest.mark.asyncio
    async def test_complete_with_metadata_returns_token_counts(self, oai_service):
        resp = _make_openai_response("response", prompt_tokens=150, completion_tokens=75)
        oai_service._client.chat.completions.create = AsyncMock(return_value=resp)
        oai_service.rate_limiter.acquire = AsyncMock()
        text, meta = await oai_service.complete_with_metadata(
            messages=[{"role": "user", "content": "hi"}],
        )
        assert text == "response"
        assert meta["input_tokens"] == 150
        assert meta["output_tokens"] == 75


class TestOpenAILLMServiceJson:

    @pytest.mark.asyncio
    async def test_complete_json_parses_json_object(self, oai_service):
        resp = _make_openai_response('{"result": "ok"}')
        oai_service._client.chat.completions.create = AsyncMock(return_value=resp)
        oai_service.rate_limiter.acquire = AsyncMock()
        result = await oai_service.complete_json(
            messages=[{"role": "user", "content": "give me json"}],
        )
        assert result == {"result": "ok"}

    @pytest.mark.asyncio
    async def test_complete_json_strips_markdown(self, oai_service):
        resp = _make_openai_response('```json\n{"foo": "bar"}\n```')
        oai_service._client.chat.completions.create = AsyncMock(return_value=resp)
        oai_service.rate_limiter.acquire = AsyncMock()
        result = await oai_service.complete_json(
            messages=[{"role": "user", "content": "json please"}],
        )
        assert result == {"foo": "bar"}


class TestOpenAILLMServiceHealthCheck:

    @pytest.mark.asyncio
    async def test_health_check_success(self, oai_service):
        resp = _make_openai_response("pong")
        oai_service._client.chat.completions.create = AsyncMock(return_value=resp)
        result = await oai_service.health_check()
        assert result["ok"] is True
        assert result["provider"] == "openai"
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_health_check_failure(self, oai_service):
        oai_service._client.chat.completions.create = AsyncMock(side_effect=Exception("timeout"))
        result = await oai_service.health_check()
        assert result["ok"] is False
        assert "timeout" in result["error"]

    def test_rate_limit_stats(self, oai_service):
        stats = oai_service.rate_limit_stats()
        assert "thinking" in stats
        assert "default" in stats

    def test_cache_stats(self, oai_service):
        stats = oai_service.cache_stats()
        assert "hits" in stats
        assert "size" in stats


# ── Async iterator helper ──────────────────────────────────────────

async def _async_iter(items):
    """Yield items one by one as an async iterator."""
    for item in items:
        yield item
