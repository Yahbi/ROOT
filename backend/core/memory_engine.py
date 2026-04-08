"""
ROOT Memory Engine — persistent, evolving, searchable memory.

SQLite + FTS5 for full-text search. Memories strengthen with use,
decay without it, and can be superseded by newer knowledge.
Supports semantic search via optional VectorStore integration.

Extended features:
- Memory clustering by tag similarity
- Importance scoring (access frequency × recency × confidence)
- Bulk insert / bulk confidence update
- Export / import JSON backups
- Near-duplicate deduplication (Jaccard on tokens)
- Rich statistics (by type, avg confidence, growth rate)
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from backend.config import MEMORY_DB_PATH, MEMORY_MAX_ENTRIES
from backend.models.memory import MemoryEntry, MemoryQuery, MemoryType

if TYPE_CHECKING:
    from backend.core.vector_store import TextEmbedder, VectorStore

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryEngine:
    """Persistent memory store with full-text search and confidence decay."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = str(db_path or MEMORY_DB_PATH)
        self._conn: Optional[sqlite3.Connection] = None
        self._vector_store: Optional[VectorStore] = None
        self._embedder: Optional[TextEmbedder] = None

    # ── lifecycle ──────────────────────────────────────────────

    def start(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._create_tables()

    def stop(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            raise RuntimeError("MemoryEngine not started")
        return self._conn

    # ── schema ─────────────────────────────────────────────────

    def _create_tables(self) -> None:
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                tags TEXT DEFAULT '',
                source TEXT DEFAULT 'root',
                confidence REAL DEFAULT 1.0,
                access_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                last_accessed TEXT,
                superseded_by TEXT
            );

            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content, tags, source,
                content='memories',
                content_rowid='rowid'
            );

            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content, tags, source)
                VALUES (new.rowid, new.content, new.tags, new.source);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, tags, source)
                VALUES ('delete', old.rowid, old.content, old.tags, old.source);
            END;

            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, tags, source)
                VALUES ('delete', old.rowid, old.content, old.tags, old.source);
                INSERT INTO memories_fts(rowid, content, tags, source)
                VALUES (new.rowid, new.content, new.tags, new.source);
            END;

            CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type);
            CREATE INDEX IF NOT EXISTS idx_memories_confidence ON memories(confidence);
            CREATE INDEX IF NOT EXISTS idx_memories_created ON memories(created_at);
        """)

    # ── write ──────────────────────────────────────────────────

    def store(self, entry: MemoryEntry) -> MemoryEntry:
        """Store a new memory with deduplication. Returns the entry with assigned ID."""
        # Deduplication: check for very similar existing content
        existing = self._find_duplicate(entry.content)
        if existing:
            self.strengthen(existing.id, boost=0.05)
            return existing

        new_id = entry.id or f"mem_{uuid.uuid4().hex[:12]}"
        tags_str = ",".join(entry.tags)
        self.conn.execute(
            """INSERT INTO memories (id, content, memory_type, tags, source,
               confidence, access_count, created_at, last_accessed, superseded_by)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_id, entry.content, entry.memory_type.value, tags_str,
                entry.source, entry.confidence, entry.access_count,
                entry.created_at, entry.last_accessed, entry.superseded_by,
            ),
        )
        self.conn.commit()
        self._enforce_limit()

        stored_entry = entry.model_copy(update={"id": new_id})

        # Generate and store embedding if vector store is available
        self._embed_and_store(new_id, entry.content)

        return stored_entry

    def _find_duplicate(self, content: str) -> Optional[MemoryEntry]:
        """Check if very similar content already exists using bidirectional prefix match.

        Detects two forms of near-duplication:
        1. The new content starts with an existing memory's prefix (new is longer).
        2. An existing memory starts with the new content's prefix (new is shorter).

        The first 80 characters of whichever string is shorter are used as the
        anchor so we avoid false positives while still catching the common case
        of appending a few extra words to a known memory.
        """
        normalized = re.sub(r'\s+', ' ', content.lower().strip())
        if len(normalized) < 20:
            return None

        # Strategy 1: existing entries whose content starts with new content's prefix
        prefix_new = normalized[:80].replace("'", "''")
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE superseded_by IS NULL AND LOWER(content) LIKE ? LIMIT 1",
            (f"{prefix_new}%",),
        ).fetchall()
        if rows:
            return self._row_to_entry(rows[0])

        # Strategy 2: new content starts with an existing entry's prefix
        # (handles the case where the new content is an extension of an older one)
        if len(normalized) > 80:
            # Fetch candidate rows whose normalised content could be a prefix of ours
            # We use the first 20 chars as a coarse pre-filter, then check in Python
            coarse = normalized[:20].replace("'", "''")
            candidates = self.conn.execute(
                "SELECT * FROM memories WHERE superseded_by IS NULL AND LOWER(content) LIKE ? LIMIT 50",
                (f"{coarse}%",),
            ).fetchall()
            for row in candidates:
                existing_norm = re.sub(r'\s+', ' ', row["content"].lower().strip())
                anchor = existing_norm[:80]
                if normalized.startswith(anchor):
                    return self._row_to_entry(row)

        return None

    def supersede(self, old_id: str, new_entry: MemoryEntry) -> MemoryEntry:
        """Replace an old memory with a new one, linking them."""
        stored = self.store(new_entry)
        self.conn.execute(
            "UPDATE memories SET superseded_by = ? WHERE id = ?",
            (stored.id, old_id),
        )
        self.conn.commit()
        return stored

    # ── read ───────────────────────────────────────────────────

    def recall(self, memory_id: str) -> Optional[MemoryEntry]:
        """Retrieve a single memory by ID, incrementing access count.

        Returns the entry with the *updated* access_count and last_accessed
        values so callers always see the current state.
        """
        row = self.conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if not row:
            return None
        now = _now_iso()
        self.conn.execute(
            "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
            (now, memory_id),
        )
        self.conn.commit()
        # Re-fetch so the returned entry reflects the updated access_count
        updated_row = self.conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        return self._row_to_entry(updated_row)

    @staticmethod
    def _sanitize_fts_query(raw: str) -> str:
        """Sanitize a raw string for safe FTS5 MATCH usage.

        Escapes special FTS5 operators so queries like
        'C++', 'python-async', and 'What do you know?' work safely.
        """
        import re
        # Remove FTS5 special chars but keep hyphens inside words
        cleaned = re.sub(r'[*?:()\"^{}\+~/]', ' ', raw)
        # Extract words (allow alphanumeric, hyphens, single chars)
        words = [w.strip("-") for w in cleaned.split() if w.strip("-")]
        # Filter to valid FTS tokens
        words = [w for w in words if any(c.isalnum() for c in w)]
        if not words:
            return ""
        # Quote each word to escape any remaining special chars
        return " ".join(f'"{w}"' if not w.isalnum() else w for w in words)

    def search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """Search memories using FTS5, optionally enhanced with vector similarity.

        When ``query.hybrid`` is True and a vector store is available, runs
        hybrid search (FTS5 + vector with Reciprocal Rank Fusion).  Otherwise
        falls back to FTS5-only keyword search.
        """
        use_hybrid = (
            query.hybrid
            and self._vector_store is not None
            and self._embedder is not None
        )
        if use_hybrid:
            return self.hybrid_search(query)

        return self._fts_search(query)

    def _fts_search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """Pure FTS5 keyword search (original search implementation)."""
        safe_query = self._sanitize_fts_query(query.query)
        if safe_query:
            sql = """
                SELECT m.* FROM memories m
                JOIN memories_fts f ON m.rowid = f.rowid
                WHERE memories_fts MATCH ?
                  AND m.confidence >= ?
                  AND m.superseded_by IS NULL
            """
            params: list = [safe_query, query.min_confidence]
        else:
            sql = """
                SELECT * FROM memories
                WHERE confidence >= ?
                  AND superseded_by IS NULL
            """
            params = [query.min_confidence]

        if query.memory_type:
            sql += " AND memory_type = ?"
            params.append(query.memory_type.value)

        sql += " ORDER BY confidence DESC, access_count DESC LIMIT ?"
        params.append(query.limit)

        rows = self.conn.execute(sql, params).fetchall()
        # Bump access counts
        ids = [r["id"] for r in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            self.conn.execute(
                f"UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id IN ({placeholders})",
                [_now_iso(), *ids],
            )
            self.conn.commit()
        return [self._row_to_entry(r) for r in rows]

    def get_recent(self, limit: int = 20) -> list[MemoryEntry]:
        """Get most recent active memories."""
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE superseded_by IS NULL ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_strongest(self, limit: int = 20) -> list[MemoryEntry]:
        """Get highest-confidence, most-accessed memories."""
        rows = self.conn.execute(
            """SELECT * FROM memories WHERE superseded_by IS NULL
               ORDER BY (confidence * 0.6 + min(access_count, 100) / 100.0 * 0.4) DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) as c FROM memories WHERE superseded_by IS NULL").fetchone()
        return row["c"] if row else 0

    def stats(self) -> dict:
        """Memory statistics."""
        rows = self.conn.execute(
            """SELECT memory_type, COUNT(*) as cnt, AVG(confidence) as avg_conf
               FROM memories WHERE superseded_by IS NULL GROUP BY memory_type"""
        ).fetchall()
        agg = self.conn.execute(
            "SELECT SUM(access_count) as total_accesses, AVG(confidence) as avg_conf FROM memories WHERE superseded_by IS NULL"
        ).fetchone()
        return {
            "total": self.count(),
            "total_accesses": agg["total_accesses"] or 0,
            "avg_confidence": round(agg["avg_conf"] or 0, 3),
            "by_type": {r["memory_type"]: {"count": r["cnt"], "avg_confidence": round(r["avg_conf"], 3)} for r in rows},
        }

    def get_by_tag(self, tag: str, limit: int = 20) -> list[MemoryEntry]:
        """Get memories matching a specific tag."""
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE superseded_by IS NULL AND tags LIKE ? ORDER BY confidence DESC LIMIT ?",
            (f"%{tag}%", limit),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def get_by_source(self, source: str, limit: int = 20) -> list[MemoryEntry]:
        """Get memories from a specific source."""
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE superseded_by IS NULL AND source = ? ORDER BY created_at DESC LIMIT ?",
            (source, limit),
        ).fetchall()
        return [self._row_to_entry(r) for r in rows]

    def rebuild_fts(self) -> int:
        """Rebuild the FTS5 index from scratch. Fixes stale/missing FTS entries."""
        self.conn.execute("INSERT INTO memories_fts(memories_fts) VALUES('rebuild')")
        self.conn.commit()
        return self.count()

    # ── maintenance ────────────────────────────────────────────

    def decay(self, factor: float = 0.995) -> int:
        """Decay confidence of memories not accessed recently. Returns count affected."""
        cutoff = 0.05  # Remove memories below this threshold
        cursor = self.conn.execute(
            "UPDATE memories SET confidence = confidence * ? WHERE superseded_by IS NULL AND confidence > ?",
            (factor, cutoff),
        )
        self.conn.execute("DELETE FROM memories WHERE confidence <= ? AND superseded_by IS NULL", (cutoff,))
        self.conn.commit()
        return cursor.rowcount

    def strengthen(self, memory_id: str, boost: float = 0.05) -> None:
        """Strengthen a memory's confidence (capped at 1.0)."""
        self.conn.execute(
            "UPDATE memories SET confidence = MIN(1.0, confidence + ?) WHERE id = ?",
            (boost, memory_id),
        )
        self.conn.commit()

    def _enforce_limit(self) -> None:
        """Remove lowest-confidence memories if over limit."""
        count = self.count()
        if count <= MEMORY_MAX_ENTRIES:
            return
        excess = count - MEMORY_MAX_ENTRIES
        self.conn.execute(
            """DELETE FROM memories WHERE id IN (
                SELECT id FROM memories WHERE superseded_by IS NULL
                ORDER BY confidence ASC, access_count ASC LIMIT ?
            )""",
            (excess,),
        )
        self.conn.commit()

    # ── helpers ─────────────────────────────────────────────────

    @staticmethod
    def _row_to_entry(row: sqlite3.Row) -> MemoryEntry:
        tags = [t.strip() for t in row["tags"].split(",") if t.strip()]
        return MemoryEntry(
            id=row["id"],
            content=row["content"],
            memory_type=MemoryType(row["memory_type"]),
            tags=tags,
            source=row["source"],
            confidence=row["confidence"],
            access_count=row["access_count"],
            created_at=row["created_at"],
            last_accessed=row["last_accessed"],
            superseded_by=row["superseded_by"],
        )

    # ── vector store integration ────────────────────────────────

    def set_vector_store(
        self,
        vs: VectorStore,
        embedder: Optional[TextEmbedder] = None,
    ) -> None:
        """Attach a VectorStore (and optional embedder) for semantic search.

        Late binding allows MemoryEngine to work without vector support
        until explicitly configured.
        """
        self._vector_store = vs
        if embedder is not None:
            self._embedder = embedder
        logger.info("VectorStore attached to MemoryEngine")

    def _embed_and_store(self, entry_id: str, content: str) -> None:
        """Generate an embedding for content and store it in the vector store."""
        if self._vector_store is None or self._embedder is None:
            return
        try:
            # Support both old TextEmbedder.embed() and new EmbeddingService.embed_sync()
            if hasattr(self._embedder, "embed_sync"):
                vector = self._embedder.embed_sync(content)
            else:
                vector = self._embedder.embed(content)
            self._vector_store.store(
                id=entry_id,
                text=content,
                vector=vector,
                metadata={"source": "memory_engine"},
            )
            if hasattr(self._embedder, "partial_fit"):
                self._embedder.partial_fit(content)
        except Exception as exc:
            logger.warning("Failed to embed memory %s: %s", entry_id, exc)

    def semantic_search(self, query: str, top_k: int = 10) -> list[MemoryEntry]:
        """Search memories using vector similarity.

        Returns memories ranked by cosine similarity to the query embedding.
        Falls back to empty list if vector store is not configured.
        """
        results = self._vector_search(query, top_k=top_k)
        # Fetch full MemoryEntry for each result
        entries: list[MemoryEntry] = []
        for result_id, _score in results:
            entry = self.recall(result_id)
            if entry is not None:
                entries.append(entry)
        return entries

    def _vector_search(
        self, query: str, top_k: int = 10
    ) -> list[tuple[str, float]]:
        """Embed the query and search the vector store for similar entries.

        Returns a list of (memory_id, similarity_score) tuples sorted by
        descending similarity.  Returns an empty list if the vector store
        or embedder is not available.
        """
        if self._vector_store is None or self._embedder is None:
            logger.debug("Vector search unavailable: no vector store configured")
            return []

        try:
            # Support both sync (TextEmbedder) and async (EmbeddingService)
            if hasattr(self._embedder, "embed_sync"):
                query_vector = self._embedder.embed_sync(query)
            else:
                query_vector = self._embedder.embed(query)

            results = self._vector_store.search(
                query_vector, top_k=top_k, threshold=0.1
            )
        except Exception as exc:
            logger.error("Vector search failed: %s", exc)
            return []

        return [(r.id, r.score) for r in results]

    def hybrid_search(self, query: MemoryQuery) -> list[MemoryEntry]:
        """Combine FTS5 keyword search + vector similarity via Reciprocal Rank Fusion.

        Runs both retrieval paths independently, then merges results using
        RRF: ``score(d) = sum(1 / (k + rank_i))`` where *k* = 60 (the
        standard RRF constant) and *rank_i* is the 1-based rank of document
        *d* in retrieval list *i*.

        Falls back to FTS5-only if the vector store is not available.
        """
        # ── 1. FTS5 keyword search ─────────────────────────────────
        fts_only_query = query.model_copy(update={"hybrid": False})
        fts_entries = self._fts_search(fts_only_query)

        # ── 2. Vector similarity search ────────────────────────────
        vector_results = self._vector_search(
            query.query, top_k=query.limit * 2
        )

        # If vector search returned nothing, just return FTS results
        if not vector_results:
            return fts_entries[: query.limit]

        # ── 3. Reciprocal Rank Fusion (RRF) ────────────────────────
        k = 60  # Standard RRF constant

        rrf_scores: dict[str, float] = {}

        # FTS5 rank contribution (1-based ranks)
        for rank, entry in enumerate(fts_entries, start=1):
            rrf_scores[entry.id] = rrf_scores.get(entry.id, 0.0) + 1.0 / (
                k + rank
            )

        # Vector rank contribution (1-based ranks)
        for rank, (mem_id, _sim) in enumerate(vector_results, start=1):
            rrf_scores[mem_id] = rrf_scores.get(mem_id, 0.0) + 1.0 / (
                k + rank
            )

        # ── 4. Build deduplicated entry map ────────────────────────
        entry_map: dict[str, MemoryEntry] = {e.id: e for e in fts_entries}

        # For IDs found only in vector results, fetch the full entry
        for mem_id, _sim in vector_results:
            if mem_id not in entry_map:
                entry = self.recall(mem_id)
                if entry is not None:
                    # Apply same filters the FTS path would apply
                    if entry.confidence < query.min_confidence:
                        rrf_scores.pop(mem_id, None)
                        continue
                    if entry.superseded_by is not None:
                        rrf_scores.pop(mem_id, None)
                        continue
                    if (
                        query.memory_type
                        and entry.memory_type != query.memory_type
                    ):
                        rrf_scores.pop(mem_id, None)
                        continue
                    entry_map[mem_id] = entry
                else:
                    # Entry no longer exists in the DB — skip
                    rrf_scores.pop(mem_id, None)

        # ── 5. Sort by RRF score and return top-k ──────────────────
        sorted_ids = sorted(
            rrf_scores, key=lambda mid: rrf_scores[mid], reverse=True
        )

        results: list[MemoryEntry] = []
        for mem_id in sorted_ids:
            if mem_id in entry_map:
                results.append(entry_map[mem_id])
            if len(results) >= query.limit:
                break

        logger.debug(
            "Hybrid search '%s': %d FTS + %d vector → %d merged (RRF k=%d)",
            query.query[:50],
            len(fts_entries),
            len(vector_results),
            len(results),
            k,
        )
        return results

    # ── clustering ─────────────────────────────────────────────

    def cluster_by_tags(self, min_shared: int = 1) -> dict[str, list[MemoryEntry]]:
        """Group active memories into clusters by shared tags.

        Two memories belong to the same cluster when they share at least
        *min_shared* tags.  Returns a dict mapping a representative tag
        (the most common shared tag in the cluster) to the list of
        MemoryEntry objects in that cluster.  Memories with no tags are
        grouped under the special key ``"__untagged__"``.

        Uses a simple union-find (disjoint-set) to merge overlapping groups
        so transitive tag relationships are respected.
        """
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE superseded_by IS NULL"
        ).fetchall()
        entries = [self._row_to_entry(r) for r in rows]

        # Map from index → representative index (union-find parent)
        parent = list(range(len(entries)))

        def _find(i: int) -> int:
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i

        def _union(a: int, b: int) -> None:
            ra, rb = _find(a), _find(b)
            if ra != rb:
                parent[rb] = ra

        # Build tag → entry indices map
        tag_to_indices: dict[str, list[int]] = {}
        for idx, entry in enumerate(entries):
            for tag in entry.tags:
                tag_to_indices.setdefault(tag, []).append(idx)

        # Union entries that share enough tags
        shared_counts: dict[tuple[int, int], int] = {}
        for indices in tag_to_indices.values():
            for i in range(len(indices)):
                for j in range(i + 1, len(indices)):
                    a, b = min(indices[i], indices[j]), max(indices[i], indices[j])
                    shared_counts[(a, b)] = shared_counts.get((a, b), 0) + 1

        for (a, b), count in shared_counts.items():
            if count >= min_shared:
                _union(a, b)

        # Collect groups
        from collections import defaultdict
        group_map: dict[int, list[int]] = defaultdict(list)
        for idx in range(len(entries)):
            group_map[_find(idx)].append(idx)

        # Build output: representative label = most frequent tag in the group
        clusters: dict[str, list[MemoryEntry]] = {}
        for root_idx, member_indices in group_map.items():
            members = [entries[i] for i in member_indices]
            all_tags: list[str] = []
            for m in members:
                all_tags.extend(m.tags)
            if all_tags:
                from collections import Counter
                label = Counter(all_tags).most_common(1)[0][0]
            else:
                label = "__untagged__"
            # Ensure unique cluster keys
            base_label = label
            suffix = 1
            while label in clusters and clusters[label][0].id not in {m.id for m in members}:
                label = f"{base_label}_{suffix}"
                suffix += 1
            clusters[label] = members

        return clusters

    # ── importance scoring ─────────────────────────────────────

    def importance_score(self, entry: MemoryEntry) -> float:
        """Compute an importance score for a memory entry.

        Score = confidence × frequency_factor × recency_factor

        - ``confidence``: the stored confidence value (0–1).
        - ``frequency_factor``: log-normalised access count so high-access
          memories score higher but with diminishing returns.
        - ``recency_factor``: exponential decay based on days since last
          access (or creation if never accessed).  Half-life ≈ 30 days.
        """
        import math

        # Frequency: log(1 + access_count) / log(1 + 100) normalised to ~0–1
        freq = math.log1p(entry.access_count) / math.log1p(100)

        # Recency: half-life of 30 days
        ref_time_str = entry.last_accessed or entry.created_at
        try:
            ref_time = datetime.fromisoformat(ref_time_str)
        except (ValueError, TypeError):
            ref_time = datetime.now(timezone.utc)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=timezone.utc)
        age_days = (datetime.now(timezone.utc) - ref_time).total_seconds() / 86400.0
        recency = math.exp(-age_days / 30.0)

        return round(entry.confidence * freq * recency, 6)

    def get_by_importance(self, limit: int = 20) -> list[tuple[MemoryEntry, float]]:
        """Return (entry, importance_score) pairs sorted by descending importance."""
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE superseded_by IS NULL"
        ).fetchall()
        scored = [
            (self._row_to_entry(r), 0.0) for r in rows
        ]
        scored = [(e, self.importance_score(e)) for e, _ in scored]
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:limit]

    # ── bulk operations ────────────────────────────────────────

    def bulk_store(self, entries: list[MemoryEntry]) -> list[MemoryEntry]:
        """Insert multiple memory entries in a single transaction.

        Applies the same deduplication logic as :meth:`store` for each
        entry and skips exact duplicates.  Returns the list of stored (or
        pre-existing) entries in the same order as the input.
        """
        stored: list[MemoryEntry] = []
        for entry in entries:
            existing = self._find_duplicate(entry.content)
            if existing:
                self.strengthen(existing.id, boost=0.05)
                stored.append(existing)
                continue

            new_id = entry.id or f"mem_{uuid.uuid4().hex[:12]}"
            tags_str = ",".join(entry.tags)
            self.conn.execute(
                """INSERT INTO memories
                   (id, content, memory_type, tags, source,
                    confidence, access_count, created_at, last_accessed, superseded_by)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    new_id, entry.content, entry.memory_type.value, tags_str,
                    entry.source, entry.confidence, entry.access_count,
                    entry.created_at, entry.last_accessed, entry.superseded_by,
                ),
            )
            stored.append(entry.model_copy(update={"id": new_id}))

        self.conn.commit()
        self._enforce_limit()

        # Embed new entries
        for s_entry in stored:
            if s_entry.id:
                self._embed_and_store(s_entry.id, s_entry.content)

        return stored

    def bulk_update_confidence(self, updates: dict[str, float]) -> int:
        """Update confidence scores for multiple memories in one transaction.

        ``updates`` maps memory ID → new confidence value (clamped to 0–1).
        Returns the number of rows actually updated.
        """
        if not updates:
            return 0
        count = 0
        for memory_id, new_conf in updates.items():
            clamped = max(0.0, min(1.0, new_conf))
            cur = self.conn.execute(
                "UPDATE memories SET confidence = ? WHERE id = ?",
                (clamped, memory_id),
            )
            count += cur.rowcount
        self.conn.commit()
        return count

    # ── export / import ────────────────────────────────────────

    def export_json(self, include_superseded: bool = False) -> str:
        """Export all (or only active) memories as a JSON string.

        The JSON schema is::

            {
              "exported_at": "<ISO timestamp>",
              "version": 1,
              "memories": [ <MemoryEntry dict>, ... ]
            }

        Set *include_superseded* to ``True`` to include memories that have
        been replaced by newer ones (useful for full backups).
        """
        if include_superseded:
            rows = self.conn.execute("SELECT * FROM memories").fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM memories WHERE superseded_by IS NULL"
            ).fetchall()

        entries = [self._row_to_entry(r).model_dump() for r in rows]
        payload = {
            "exported_at": _now_iso(),
            "version": 1,
            "memories": entries,
        }
        return json.dumps(payload, default=str, indent=2)

    def import_json(self, data: str, overwrite: bool = False) -> dict:
        """Import memories from a JSON string produced by :meth:`export_json`.

        When *overwrite* is ``False`` (default) existing entries (by ID) are
        skipped.  When *overwrite* is ``True`` they are replaced.

        Returns a summary dict with ``imported``, ``skipped``, and
        ``errors`` counts.
        """
        try:
            payload = json.loads(data)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON: {exc}") from exc

        if not isinstance(payload, dict) or "memories" not in payload:
            raise ValueError("JSON must contain a 'memories' key")

        imported = skipped = errors = 0

        for raw in payload["memories"]:
            try:
                mt_str = raw.get("memory_type", "fact")
                try:
                    mt = MemoryType(mt_str)
                except ValueError:
                    mt = MemoryType.FACT

                entry = MemoryEntry(
                    id=raw.get("id"),
                    content=raw["content"],
                    memory_type=mt,
                    tags=raw.get("tags", []),
                    source=raw.get("source", "import"),
                    confidence=raw.get("confidence", 1.0),
                    access_count=raw.get("access_count", 0),
                    created_at=raw.get("created_at", _now_iso()),
                    last_accessed=raw.get("last_accessed"),
                    superseded_by=raw.get("superseded_by"),
                )

                # Check if ID already exists
                if entry.id:
                    existing_row = self.conn.execute(
                        "SELECT id FROM memories WHERE id = ?", (entry.id,)
                    ).fetchone()
                    if existing_row:
                        if not overwrite:
                            skipped += 1
                            continue
                        # Overwrite: delete old row first
                        self.conn.execute(
                            "DELETE FROM memories WHERE id = ?", (entry.id,)
                        )

                tags_str = ",".join(entry.tags)
                mem_id = entry.id or f"mem_{uuid.uuid4().hex[:12]}"
                self.conn.execute(
                    """INSERT INTO memories
                       (id, content, memory_type, tags, source, confidence,
                        access_count, created_at, last_accessed, superseded_by)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        mem_id, entry.content, entry.memory_type.value, tags_str,
                        entry.source, entry.confidence, entry.access_count,
                        entry.created_at, entry.last_accessed, entry.superseded_by,
                    ),
                )
                imported += 1
            except Exception as exc:
                logger.warning("import_json: skipping entry due to error: %s", exc)
                errors += 1

        self.conn.commit()
        return {"imported": imported, "skipped": skipped, "errors": errors}

    # ── near-duplicate deduplication ───────────────────────────

    @staticmethod
    def _token_set(text: str) -> set[str]:
        """Tokenise text into a set of lowercase alphanum words."""
        return set(re.findall(r"[a-z0-9]+", text.lower()))

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        if not a and not b:
            return 1.0
        inter = len(a & b)
        union = len(a | b)
        return inter / union if union else 0.0

    def find_near_duplicates(
        self, threshold: float = 0.85
    ) -> list[tuple[MemoryEntry, MemoryEntry, float]]:
        """Detect near-duplicate memory pairs using Jaccard token similarity.

        Returns a list of ``(entry_a, entry_b, similarity)`` triples where
        *similarity* >= *threshold*.  Only active (non-superseded) memories
        are considered.  Pairs are de-duplicated so (a, b) and (b, a) do not
        both appear.
        """
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE superseded_by IS NULL"
        ).fetchall()
        entries = [self._row_to_entry(r) for r in rows]
        token_sets = [self._token_set(e.content) for e in entries]

        duplicates: list[tuple[MemoryEntry, MemoryEntry, float]] = []
        for i in range(len(entries)):
            for j in range(i + 1, len(entries)):
                sim = self._jaccard(token_sets[i], token_sets[j])
                if sim >= threshold:
                    duplicates.append((entries[i], entries[j], round(sim, 4)))

        return duplicates

    def merge_near_duplicates(
        self, threshold: float = 0.85
    ) -> list[tuple[str, str]]:
        """Find near-duplicates and merge each pair by superseding the older one.

        The newer entry (by ``created_at``) survives; the older is marked
        superseded.  Returns a list of ``(superseded_id, survivor_id)`` pairs.
        """
        pairs = self.find_near_duplicates(threshold=threshold)
        merged: list[tuple[str, str]] = []

        for entry_a, entry_b, _sim in pairs:
            # Skip if either entry was already superseded in this run
            check = self.conn.execute(
                "SELECT superseded_by FROM memories WHERE id = ? OR id = ?",
                (entry_a.id, entry_b.id),
            ).fetchall()
            if any(r["superseded_by"] for r in check):
                continue

            # The entry with the earlier created_at is the "older" one
            try:
                ts_a = datetime.fromisoformat(entry_a.created_at)
                ts_b = datetime.fromisoformat(entry_b.created_at)
            except (ValueError, TypeError):
                ts_a = ts_b = datetime.now(timezone.utc)

            older, survivor = (entry_a, entry_b) if ts_a <= ts_b else (entry_b, entry_a)

            # Merge: boost survivor confidence, supersede older
            self.strengthen(survivor.id, boost=0.05)
            self.conn.execute(
                "UPDATE memories SET superseded_by = ? WHERE id = ?",
                (survivor.id, older.id),
            )
            self.conn.commit()
            merged.append((older.id, survivor.id))
            logger.info(
                "Merged near-duplicate %s → %s (similarity %.2f)",
                older.id, survivor.id, _sim,
            )

        return merged

    # ── rich statistics ────────────────────────────────────────

    def stats(self) -> dict:
        """Return comprehensive memory statistics.

        Extends the original stats with:
        - ``by_type``: count + avg_confidence per MemoryType
        - ``growth_rate``: memories created in the last 7 days vs prior 7 days
        - ``top_tags``: the 10 most frequent tags across active memories
        - ``importance_top5``: IDs + scores of the 5 most important memories
        - ``near_duplicate_pairs``: count of near-duplicate pairs (threshold 0.85)
        """
        rows = self.conn.execute(
            """SELECT memory_type, COUNT(*) as cnt, AVG(confidence) as avg_conf
               FROM memories WHERE superseded_by IS NULL GROUP BY memory_type"""
        ).fetchall()
        agg = self.conn.execute(
            """SELECT SUM(access_count) as total_accesses,
                      AVG(confidence) as avg_conf,
                      COUNT(*) as total
               FROM memories WHERE superseded_by IS NULL"""
        ).fetchone()

        # Growth rate: last 7 days vs prior 7 days
        now = datetime.now(timezone.utc)
        cutoff_7 = (now.timestamp() - 7 * 86400)
        cutoff_14 = (now.timestamp() - 14 * 86400)

        def _ts(iso: str) -> float:
            try:
                dt = datetime.fromisoformat(iso)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.timestamp()
            except Exception:
                return 0.0

        all_created = self.conn.execute(
            "SELECT created_at FROM memories WHERE superseded_by IS NULL"
        ).fetchall()
        recent_7 = sum(1 for r in all_created if _ts(r["created_at"]) >= cutoff_7)
        prior_7 = sum(
            1 for r in all_created
            if cutoff_14 <= _ts(r["created_at"]) < cutoff_7
        )
        growth_pct: Optional[float] = None
        if prior_7 > 0:
            growth_pct = round((recent_7 - prior_7) / prior_7 * 100, 1)

        # Top tags
        tag_counts: dict[str, int] = {}
        tag_rows = self.conn.execute(
            "SELECT tags FROM memories WHERE superseded_by IS NULL AND tags != ''"
        ).fetchall()
        for row in tag_rows:
            for tag in [t.strip() for t in row["tags"].split(",") if t.strip()]:
                tag_counts[tag] = tag_counts.get(tag, 0) + 1
        top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        # Importance top-5
        importance_top5 = [
            {"id": e.id, "score": score}
            for e, score in self.get_by_importance(limit=5)
        ]

        return {
            "total": agg["total"] or 0,
            "total_accesses": agg["total_accesses"] or 0,
            "avg_confidence": round(agg["avg_conf"] or 0, 3),
            "by_type": {
                r["memory_type"]: {
                    "count": r["cnt"],
                    "avg_confidence": round(r["avg_conf"], 3),
                }
                for r in rows
            },
            "growth": {
                "last_7_days": recent_7,
                "prior_7_days": prior_7,
                "growth_pct": growth_pct,
            },
            "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
            "importance_top5": importance_top5,
        }
