"""
ROOT Embedding Service — dense semantic embeddings with caching.

Replaces the legacy TF-IDF hash-bucket embedder with a dual-provider
architecture: OpenAI text-embedding-3-small for high-quality embeddings,
and an improved local bag-of-words fallback with subword hash bucketing
and log-frequency weighting for zero-dependency operation.

Embeddings are cached in SQLite (WAL mode) keyed by content hash, so
identical texts are never re-embedded.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import math
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from backend.config import DATA_DIR, OPENAI_API_KEY

logger = logging.getLogger("root.embedding_service")

EMBEDDING_CACHE_DB = DATA_DIR / "embedding_cache.db"


# ── Immutable data models ────────────────────────────────────────


@dataclass(frozen=True)
class EmbeddingResult:
    """A single embedding result with metadata."""

    text_hash: str
    vector: np.ndarray
    dimension: int
    provider: str
    cached: bool = False

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, EmbeddingResult):
            return NotImplemented
        return self.text_hash == other.text_hash

    def __hash__(self) -> int:
        return hash(self.text_hash)


@dataclass(frozen=True)
class ProviderInfo:
    """Immutable descriptor for an embedding provider."""

    name: str
    model: str
    dimension: int
    available: bool
    reason: str = ""


# ── Local Embedder (improved bag-of-words) ───────────────────────


class LocalEmbedder:
    """Normalized bag-of-words embedder with subword hash bucketing.

    Improvements over the legacy TF-IDF approach:
    - Character n-gram (3-6) subword features capture morphology
    - Log-frequency weighting prevents common-token dominance
    - Dual hashing (positive + negative buckets) reduces collisions
    - L2 normalization for cosine-compatible vectors
    """

    def __init__(self, dimension: int = 1536) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase, normalize whitespace, extract word tokens (len >= 2)."""
        cleaned = re.sub(r"[^a-z0-9\s\-_]", " ", text.lower())
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return [t for t in cleaned.split() if len(t) >= 2]

    @staticmethod
    def _char_ngrams(token: str, min_n: int = 3, max_n: int = 6) -> list[str]:
        """Extract character n-grams from a token with boundary markers."""
        padded = f"<{token}>"
        ngrams: list[str] = []
        for n in range(min_n, min(max_n + 1, len(padded) + 1)):
            for i in range(len(padded) - n + 1):
                ngrams.append(padded[i : i + n])
        return ngrams

    def embed(self, text: str) -> np.ndarray:
        """Produce a fixed-dimension vector for the given text.

        Uses word tokens and character n-gram subword features,
        hashed into buckets with dual-sign hashing and log-frequency
        weighting. Returns a unit-normalized float32 vector.
        """
        tokens = self._tokenize(text)
        if not tokens:
            return np.zeros(self._dimension, dtype=np.float32)

        vector = np.zeros(self._dimension, dtype=np.float32)

        # Collect all features: word tokens + character n-grams
        features: dict[str, int] = {}
        for token in tokens:
            features[token] = features.get(token, 0) + 1
            for ngram in self._char_ngrams(token):
                features[ngram] = features.get(ngram, 0) + 1

        for feature, count in features.items():
            # Log-frequency weighting to dampen high-frequency features
            weight = 1.0 + math.log(count)

            # Primary hash determines the bucket
            h1 = hashlib.md5(feature.encode("utf-8")).hexdigest()
            bucket = int(h1, 16) % self._dimension

            # Secondary hash determines the sign (+1 or -1)
            # This reduces collision impact (features cancel instead of pile up)
            h2 = hashlib.md5(feature.encode("utf-8")[::-1]).hexdigest()
            sign = 1.0 if int(h2, 16) % 2 == 0 else -1.0

            vector[bucket] += sign * weight

        # L2 normalize for cosine similarity compatibility
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector.astype(np.float32)

    def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed a batch of texts locally."""
        return [self.embed(t) for t in texts]


# ── Embedding Service ────────────────────────────────────────────


class EmbeddingService:
    """Dense semantic embedding service with caching.

    Supports OpenAI API-based embeddings (text-embedding-3-small) and
    a local fallback. Embeddings are cached in SQLite keyed by a SHA-256
    hash of the input text, so identical content is never re-embedded.

    Parameters
    ----------
    provider:
        "openai", "local", or "auto" (try OpenAI, fall back to local).
    model:
        OpenAI model name (ignored for local provider).
    dimension:
        Embedding vector dimension.
    db_path:
        Path to the SQLite cache database. Defaults to DATA_DIR/embedding_cache.db.
    """

    def __init__(
        self,
        provider: str = "auto",
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
        db_path: Optional[Path] = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._dimension = dimension
        self._db_path = str(db_path or EMBEDDING_CACHE_DB)

        # State
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self._local_embedder = LocalEmbedder(dimension=dimension)
        self._resolved_provider: Optional[str] = None

        # Stats counters
        self._cache_hits = 0
        self._cache_misses = 0
        self._api_calls = 0
        self._api_errors = 0
        self._local_calls = 0
        self._total_embedded = 0

    # ── lifecycle ─────────────────────────────────────────────

    def start(self) -> None:
        """Open SQLite cache and create tables."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()
        self._resolve_provider()
        logger.info(
            "EmbeddingService started: provider=%s, model=%s, dim=%d, cache=%s",
            self._resolved_provider,
            self._model,
            self._dimension,
            self._db_path,
        )

    def stop(self) -> None:
        """Close the SQLite connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
        logger.info("EmbeddingService stopped")

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("EmbeddingService not started — call start() first")
        return self._conn

    @property
    def provider(self) -> str:
        """The resolved provider name ("openai" or "local")."""
        return self._resolved_provider or self._provider

    # ── schema ────────────────────────────────────────────────

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS embedding_cache (
                text_hash TEXT PRIMARY KEY,
                vector BLOB,
                dimension INTEGER,
                provider TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_embedding_cache_provider
                ON embedding_cache(provider);
        """)

    # ── provider resolution ───────────────────────────────────

    def _resolve_provider(self) -> None:
        """Determine which provider to use based on configuration."""
        if self._provider == "openai":
            if not OPENAI_API_KEY:
                logger.warning(
                    "Provider set to 'openai' but OPENAI_API_KEY is not configured; "
                    "embed() calls will fail unless the key is set before use"
                )
            self._resolved_provider = "openai"

        elif self._provider == "local":
            self._resolved_provider = "local"

        elif self._provider == "auto":
            if OPENAI_API_KEY:
                self._resolved_provider = "openai"
                logger.info("Auto-detected OpenAI API key — using OpenAI embeddings")
            else:
                self._resolved_provider = "local"
                logger.info(
                    "No OpenAI API key found — using local bag-of-words embeddings"
                )
        else:
            logger.warning(
                "Unknown provider '%s', falling back to local", self._provider
            )
            self._resolved_provider = "local"

    def _openai_available(self) -> bool:
        """Check whether OpenAI embeddings can be used right now."""
        return bool(OPENAI_API_KEY)

    # ── cache operations ──────────────────────────────────────

    @staticmethod
    def _text_hash(text: str) -> str:
        """SHA-256 hash of the text, used as cache key."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _cache_get(self, text_hash: str) -> Optional[np.ndarray]:
        """Look up a cached embedding by text hash. Returns None on miss."""
        with self._lock:
            row = self.conn.execute(
                "SELECT vector, dimension FROM embedding_cache WHERE text_hash = ?",
                (text_hash,),
            ).fetchone()

        if row is None:
            return None

        dim = row["dimension"]
        try:
            vector = np.frombuffer(row["vector"], dtype=np.float32, count=dim).copy()
            return vector
        except (ValueError, TypeError) as exc:
            logger.warning("Corrupt cache entry for %s: %s", text_hash[:16], exc)
            return None

    def _cache_put(
        self, text_hash: str, vector: np.ndarray, provider: str
    ) -> None:
        """Store an embedding in the cache."""
        blob = vector.astype(np.float32).tobytes()
        dimension = len(vector)
        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO embedding_cache
                   (text_hash, vector, dimension, provider)
                   VALUES (?, ?, ?, ?)""",
                (text_hash, blob, dimension, provider),
            )
            self.conn.commit()

    # ── OpenAI API embeddings ─────────────────────────────────

    async def _embed_openai(self, text: str) -> np.ndarray:
        """Call OpenAI embeddings API via httpx."""
        import httpx

        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": text,
            "model": self._model,
            "dimensions": self._dimension,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        embedding = data["data"][0]["embedding"]
        vector = np.array(embedding, dtype=np.float32)
        self._api_calls += 1
        return vector

    async def _embed_openai_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Call OpenAI embeddings API for a batch of texts."""
        import httpx

        url = "https://api.openai.com/v1/embeddings"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": texts,
            "model": self._model,
            "dimensions": self._dimension,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        # OpenAI returns embeddings sorted by index
        results = sorted(data["data"], key=lambda d: d["index"])
        vectors = [
            np.array(item["embedding"], dtype=np.float32) for item in results
        ]
        self._api_calls += 1
        return vectors

    # ── core embed methods ────────────────────────────────────

    async def embed(self, text: str) -> np.ndarray:
        """Embed a single text, checking cache first.

        Returns a numpy float32 vector of shape (dimension,).
        """
        if not text or not text.strip():
            return np.zeros(self._dimension, dtype=np.float32)

        text_hash = self._text_hash(text)

        # Check cache
        cached = self._cache_get(text_hash)
        if cached is not None:
            self._cache_hits += 1
            self._total_embedded += 1
            return cached

        self._cache_misses += 1

        # Compute embedding
        vector = await self._compute_embedding(text)
        provider = self._resolved_provider or "local"

        # Store in cache
        self._cache_put(text_hash, vector, provider)
        self._total_embedded += 1

        return vector

    async def embed_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Embed a batch of texts, checking cache for each.

        Uncached texts are embedded together via the active provider.
        Returns a list of numpy float32 vectors in the same order as input.
        """
        if not texts:
            return []

        results: list[Optional[np.ndarray]] = [None] * len(texts)
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        # Check cache for each text
        for i, text in enumerate(texts):
            if not text or not text.strip():
                results[i] = np.zeros(self._dimension, dtype=np.float32)
                continue

            text_hash = self._text_hash(text)
            cached = self._cache_get(text_hash)
            if cached is not None:
                results[i] = cached
                self._cache_hits += 1
            else:
                uncached_indices.append(i)
                uncached_texts.append(text)
                self._cache_misses += 1

        # Embed uncached texts
        if uncached_texts:
            vectors = await self._compute_embedding_batch(uncached_texts)
            provider = self._resolved_provider or "local"

            for idx, text, vector in zip(
                uncached_indices, uncached_texts, vectors
            ):
                results[idx] = vector
                self._cache_put(self._text_hash(text), vector, provider)

        self._total_embedded += len(texts)

        # All slots should be filled; satisfy the type checker
        return [r if r is not None else np.zeros(self._dimension, dtype=np.float32)
                for r in results]

    def embed_sync(self, text: str) -> np.ndarray:
        """Synchronous embedding for startup and non-async contexts.

        Runs the async embed() in a new event loop if necessary.
        """
        if not text or not text.strip():
            return np.zeros(self._dimension, dtype=np.float32)

        text_hash = self._text_hash(text)

        # Check cache first (no async needed)
        cached = self._cache_get(text_hash)
        if cached is not None:
            self._cache_hits += 1
            self._total_embedded += 1
            return cached

        self._cache_misses += 1

        # For sync path, prefer local to avoid event loop complexity at startup
        if self._resolved_provider == "openai" and self._openai_available():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # We're inside an async context — use local to avoid deadlock
                logger.debug(
                    "embed_sync called inside running loop; using local embedder"
                )
                vector = self._local_embedder.embed(text)
                provider = "local"
            else:
                # No running loop — safe to create one
                try:
                    vector = asyncio.run(self._embed_openai(text))
                    provider = "openai"
                except Exception as exc:
                    logger.warning(
                        "OpenAI embed failed in sync path, falling back to local: %s",
                        exc,
                    )
                    vector = self._local_embedder.embed(text)
                    provider = "local"
                    self._api_errors += 1
        else:
            vector = self._local_embedder.embed(text)
            provider = "local"
            self._local_calls += 1

        self._cache_put(text_hash, vector, provider)
        self._total_embedded += 1

        return vector

    # ── internal dispatch ─────────────────────────────────────

    async def _compute_embedding(self, text: str) -> np.ndarray:
        """Dispatch a single text to the resolved provider."""
        if self._resolved_provider == "openai" and self._openai_available():
            try:
                return await self._embed_openai(text)
            except Exception as exc:
                self._api_errors += 1
                if self._provider == "auto":
                    logger.warning(
                        "OpenAI embedding failed, falling back to local: %s", exc
                    )
                    self._local_calls += 1
                    return self._local_embedder.embed(text)
                else:
                    raise RuntimeError(
                        f"OpenAI embedding failed and provider is not 'auto': {exc}"
                    ) from exc

        self._local_calls += 1
        return self._local_embedder.embed(text)

    async def _compute_embedding_batch(
        self, texts: list[str]
    ) -> list[np.ndarray]:
        """Dispatch a batch of texts to the resolved provider."""
        if self._resolved_provider == "openai" and self._openai_available():
            try:
                return await self._embed_openai_batch(texts)
            except Exception as exc:
                self._api_errors += 1
                if self._provider == "auto":
                    logger.warning(
                        "OpenAI batch embedding failed (%d texts), "
                        "falling back to local: %s",
                        len(texts),
                        exc,
                    )
                    self._local_calls += len(texts)
                    return self._local_embedder.embed_batch(texts)
                else:
                    raise RuntimeError(
                        f"OpenAI batch embedding failed and provider is "
                        f"not 'auto': {exc}"
                    ) from exc

        self._local_calls += len(texts)
        return self._local_embedder.embed_batch(texts)

    # ── stats ─────────────────────────────────────────────────

    def stats(self) -> dict:
        """Return service statistics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests) if total_requests > 0 else 0.0

        cache_size = 0
        if self._conn:
            with self._lock:
                row = self.conn.execute(
                    "SELECT COUNT(*) as c FROM embedding_cache"
                ).fetchone()
                cache_size = row["c"] if row else 0

        return {
            "provider": self._resolved_provider or self._provider,
            "model": self._model,
            "dimension": self._dimension,
            "cache_size": cache_size,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "cache_hit_rate": round(hit_rate, 4),
            "api_calls": self._api_calls,
            "api_errors": self._api_errors,
            "local_calls": self._local_calls,
            "total_embedded": self._total_embedded,
            "db_path": self._db_path,
        }

    # ── TextEmbedder duck-type compatibility ───────────────────
    # MemoryEngine calls self._embedder.embed(content) and
    # self._embedder.partial_fit(content). These wrappers allow
    # EmbeddingService to be used as a drop-in replacement.

    def partial_fit(self, text: str) -> None:
        """No-op for API-based embeddings. Local embedder doesn't need fitting."""
        pass

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def is_fitted(self) -> bool:
        return True

    def provider_info(self) -> ProviderInfo:
        """Return information about the active embedding provider."""
        if self._resolved_provider == "openai":
            available = self._openai_available()
            reason = "" if available else "OPENAI_API_KEY not set"
            return ProviderInfo(
                name="openai",
                model=self._model,
                dimension=self._dimension,
                available=available,
                reason=reason,
            )
        return ProviderInfo(
            name="local",
            model="bag-of-words-subword",
            dimension=self._dimension,
            available=True,
        )
