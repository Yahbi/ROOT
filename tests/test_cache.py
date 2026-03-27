"""Tests for backend.core.cache — thread-safe TTL cache."""

import threading
import time

import pytest

from backend.core.cache import Cache, CacheEntry


# ------------------------------------------------------------------
# CacheEntry (frozen dataclass)
# ------------------------------------------------------------------


class TestCacheEntry:
    def test_immutable(self):
        entry = CacheEntry(key="k", value="v", expires_at=1.0, created_at=0.0)
        with pytest.raises(AttributeError):
            entry.key = "other"

    def test_fields(self):
        entry = CacheEntry(key="k", value=42, expires_at=10.0, created_at=5.0)
        assert entry.key == "k"
        assert entry.value == 42
        assert entry.expires_at == 10.0
        assert entry.created_at == 5.0


# ------------------------------------------------------------------
# Cache — basic get / set / delete / clear
# ------------------------------------------------------------------


class TestCacheBasicOps:
    @pytest.fixture(autouse=True)
    def _cache(self):
        self.cache = Cache(default_ttl=60, max_size=100, cleanup_interval=3600)
        yield
        self.cache.shutdown()

    def test_set_and_get(self):
        self.cache.set("a", "hello")
        assert self.cache.get("a") == "hello"

    def test_get_missing_key_returns_none(self):
        assert self.cache.get("nonexistent") is None

    def test_overwrite_existing_key(self):
        self.cache.set("a", 1)
        self.cache.set("a", 2)
        assert self.cache.get("a") == 2

    def test_delete_existing_key(self):
        self.cache.set("a", 1)
        assert self.cache.delete("a") is True
        assert self.cache.get("a") is None

    def test_delete_missing_key(self):
        assert self.cache.delete("nope") is False

    def test_clear_returns_count(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        assert self.cache.clear() == 2
        assert self.cache.get("a") is None
        assert self.cache.get("b") is None

    def test_clear_empty_cache(self):
        assert self.cache.clear() == 0

    def test_stores_various_value_types(self):
        self.cache.set("str", "hello")
        self.cache.set("int", 42)
        self.cache.set("list", [1, 2, 3])
        self.cache.set("dict", {"k": "v"})
        self.cache.set("none", None)

        assert self.cache.get("str") == "hello"
        assert self.cache.get("int") == 42
        assert self.cache.get("list") == [1, 2, 3]
        assert self.cache.get("dict") == {"k": "v"}
        # None value vs missing key: stats distinguish them
        assert self.cache.get("none") is None


# ------------------------------------------------------------------
# TTL expiration
# ------------------------------------------------------------------


class TestCacheTTL:
    @pytest.fixture(autouse=True)
    def _cache(self):
        self.cache = Cache(default_ttl=60, max_size=100, cleanup_interval=3600)
        yield
        self.cache.shutdown()

    def test_expired_entry_returns_none(self):
        self.cache.set("x", "val", ttl=0)
        # ttl=0 means expires immediately (at now + 0)
        time.sleep(0.01)
        assert self.cache.get("x") is None

    def test_entry_available_before_expiry(self):
        self.cache.set("x", "val", ttl=5)
        assert self.cache.get("x") == "val"

    def test_custom_ttl_overrides_default(self):
        self.cache.set("short", "val", ttl=0)
        self.cache.set("long", "val", ttl=300)
        time.sleep(0.01)
        assert self.cache.get("short") is None
        assert self.cache.get("long") == "val"


# ------------------------------------------------------------------
# Max-size eviction
# ------------------------------------------------------------------


class TestCacheEviction:
    @pytest.fixture(autouse=True)
    def _cache(self):
        self.cache = Cache(default_ttl=300, max_size=3, cleanup_interval=3600)
        yield
        self.cache.shutdown()

    def test_evicts_oldest_when_exceeding_max_size(self):
        self.cache.set("a", 1)
        time.sleep(0.001)
        self.cache.set("b", 2)
        time.sleep(0.001)
        self.cache.set("c", 3)
        time.sleep(0.001)
        # Adding a 4th entry should evict "a" (oldest created_at)
        self.cache.set("d", 4)

        assert self.cache.get("a") is None
        assert self.cache.get("b") == 2
        assert self.cache.get("c") == 3
        assert self.cache.get("d") == 4

    def test_evictions_counter_increments(self):
        for i in range(5):
            self.cache.set(f"k{i}", i)
            time.sleep(0.001)
        stats = self.cache.stats()
        assert stats["evictions"] == 2  # 5 inserted, max_size=3 → 2 evicted


# ------------------------------------------------------------------
# Stats — hits, misses, hit_rate
# ------------------------------------------------------------------


class TestCacheStats:
    @pytest.fixture(autouse=True)
    def _cache(self):
        self.cache = Cache(default_ttl=300, max_size=100, cleanup_interval=3600)
        yield
        self.cache.shutdown()

    def test_initial_stats(self):
        stats = self.cache.stats()
        assert stats == {
            "hits": 0,
            "misses": 0,
            "hit_rate": 0.0,
            "size": 0,
            "evictions": 0,
        }

    def test_hit_counting(self):
        self.cache.set("a", 1)
        self.cache.get("a")
        self.cache.get("a")
        assert self.cache.stats()["hits"] == 2

    def test_miss_counting(self):
        self.cache.get("missing1")
        self.cache.get("missing2")
        assert self.cache.stats()["misses"] == 2

    def test_expired_entry_counts_as_miss(self):
        self.cache.set("x", 1, ttl=0)
        time.sleep(0.01)
        self.cache.get("x")
        assert self.cache.stats()["misses"] == 1
        assert self.cache.stats()["hits"] == 0

    def test_hit_rate_calculation(self):
        self.cache.set("a", 1)
        self.cache.get("a")      # hit
        self.cache.get("a")      # hit
        self.cache.get("miss")   # miss
        stats = self.cache.stats()
        # 2 hits / 3 total = 0.6667
        assert stats["hit_rate"] == round(2 / 3, 4)

    def test_size_reflects_current_entries(self):
        self.cache.set("a", 1)
        self.cache.set("b", 2)
        assert self.cache.stats()["size"] == 2
        self.cache.delete("a")
        assert self.cache.stats()["size"] == 1


# ------------------------------------------------------------------
# Thread safety
# ------------------------------------------------------------------


class TestCacheThreadSafety:
    @pytest.fixture(autouse=True)
    def _cache(self):
        self.cache = Cache(default_ttl=300, max_size=10_000, cleanup_interval=3600)
        yield
        self.cache.shutdown()

    def test_concurrent_set_and_get(self):
        errors: list[str] = []
        barrier = threading.Barrier(4)

        def writer(prefix: str):
            barrier.wait()
            for i in range(200):
                self.cache.set(f"{prefix}_{i}", i)

        def reader(prefix: str):
            barrier.wait()
            for i in range(200):
                val = self.cache.get(f"{prefix}_{i}")
                if val is not None and val != i:
                    errors.append(f"Expected {i}, got {val}")

        threads = [
            threading.Thread(target=writer, args=("w1",)),
            threading.Thread(target=writer, args=("w2",)),
            threading.Thread(target=reader, args=("w1",)),
            threading.Thread(target=reader, args=("w2",)),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        assert errors == [], f"Thread safety violations: {errors}"


# ------------------------------------------------------------------
# Shutdown
# ------------------------------------------------------------------


class TestCacheShutdown:
    def test_shutdown_stops_cleanup_thread(self):
        cache = Cache(default_ttl=60, max_size=100, cleanup_interval=3600)
        cache.shutdown()
        # After shutdown, the cleanup thread should finish promptly
        cache._cleanup_thread.join(timeout=2)
        assert not cache._cleanup_thread.is_alive()

    def test_cache_still_works_after_shutdown(self):
        """Shutdown only stops the background thread; get/set still work."""
        cache = Cache(default_ttl=60, max_size=100, cleanup_interval=3600)
        cache.shutdown()
        cache.set("a", 1)
        assert cache.get("a") == 1
