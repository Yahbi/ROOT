"""Async in-memory LRU response cache for LLM calls.

Provides a thread-safe, asyncio-compatible cache that stores LLM responses
keyed by a hash of (system_prompt + user_message).  Supports per-entry TTL
and a maximum size with LRU eviction.

Usage::

    cache = AsyncResponseCache(max_size=1000)

    # Try cache first, compute on miss
    result = await cache.get_or_compute(
        key="abc123",
        compute_fn=my_async_llm_call,
        ttl=300,
    )

TTL defaults:
- Chat (interactive): 5 minutes (300 s)
- Background tasks: 30 minutes (1800 s)
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger("root.response_cache")

# ── TTL Presets ────────────────────────────────────────────────────
TTL_CHAT = 300       # 5 minutes for interactive chat
TTL_BACKGROUND = 1800  # 30 minutes for background / proactive tasks


@dataclass(frozen=True)
class _CacheEntry:
    """Immutable record for a cached response."""
    value: Any
    expires_at: float
    created_at: float


class AsyncResponseCache:
    """Async-safe in-memory LRU cache with per-entry TTL.

    Parameters
    ----------
    max_size:
        Maximum number of entries before LRU eviction kicks in.
    default_ttl:
        Default time-to-live in seconds when no explicit TTL is given.
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = TTL_CHAT) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._store: OrderedDict[str, _CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    # ── Public API ────────────────────────────────────────────────

    async def get(self, key: str) -> Optional[Any]:
        """Return the cached value for *key*, or ``None`` if missing/expired."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None

            if time.monotonic() >= entry.expires_at:
                del self._store[key]
                self._misses += 1
                return None

            # Move to end (most recently used)
            self._store.move_to_end(key)
            self._hits += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store *value* under *key* with an optional per-entry *ttl* (seconds)."""
        effective_ttl = ttl if ttl is not None else self._default_ttl
        now = time.monotonic()
        entry = _CacheEntry(
            value=value,
            expires_at=now + effective_ttl,
            created_at=now,
        )
        async with self._lock:
            self._store[key] = entry
            self._store.move_to_end(key)
            self._evict_if_needed()

    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Awaitable[Any]],
        ttl: Optional[int] = None,
    ) -> Any:
        """Return the cached value or compute it via *compute_fn*.

        If the key is missing or expired, calls ``await compute_fn()``
        and stores the result.  The compute is done outside the lock so
        other cache operations are not blocked by a slow LLM call.
        """
        # Fast-path: check cache
        cached = await self.get(key)
        if cached is not None:
            return cached

        # Compute outside the lock
        result = await compute_fn()

        # Store result (only if non-empty)
        if result:
            await self.set(key, result, ttl)

        return result

    async def delete(self, key: str) -> bool:
        """Remove *key* from the cache. Returns ``True`` if it existed."""
        async with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    async def clear(self) -> int:
        """Remove all entries. Returns the number of entries cleared."""
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            return count

    def stats(self) -> dict[str, Any]:
        """Return cache statistics (synchronous — safe for dashboard reads)."""
        total = self._hits + self._misses
        return {
            "size": len(self._store),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / max(total, 1), 4),
            "evictions": self._evictions,
        }

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def make_key(system_prompt: str, user_message: str) -> str:
        """Create a deterministic cache key from system prompt and user message.

        Hashes the combined content for a compact, collision-resistant key.
        """
        content = f"{system_prompt}|{user_message}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _evict_if_needed(self) -> None:
        """Evict oldest entries when cache exceeds max_size.

        Must be called while holding ``self._lock``.
        """
        while len(self._store) > self._max_size:
            self._store.popitem(last=False)
            self._evictions += 1
