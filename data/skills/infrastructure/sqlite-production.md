---
name: SQLite in Production
description: WAL mode, busy timeout, connection pooling, VACUUM, backup strategies
version: "1.0.0"
author: ROOT
tags: [infrastructure, sqlite, database, WAL, backup, production]
platforms: [all]
---

# SQLite in Production

Deploy SQLite reliably for production workloads with proper configuration and operational practices.

## WAL Mode Configuration

### Enabling WAL
```sql
PRAGMA journal_mode=WAL;          -- Enables Write-Ahead Logging (persistent)
PRAGMA synchronous=NORMAL;        -- Safe with WAL (FULL is unnecessary overhead)
PRAGMA busy_timeout=5000;         -- Wait 5 seconds on lock instead of failing immediately
PRAGMA cache_size=-64000;         -- 64MB page cache (negative = KB, positive = pages)
PRAGMA foreign_keys=ON;           -- Enforce FK constraints (off by default!)
PRAGMA temp_store=MEMORY;         -- Store temp tables in memory
```

### Why WAL Matters
- Readers never block writers, writers never block readers (concurrent access)
- Without WAL: any write locks the entire database for all readers
- WAL checkpoint happens automatically (or `PRAGMA wal_checkpoint(TRUNCATE)` manually)
- Set `PRAGMA wal_autocheckpoint=1000;` (checkpoint every 1000 pages, default)

## Connection Management

### Python Connection Pool Pattern
```python
import sqlite3
from contextlib import contextmanager
from threading import local

_thread_local = local()

def get_connection(db_path: str) -> sqlite3.Connection:
    """One connection per thread (SQLite connections are not thread-safe)."""
    conn = getattr(_thread_local, 'conn', None)
    if conn is None:
        conn = sqlite3.connect(db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        _thread_local.conn = conn
    return conn
```

### Connection Rules
- One writer at a time (WAL allows concurrent reads but serializes writes)
- Use short write transactions: BEGIN → write → COMMIT quickly
- Never hold a write transaction open during slow operations (network calls, LLM queries)
- For async apps (FastAPI): use `aiosqlite` or run SQLite in a thread pool via `asyncio.to_thread`

## Performance Optimization

### Index Strategy
```sql
-- Check for missing indexes: queries doing full table scans
EXPLAIN QUERY PLAN SELECT * FROM memories WHERE category = 'fact';
-- If output shows "SCAN" instead of "SEARCH", add an index

-- Covering index (query answered entirely from index, no table lookup)
CREATE INDEX idx_memories_cat_conf ON memories(category, confidence DESC);

-- Partial index (only index rows you query)
CREATE INDEX idx_active_tasks ON tasks(priority) WHERE status = 'pending';
```

### Write Performance
- Batch inserts in transactions: 100 individual INSERTs = 100 fsync; 1 transaction with 100 INSERTs = 1 fsync
- Use `INSERT OR REPLACE` or `INSERT ON CONFLICT` for upserts
- For bulk loads: temporarily `PRAGMA synchronous=OFF`, load data, then restore

## VACUUM and Maintenance

### When to VACUUM
- After deleting large amounts of data (reclaims disk space)
- `VACUUM` rebuilds the entire database (requires 2x disk space temporarily)
- `PRAGMA auto_vacuum=INCREMENTAL;` + `PRAGMA incremental_vacuum;` for gradual reclaim
- Schedule VACUUM during maintenance windows (locks database during operation)

### Database Size Monitoring
```sql
-- Check page count and free pages
PRAGMA page_count;        -- Total pages
PRAGMA freelist_count;    -- Unused pages (reclaimable by VACUUM)
-- If freelist_count > 20% of page_count, VACUUM is worthwhile
```

## Backup Strategies

### Online Backup (No Downtime)
```python
import sqlite3

def backup_database(source_path: str, backup_path: str):
    """Hot backup using SQLite's built-in backup API."""
    source = sqlite3.connect(source_path)
    backup = sqlite3.connect(backup_path)
    source.backup(backup)  # Atomic, consistent copy even during writes
    backup.close()
    source.close()
```

### Backup Schedule
| Frequency | Method | Retention |
|-----------|--------|-----------|
| Every 6 hours | SQLite backup API → local copy | 48 hours (8 copies) |
| Daily | Copy to remote storage (S3, rsync) | 30 days |
| Weekly | Full archive with integrity check | 90 days |

### Integrity Verification
```bash
sqlite3 backup.db "PRAGMA integrity_check;"    # Should return "ok"
sqlite3 backup.db "PRAGMA quick_check;"        # Faster, less thorough
```

## Limits and When to Migrate
- Max database size: 281 TB (practical limit is disk speed, not SQLite)
- Concurrent writers: 1 (serialized). If write contention > 100ms regularly, consider PostgreSQL
- No built-in replication. If you need read replicas, use Litestream for streaming replication
- No user-level access control. If multi-tenant isolation is needed, use one DB file per tenant or switch to PostgreSQL
