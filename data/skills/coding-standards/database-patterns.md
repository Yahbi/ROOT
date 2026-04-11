---
name: Database Patterns
description: Repository pattern, unit of work, connection management, migration strategies
version: "1.0.0"
author: ROOT
tags: [coding-standards, database, repository-pattern, unit-of-work, migrations]
platforms: [all]
---

# Database Patterns

Structure database access code for testability, maintainability, and safe schema evolution.

## Repository Pattern

### Interface Definition
```python
from typing import Protocol, TypeVar, Generic
from datetime import datetime

T = TypeVar("T")

class Repository(Protocol[T]):
    """Abstract repository interface — implementations are swappable."""
    async def get(self, id: str) -> T | None: ...
    async def save(self, entity: T) -> T: ...
    async def delete(self, id: str) -> bool: ...
    async def list(self, limit: int = 100, offset: int = 0) -> list[T]: ...
```

### SQLite Implementation
```python
import sqlite3
import json
from dataclasses import asdict

class SQLiteMemoryRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        conn.row_factory = sqlite3.Row
        return conn

    async def get(self, id: str) -> dict | None:
        conn = self._get_conn()
        try:
            row = conn.execute("SELECT * FROM memories WHERE id = ?", (id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    async def save(self, entity: dict) -> dict:
        conn = self._get_conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO memories (id, content, category, confidence) VALUES (?, ?, ?, ?)",
                (entity["id"], entity["content"], entity["category"], entity["confidence"])
            )
            conn.commit()
            return entity
        finally:
            conn.close()
```

### Benefits
- Business logic does not depend on database implementation details
- Swap SQLite for PostgreSQL without changing service code
- Test with in-memory repository (no database needed for unit tests)
- Centralize query logic (no SQL scattered across the codebase)

## Unit of Work

### Coordinating Multiple Repositories
```python
class UnitOfWork:
    """Ensures all repository operations in a transaction succeed or fail together."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: sqlite3.Connection | None = None

    async def __aenter__(self):
        self.conn = sqlite3.connect(self.db_path, timeout=10)
        self.conn.execute("BEGIN")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
        self.conn.close()

# Usage: both operations succeed or both fail
async with UnitOfWork("data/app.db") as uow:
    await uow.memories.save(memory)
    await uow.learning.record_outcome(outcome)
    # If learning.record_outcome fails, memory.save is rolled back
```

### When Unit of Work Matters
- Multiple writes that must be atomic (order + inventory reservation)
- Cross-table consistency requirements
- Not needed for single-table writes (just use a transaction directly)

## Connection Management

### Connection Pool Pattern
```python
from contextlib import asynccontextmanager
import aiosqlite

class DatabasePool:
    def __init__(self, db_path: str, max_connections: int = 10):
        self.db_path = db_path
        self._semaphore = asyncio.Semaphore(max_connections)

    @asynccontextmanager
    async def acquire(self):
        async with self._semaphore:
            db = await aiosqlite.connect(self.db_path)
            await db.execute("PRAGMA journal_mode=WAL")
            await db.execute("PRAGMA busy_timeout=5000")
            db.row_factory = aiosqlite.Row
            try:
                yield db
            finally:
                await db.close()

# Usage
pool = DatabasePool("data/memory.db", max_connections=5)
async with pool.acquire() as db:
    cursor = await db.execute("SELECT * FROM memories WHERE category = ?", ("fact",))
    rows = await cursor.fetchall()
```

### Connection Rules
| Rule | Reason |
|------|--------|
| Use connection pools (not connect-per-query) | Reduces connection overhead |
| Set busy_timeout for SQLite | Prevents immediate failure on lock contention |
| Close connections in finally block | Prevents connection leaks |
| Use context managers | Automatic cleanup on exceptions |
| Set WAL mode once at connection creation | Ensures consistent behavior |

## Migration Strategies

### Expand-Contract Pattern (Zero Downtime)
```
Phase 1: Expand
  ALTER TABLE users ADD COLUMN display_name TEXT;
  -- App writes to both name and display_name

Phase 2: Migrate
  UPDATE users SET display_name = name WHERE display_name IS NULL;
  -- Backfill existing data

Phase 3: Contract
  -- App now reads only from display_name
  ALTER TABLE users DROP COLUMN name;  -- Only after all code uses display_name
```

### Migration Best Practices
| Practice | Reason |
|----------|--------|
| One change per migration file | Easy to review, rollback, debug |
| Idempotent migrations | Safe to run twice (`CREATE TABLE IF NOT EXISTS`) |
| Forward-only (no down migrations) | Down migrations are rarely tested and often break |
| Test migrations on production-sized data | A migration fast on 1K rows may lock 10M rows for minutes |
| Back up before migrating | Recovery option if migration corrupts data |

### SQLite-Specific Migration Pattern
```python
def migrate(conn: sqlite3.Connection):
    """Run all pending migrations."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_versions (version INTEGER PRIMARY KEY, applied_at TEXT)")
    current = conn.execute("SELECT MAX(version) FROM schema_versions").fetchone()[0] or 0

    migrations = {
        1: "CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, content TEXT, category TEXT)",
        2: "ALTER TABLE memories ADD COLUMN confidence REAL DEFAULT 0.5",
        3: "CREATE INDEX IF NOT EXISTS idx_memories_category ON memories(category)",
    }

    for version, sql in sorted(migrations.items()):
        if version > current:
            conn.execute(sql)
            conn.execute("INSERT INTO schema_versions VALUES (?, datetime('now'))", (version,))
    conn.commit()
```

## Query Optimization Checklist

- [ ] Use parameterized queries (never f-string SQL)
- [ ] Add indexes for columns in WHERE, JOIN, and ORDER BY clauses
- [ ] Use LIMIT for list queries (never SELECT * without bounds)
- [ ] Batch inserts in transactions (not one commit per row)
- [ ] Use EXPLAIN QUERY PLAN to verify index usage
- [ ] Monitor slow queries (log queries exceeding 100ms)
