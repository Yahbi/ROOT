"""
ROOT Vector Store — SQLite-backed semantic search with TF-IDF embeddings.

Stores embeddings as BLOBs in SQLite, uses numpy for cosine similarity.
Integrates with MemoryEngine via hybrid search (FTS5 + vector with RRF).
"""

from __future__ import annotations

import json
import logging
import math
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from backend.config import DATA_DIR

logger = logging.getLogger(__name__)

VECTOR_DB_PATH = DATA_DIR / "vectors.db"
VOCAB_PATH = DATA_DIR / "vocab.json"
DEFAULT_DIMENSION = 256


# ── Immutable data models ──────────────────────────────────────────


@dataclass(frozen=True)
class VectorRecord:
    """A stored vector with metadata."""

    id: str
    text: str
    vector: np.ndarray
    metadata: dict = field(default_factory=dict)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VectorRecord):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


@dataclass(frozen=True)
class SearchResult:
    """A single search result with score."""

    id: str
    score: float
    metadata: dict = field(default_factory=dict)


# ── Text Embedder (TF-IDF style) ───────────────────────────────────


class TextEmbedder:
    """Builds TF-IDF-style fixed-dimension vectors from text.

    Vocabulary is built from stored texts. Each text is embedded as a
    fixed-dimension vector by hashing tokens into buckets and weighting
    by IDF scores.
    """

    def __init__(self, dimension: int = DEFAULT_DIMENSION) -> None:
        self._dimension = dimension
        self._vocab: dict[str, int] = {}       # token → document frequency
        self._doc_count: int = 0
        self._lock = threading.Lock()

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def is_fitted(self) -> bool:
        return self._doc_count > 0

    # ── tokenization ────────────────────────────────────────────

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Lowercase, strip punctuation, split into tokens."""
        cleaned = re.sub(r"[^a-z0-9\s]", " ", text.lower())
        return [t for t in cleaned.split() if len(t) >= 2]

    # ── vocabulary management ───────────────────────────────────

    def fit(self, texts: list[str]) -> None:
        """Build vocabulary from a corpus of texts."""
        with self._lock:
            vocab: dict[str, int] = {}
            doc_count = 0
            for text in texts:
                tokens = set(self._tokenize(text))
                doc_count += 1
                for token in tokens:
                    vocab[token] = vocab.get(token, 0) + 1
            self._vocab = vocab
            self._doc_count = doc_count
        logger.info(
            "TextEmbedder fitted: %d documents, %d unique tokens",
            self._doc_count,
            len(self._vocab),
        )

    def partial_fit(self, text: str) -> None:
        """Incrementally update vocabulary with a single text."""
        with self._lock:
            tokens = set(self._tokenize(text))
            self._doc_count += 1
            for token in tokens:
                self._vocab[token] = self._vocab.get(token, 0) + 1

    # ── embedding ───────────────────────────────────────────────

    def embed(self, text: str) -> np.ndarray:
        """Produce a fixed-dimension vector for the given text.

        Uses hashing trick to map tokens into buckets, weighted by IDF.
        Returns a unit-normalized vector.
        """
        tokens = self._tokenize(text)
        if not tokens:
            return np.zeros(self._dimension, dtype=np.float32)

        vector = np.zeros(self._dimension, dtype=np.float32)

        # Term frequencies for this document
        tf: dict[str, int] = {}
        for token in tokens:
            tf[token] = tf.get(token, 0) + 1

        max_tf = max(tf.values()) if tf else 1

        for token, count in tf.items():
            # Augmented TF to prevent bias toward long documents
            term_freq = 0.5 + 0.5 * (count / max_tf)

            # IDF: log(N / df), with smoothing
            df = self._vocab.get(token, 0)
            if self._doc_count > 0 and df > 0:
                idf = math.log((1 + self._doc_count) / (1 + df)) + 1.0
            else:
                idf = 1.0

            # Hash token into a bucket
            bucket = hash(token) % self._dimension
            vector[bucket] += term_freq * idf

        # L2 normalize
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector

    # ── persistence ─────────────────────────────────────────────

    def save_vocab(self, path: Optional[Path] = None) -> None:
        """Save vocabulary to JSON file."""
        save_path = path or VOCAB_PATH
        save_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "dimension": self._dimension,
            "doc_count": self._doc_count,
            "vocab": self._vocab,
        }
        save_path.write_text(json.dumps(data), encoding="utf-8")
        logger.info("Vocabulary saved to %s (%d tokens)", save_path, len(self._vocab))

    def load_vocab(self, path: Optional[Path] = None) -> bool:
        """Load vocabulary from JSON file. Returns True if successful."""
        load_path = path or VOCAB_PATH
        if not load_path.exists():
            logger.warning("Vocabulary file not found: %s", load_path)
            return False
        try:
            data = json.loads(load_path.read_text(encoding="utf-8"))
            with self._lock:
                self._dimension = data["dimension"]
                self._doc_count = data["doc_count"]
                self._vocab = data["vocab"]
            logger.info(
                "Vocabulary loaded: %d documents, %d tokens",
                self._doc_count,
                len(self._vocab),
            )
            return True
        except (json.JSONDecodeError, KeyError) as exc:
            logger.error("Failed to load vocabulary: %s", exc)
            return False


# ── Vector Store ────────────────────────────────────────────────────


class VectorStore:
    """SQLite-backed vector store with cosine similarity search.

    Embeddings are stored as BLOBs (numpy array serialization).
    Thread-safe via a reentrant lock on all DB operations.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = str(db_path or VECTOR_DB_PATH)
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.Lock()
        self._dimension: int = DEFAULT_DIMENSION

    # ── lifecycle ───────────────────────────────────────────────

    def start(self) -> None:
        """Open database and create tables."""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()
        logger.info("VectorStore started: %s", self._db_path)

    def stop(self) -> None:
        """Close database connection."""
        with self._lock:
            if self._conn:
                self._conn.close()
                self._conn = None
        logger.info("VectorStore stopped")

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("VectorStore not started")
        return self._conn

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS vectors (
                id TEXT PRIMARY KEY,
                text TEXT NOT NULL,
                vector BLOB NOT NULL,
                metadata TEXT DEFAULT '{}',
                dimension INTEGER NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE INDEX IF NOT EXISTS idx_vectors_created
                ON vectors(created_at);
        """)

    # ── write ───────────────────────────────────────────────────

    def store(
        self,
        id: str,
        text: str,
        vector: np.ndarray,
        metadata: Optional[dict] = None,
    ) -> None:
        """Store an embedding. Overwrites if id already exists."""
        meta_json = json.dumps(metadata or {})
        blob = vector.astype(np.float32).tobytes()
        dimension = len(vector)

        with self._lock:
            self.conn.execute(
                """INSERT OR REPLACE INTO vectors (id, text, vector, metadata, dimension)
                   VALUES (?, ?, ?, ?, ?)""",
                (id, text, blob, meta_json, dimension),
            )
            self.conn.commit()

    def delete(self, id: str) -> bool:
        """Delete a vector by id. Returns True if a row was deleted."""
        with self._lock:
            cursor = self.conn.execute("DELETE FROM vectors WHERE id = ?", (id,))
            self.conn.commit()
            return cursor.rowcount > 0

    # ── read ────────────────────────────────────────────────────

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 10,
        threshold: float = 0.3,
    ) -> list[SearchResult]:
        """Find the top-k most similar vectors by cosine similarity.

        Loads all vectors into memory for brute-force comparison.
        Efficient for up to ~100k entries (typical ROOT memory scale).
        """
        query_vec = query_vector.astype(np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []
        query_vec = query_vec / query_norm

        with self._lock:
            rows = self.conn.execute(
                "SELECT id, vector, metadata, dimension FROM vectors"
            ).fetchall()

        if not rows:
            return []

        results: list[SearchResult] = []
        for row in rows:
            dim = row["dimension"]
            stored_vec = np.frombuffer(row["vector"], dtype=np.float32, count=dim)
            stored_norm = np.linalg.norm(stored_vec)
            if stored_norm == 0:
                continue

            similarity = float(np.dot(query_vec, stored_vec / stored_norm))
            if similarity >= threshold:
                try:
                    meta = json.loads(row["metadata"])
                except json.JSONDecodeError:
                    meta = {}
                results.append(SearchResult(
                    id=row["id"],
                    score=round(similarity, 4),
                    metadata=meta,
                ))

        # Sort by score descending, take top_k
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def hybrid_search(
        self,
        query_text: str,
        query_vector: np.ndarray,
        fts_results: list[dict],
        top_k: int = 10,
        vector_weight: float = 0.5,
        fts_weight: float = 0.5,
    ) -> list[SearchResult]:
        """Combine FTS5 results with vector similarity using Reciprocal Rank Fusion.

        Args:
            query_text: The raw query string (for logging/debugging).
            query_vector: Embedding of the query.
            fts_results: List of dicts with at least {"id": str, ...} from FTS5.
            top_k: Number of results to return.
            vector_weight: Weight for vector similarity scores in RRF.
            fts_weight: Weight for FTS rank scores in RRF.

        Returns:
            Merged results sorted by RRF score.
        """
        k = 60  # RRF constant (standard value)

        # Get vector search results (use a lower threshold for fusion)
        vector_results = self.search(query_vector, top_k=top_k * 2, threshold=0.1)

        # Build RRF scores
        rrf_scores: dict[str, float] = {}
        metadata_map: dict[str, dict] = {}

        # FTS5 rank contribution
        for rank, fts_item in enumerate(fts_results):
            item_id = fts_item.get("id", "")
            if not item_id:
                continue
            rrf_scores[item_id] = rrf_scores.get(item_id, 0.0) + (
                fts_weight / (k + rank + 1)
            )
            metadata_map[item_id] = {
                key: val for key, val in fts_item.items() if key != "id"
            }

        # Vector rank contribution
        for rank, vr in enumerate(vector_results):
            rrf_scores[vr.id] = rrf_scores.get(vr.id, 0.0) + (
                vector_weight / (k + rank + 1)
            )
            if vr.id not in metadata_map:
                metadata_map[vr.id] = vr.metadata

        # Sort by combined RRF score
        sorted_ids = sorted(rrf_scores, key=lambda x: rrf_scores[x], reverse=True)
        results = [
            SearchResult(
                id=item_id,
                score=round(rrf_scores[item_id], 6),
                metadata=metadata_map.get(item_id, {}),
            )
            for item_id in sorted_ids[:top_k]
        ]

        logger.debug(
            "Hybrid search for '%s': %d FTS + %d vector → %d merged",
            query_text[:50],
            len(fts_results),
            len(vector_results),
            len(results),
        )
        return results

    # ── utilities ───────────────────────────────────────────────

    def count(self) -> int:
        """Return the number of stored vectors."""
        with self._lock:
            row = self.conn.execute("SELECT COUNT(*) as c FROM vectors").fetchone()
            return row["c"] if row else 0

    def stats(self) -> dict:
        """Return store statistics."""
        with self._lock:
            row = self.conn.execute(
                "SELECT COUNT(*) as c, AVG(dimension) as avg_dim FROM vectors"
            ).fetchone()
        return {
            "total_vectors": row["c"] if row else 0,
            "avg_dimension": round(row["avg_dim"] or 0, 1),
            "db_path": self._db_path,
        }
