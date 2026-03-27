"""
ROOT Memory Engine — persistent, evolving, searchable memory.

SQLite + FTS5 for full-text search. Memories strengthen with use,
decay without it, and can be superseded by newer knowledge.
Supports semantic search via optional VectorStore integration.
"""

from __future__ import annotations

import logging
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
        """Check if very similar content already exists (exact prefix match)."""
        import re
        normalized = re.sub(r'\s+', ' ', content.lower().strip())
        if len(normalized) < 20:
            return None
        # Use first 80 chars as exact prefix (not substring) to avoid false matches
        prefix = normalized[:80].replace("'", "''")
        rows = self.conn.execute(
            "SELECT * FROM memories WHERE superseded_by IS NULL AND LOWER(content) LIKE ? LIMIT 1",
            (f"{prefix}%",),
        ).fetchall()
        if rows:
            return self._row_to_entry(rows[0])
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
        """Retrieve a single memory by ID, incrementing access count."""
        row = self.conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        if not row:
            return None
        self.conn.execute(
            "UPDATE memories SET access_count = access_count + 1, last_accessed = ? WHERE id = ?",
            (_now_iso(), memory_id),
        )
        self.conn.commit()
        return self._row_to_entry(row)

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
        """Full-text search across memories with filters."""
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
            vector = self._embedder.embed(content)
            self._vector_store.store(
                id=entry_id,
                text=content,
                vector=vector,
                metadata={"source": "memory_engine"},
            )
            self._embedder.partial_fit(content)
        except Exception as exc:
            logger.warning("Failed to embed memory %s: %s", entry_id, exc)

    def semantic_search(self, query: str, top_k: int = 10) -> list[MemoryEntry]:
        """Search memories using vector similarity.

        Returns memories ranked by cosine similarity to the query embedding.
        Falls back to empty list if vector store is not configured.
        """
        if self._vector_store is None or self._embedder is None:
            logger.debug("Semantic search unavailable: no vector store configured")
            return []

        try:
            query_vector = self._embedder.embed(query)
            results = self._vector_store.search(query_vector, top_k=top_k)
        except Exception as exc:
            logger.error("Semantic search failed: %s", exc)
            return []

        # Fetch full MemoryEntry for each result
        entries: list[MemoryEntry] = []
        for result in results:
            entry = self.recall(result.id)
            if entry is not None:
                entries.append(entry)
        return entries

    def hybrid_search(self, query: str, top_k: int = 10) -> list[MemoryEntry]:
        """Combine FTS5 + vector similarity using Reciprocal Rank Fusion.

        Runs both FTS5 search and vector search, then merges results via RRF
        for higher-quality retrieval. Falls back to FTS5-only if vector store
        is not configured.
        """
        # FTS5 search
        fts_query = MemoryQuery(query=query, limit=top_k * 2)
        fts_entries = self.search(fts_query)
        fts_results = [
            {"id": e.id, "content": e.content, "confidence": e.confidence}
            for e in fts_entries
        ]

        # If no vector store, return FTS-only results
        if self._vector_store is None or self._embedder is None:
            return fts_entries[:top_k]

        try:
            query_vector = self._embedder.embed(query)
            merged = self._vector_store.hybrid_search(
                query_text=query,
                query_vector=query_vector,
                fts_results=fts_results,
                top_k=top_k,
            )
        except Exception as exc:
            logger.error("Hybrid search vector component failed: %s", exc)
            return fts_entries[:top_k]

        # Fetch full MemoryEntry for each merged result
        entries: list[MemoryEntry] = []
        seen: set[str] = set()
        for result in merged:
            if result.id in seen:
                continue
            seen.add(result.id)
            entry = self.recall(result.id)
            if entry is not None:
                entries.append(entry)
        return entries
