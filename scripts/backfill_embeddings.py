"""
Backfill embeddings for existing memories.

Reads all memories from memory.db, generates TF-IDF embeddings,
and stores them in the vector store (vectors.db).

Usage:
    cd ~/Desktop/ROOT
    python -m scripts.backfill_embeddings
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT_DIR))

from backend.config import DATA_DIR, MEMORY_DB_PATH  # noqa: E402
from backend.core.vector_store import TextEmbedder, VectorStore  # noqa: E402


def main() -> None:
    memory_db = str(MEMORY_DB_PATH)
    if not Path(memory_db).exists():
        print(f"Memory database not found: {memory_db}")
        sys.exit(1)

    # Load all active memories
    conn = sqlite3.connect(memory_db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, content FROM memories WHERE superseded_by IS NULL"
    ).fetchall()
    conn.close()

    total = len(rows)
    if total == 0:
        print("No memories found to embed.")
        return

    print(f"Found {total} memories to embed.")

    # Build vocabulary from all texts
    texts = [row["content"] for row in rows]
    embedder = TextEmbedder(dimension=256)
    embedder.fit(texts)

    # Start vector store
    vs = VectorStore(db_path=DATA_DIR / "vectors.db")
    vs.start()

    # Embed and store each memory
    stored = 0
    for i, row in enumerate(rows, 1):
        try:
            vector = embedder.embed(row["content"])
            vs.store(
                id=row["id"],
                text=row["content"],
                vector=vector,
                metadata={"source": "backfill"},
            )
            stored += 1
        except Exception as exc:
            print(f"  [WARN] Failed to embed {row['id']}: {exc}")

        if i % 100 == 0 or i == total:
            print(f"  Progress: {i}/{total} ({stored} stored)")

    # Save vocabulary for future use
    embedder.save_vocab()

    vs.stop()
    print(f"Done. {stored}/{total} memories embedded.")
    print(f"  Vector DB: {DATA_DIR / 'vectors.db'}")
    print(f"  Vocabulary: {DATA_DIR / 'vocab.json'}")


if __name__ == "__main__":
    main()
