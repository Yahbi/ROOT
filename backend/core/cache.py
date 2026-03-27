"""
In-memory TTL cache — thread-safe with automatic background cleanup.

Provides a simple key-value cache with per-entry TTL, LRU-style eviction
when max_size is reached, and a daemon thread for periodic cleanup.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class CacheEntry:
    """Immutable record for a single cached value."""

    key: str
    value: Any
    expires_at: float
    created_at: float


class Cache:
    """Thread-safe in-memory cache with TTL expiration.

    Parameters
    ----------
    default_ttl:
        Default time-to-live in seconds for entries without an explicit TTL.
    max_size:
        Maximum number of entries. Oldest entries are evicted when exceeded.
    cleanup_interval:
        Seconds between automatic expired-entry sweeps.
    """

    def __init__(
        self,
        default_ttl: int = 300,
        max_size: int = 1000,
        cleanup_interval: int = 60,
    ) -> None:
        self._default_ttl = default_ttl
        self._max_size = max_size
        self._cleanup_interval = cleanup_interval

        self._store: dict[str, CacheEntry] = {}
        self._lock = threading.Lock()

        # Counters
        self._hits = 0
        self._misses = 0
        self._evictions = 0

        # Background cleanup daemon
        self._stop_event = threading.Event()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            daemon=True,
            name="cache-cleanup",
        )
        self._cleanup_thread.start()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[Any]:
        """Return the cached value for *key*, or ``None`` if missing/expired."""
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None

            if time.monotonic() >= entry.expires_at:
                del self._store[key]
                self._misses += 1
                return None

            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Store *value* under *key* with an optional per-entry *ttl*."""
        effective_ttl = ttl if ttl is not None else self._default_ttl
        now = time.monotonic()
        entry = CacheEntry(
            key=key,
            value=value,
            expires_at=now + effective_ttl,
            created_at=now,
        )

        with self._lock:
            self._store[key] = entry
            self._evict_if_needed()

    def delete(self, key: str) -> bool:
        """Remove *key* from the cache. Returns ``True`` if it existed."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def clear(self) -> int:
        """Remove all entries. Returns the number of entries cleared."""
        with self._lock:
            count = len(self._store)
            self._store = {}
            return count

    def stats(self) -> dict[str, Any]:
        """Return cache statistics (hits, misses, hit_rate, size, evictions)."""
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total) if total > 0 else 0.0
            return {
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 4),
                "size": len(self._store),
                "evictions": self._evictions,
            }

    def shutdown(self) -> None:
        """Signal the background cleanup thread to stop."""
        self._stop_event.set()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _cleanup(self) -> int:
        """Remove expired entries. Returns the number removed."""
        now = time.monotonic()
        removed = 0
        with self._lock:
            expired_keys = [
                k for k, entry in self._store.items()
                if now >= entry.expires_at
            ]
            for k in expired_keys:
                del self._store[k]
                removed += 1
        return removed

    def _evict_if_needed(self) -> None:
        """Evict oldest entries when cache exceeds max_size.

        Must be called while holding ``self._lock``.
        """
        while len(self._store) > self._max_size:
            oldest_key = min(
                self._store,
                key=lambda k: self._store[k].created_at,
            )
            del self._store[oldest_key]
            self._evictions += 1

    def _cleanup_loop(self) -> None:
        """Background loop that periodically removes expired entries."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._cleanup_interval)
            if not self._stop_event.is_set():
                self._cleanup()
