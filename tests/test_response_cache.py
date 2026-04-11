"""Tests for AsyncResponseCache — async LRU response cache."""

from __future__ import annotations

import pytest

from backend.core.response_cache import (
    TTL_BACKGROUND,
    TTL_CHAT,
    AsyncResponseCache,
)


class TestAsyncResponseCache:
    @pytest.mark.asyncio
    async def test_get_miss_returns_none(self):
        cache = AsyncResponseCache(max_size=10)
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_and_get(self):
        cache = AsyncResponseCache(max_size=10)
        await cache.set("key1", "value1", ttl=60)
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_expired_entry_returns_none(self):
        cache = AsyncResponseCache(max_size=10)
        await cache.set("key1", "value1", ttl=0)
        # TTL=0 means expired immediately
        import asyncio
        await asyncio.sleep(0.01)
        result = await cache.get("key1")
        assert result is None

    @pytest.mark.asyncio
    async def test_default_ttl_used(self):
        cache = AsyncResponseCache(max_size=10, default_ttl=60)
        await cache.set("key1", "value1")
        result = await cache.get("key1")
        assert result == "value1"

    @pytest.mark.asyncio
    async def test_eviction_when_full(self):
        cache = AsyncResponseCache(max_size=2)
        await cache.set("a", "val_a", ttl=60)
        await cache.set("b", "val_b", ttl=60)
        await cache.set("c", "val_c", ttl=60)
        # "a" should be evicted (LRU)
        assert await cache.get("a") is None
        assert await cache.get("b") == "val_b"
        assert await cache.get("c") == "val_c"

    @pytest.mark.asyncio
    async def test_get_or_compute_cache_hit(self):
        cache = AsyncResponseCache(max_size=10)
        await cache.set("key1", "cached_value", ttl=60)
        call_count = 0

        async def compute():
            nonlocal call_count
            call_count += 1
            return "computed_value"

        result = await cache.get_or_compute("key1", compute, ttl=60)
        assert result == "cached_value"
        assert call_count == 0  # compute_fn was not called

    @pytest.mark.asyncio
    async def test_get_or_compute_cache_miss(self):
        cache = AsyncResponseCache(max_size=10)
        call_count = 0

        async def compute():
            nonlocal call_count
            call_count += 1
            return "computed_value"

        result = await cache.get_or_compute("key1", compute, ttl=60)
        assert result == "computed_value"
        assert call_count == 1

        # Should be cached now
        result2 = await cache.get_or_compute("key1", compute, ttl=60)
        assert result2 == "computed_value"
        assert call_count == 1  # Not called again

    @pytest.mark.asyncio
    async def test_get_or_compute_empty_result_not_cached(self):
        cache = AsyncResponseCache(max_size=10)

        async def compute():
            return ""

        result = await cache.get_or_compute("key1", compute, ttl=60)
        assert result == ""
        # Empty result should not be cached
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete(self):
        cache = AsyncResponseCache(max_size=10)
        await cache.set("key1", "value1", ttl=60)
        assert await cache.delete("key1") is True
        assert await cache.get("key1") is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self):
        cache = AsyncResponseCache(max_size=10)
        assert await cache.delete("nonexistent") is False

    @pytest.mark.asyncio
    async def test_clear(self):
        cache = AsyncResponseCache(max_size=10)
        await cache.set("a", "1", ttl=60)
        await cache.set("b", "2", ttl=60)
        count = await cache.clear()
        assert count == 2
        assert cache.stats()["size"] == 0

    def test_stats(self):
        cache = AsyncResponseCache(max_size=100)
        stats = cache.stats()
        assert stats["size"] == 0
        assert stats["max_size"] == 100
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0

    @pytest.mark.asyncio
    async def test_stats_hit_miss(self):
        cache = AsyncResponseCache(max_size=10)
        await cache.set("a", "val", ttl=60)
        await cache.get("a")          # hit
        await cache.get("missing")    # miss
        stats = cache.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_make_key_deterministic(self):
        key1 = AsyncResponseCache.make_key("system prompt", "user message")
        key2 = AsyncResponseCache.make_key("system prompt", "user message")
        assert key1 == key2

    def test_make_key_different_inputs(self):
        key1 = AsyncResponseCache.make_key("system prompt", "msg1")
        key2 = AsyncResponseCache.make_key("system prompt", "msg2")
        assert key1 != key2

    def test_ttl_constants(self):
        assert TTL_CHAT == 300
        assert TTL_BACKGROUND == 1800

    @pytest.mark.asyncio
    async def test_eviction_counter(self):
        cache = AsyncResponseCache(max_size=2)
        await cache.set("a", "1", ttl=60)
        await cache.set("b", "2", ttl=60)
        await cache.set("c", "3", ttl=60)
        assert cache.stats()["evictions"] == 1
