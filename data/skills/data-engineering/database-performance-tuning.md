---
name: Database Performance Tuning
description: Optimize PostgreSQL and SQL database performance through indexing, query optimization, and schema design
version: "1.0.0"
author: ROOT
tags: [data-engineering, database, PostgreSQL, indexing, query-optimization, performance]
platforms: [all]
difficulty: intermediate
---

# Database Performance Tuning

Slow queries destroy user experience. Systematic tuning can achieve 10-1000x speedups
through proper indexing, query rewriting, and schema design.

## Diagnosis Workflow

1. Identify slow queries (pg_stat_statements)
2. Understand the query plan (EXPLAIN ANALYZE)
3. Apply appropriate optimization
4. Verify improvement
5. Monitor for regressions

## Finding Slow Queries

```sql
-- Enable pg_stat_statements extension first:
-- CREATE EXTENSION pg_stat_statements;

-- Top 10 slowest queries by total execution time
SELECT
    query,
    calls,
    total_exec_time / 1000 AS total_seconds,
    mean_exec_time AS avg_ms,
    stddev_exec_time AS stddev_ms,
    rows / calls AS avg_rows
FROM pg_stat_statements
WHERE calls > 100
ORDER BY total_exec_time DESC
LIMIT 10;

-- Queries with high average time (likely needing indexes)
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
WHERE mean_exec_time > 1000  -- > 1 second average
ORDER BY mean_exec_time DESC;
```

## Reading EXPLAIN ANALYZE

```sql
-- Always use EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) for full info
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT * FROM orders WHERE customer_id = 'cust_123' AND status = 'pending';

-- Key things to look for:
-- Seq Scan: reading entire table — add index on filter columns
-- Index Scan: good — using index for lookup
-- Nested Loop with large outer relation: may need index on inner side
-- Sort: expensive without index — add index if sorting frequently
-- Hash Join / Merge Join: acceptable for large datasets
-- Actual Rows vs. Estimated Rows: large discrepancy = stale statistics → ANALYZE table
```

## Indexing Strategy

### Basic Index Creation

```sql
-- Single column index (most common)
CREATE INDEX CONCURRENTLY idx_orders_customer_id ON orders (customer_id);
-- CONCURRENTLY: builds without locking table (use for production)

-- Composite index (covers multi-column queries)
CREATE INDEX CONCURRENTLY idx_orders_customer_status
ON orders (customer_id, status)
WHERE status != 'archived';  -- Partial index — smaller, faster

-- Index for range queries (timestamps)
CREATE INDEX CONCURRENTLY idx_orders_created_at ON orders (created_at DESC);

-- Covering index (avoids table lookup entirely)
CREATE INDEX CONCURRENTLY idx_orders_covering
ON orders (customer_id, status)
INCLUDE (order_id, total_amount, created_at);
-- Query using only these columns → index-only scan (fastest possible)
```

### Index Selection Rules

| Query Pattern | Index Type |
|--------------|-----------|
| `WHERE col = value` | B-tree on col |
| `WHERE col > x AND col < y` | B-tree on col |
| `WHERE col IN (...)` | B-tree on col |
| `WHERE col LIKE 'prefix%'` | B-tree on col |
| `WHERE col LIKE '%suffix'` | Cannot use B-tree — consider full-text |
| `WHERE col IS NULL` | Partial index `WHERE col IS NULL` |
| `ORDER BY col` | B-tree on col (same direction) |
| Full-text search | GIN index with tsvector |
| JSON/JSONB queries | GIN index on JSONB column |
| Geospatial queries | GiST index |

### When NOT to Index

- Columns with very low cardinality (e.g., boolean, 2-3 distinct values)
- Columns rarely used in WHERE/JOIN/ORDER BY
- Small tables (< 10k rows) — full scan is fast enough
- Columns updated very frequently — index maintenance overhead

## Query Optimization Techniques

### N+1 Query Problem

```python
# BAD: N+1 queries — one query per order
orders = db.execute("SELECT * FROM orders WHERE status = 'pending'")
for order in orders:
    customer = db.execute("SELECT * FROM customers WHERE id = ?", order.customer_id)
    # → 1 + N queries for N orders

# GOOD: Single JOIN query
orders_with_customers = db.execute("""
    SELECT o.*, c.name, c.email
    FROM orders o
    JOIN customers c ON c.id = o.customer_id
    WHERE o.status = 'pending'
""")
```

### Pagination Optimization

```sql
-- BAD: OFFSET pagination (slow for large offsets — scans all preceding rows)
SELECT * FROM orders ORDER BY created_at DESC LIMIT 20 OFFSET 10000;

-- GOOD: Keyset/cursor pagination (O(log n) regardless of page)
SELECT * FROM orders
WHERE created_at < '2026-04-01T10:00:00'  -- Last seen value from previous page
ORDER BY created_at DESC
LIMIT 20;
```

### Avoiding SELECT *

```sql
-- BAD: Fetches all columns including large text/JSONB fields
SELECT * FROM events WHERE user_id = 'u123';

-- GOOD: Fetch only needed columns (enables index-only scans)
SELECT event_id, event_type, created_at
FROM events
WHERE user_id = 'u123';
```

### CTEs and Subquery Optimization

```sql
-- In PostgreSQL 12+, CTEs are not optimization fences by default
-- Use MATERIALIZED when you want to force CTE to execute once
WITH high_value_customers AS MATERIALIZED (
    SELECT customer_id
    FROM orders
    GROUP BY customer_id
    HAVING SUM(total_amount) > 10000
)
SELECT c.*, hvc.customer_id IS NOT NULL AS is_high_value
FROM customers c
LEFT JOIN high_value_customers hvc ON hvc.customer_id = c.id;
```

## Connection Pooling

```python
# PgBouncer or connection pool in application layer
from psycopg2 import pool

# Create pool on application startup
connection_pool = pool.ThreadedConnectionPool(
    minconn=5,
    maxconn=20,
    dsn="postgresql://user:pass@localhost/mydb"
)

def get_db_connection():
    return connection_pool.getconn()

def return_db_connection(conn):
    connection_pool.putconn(conn)

# Rule of thumb: max_connections = (num_cores * 2) + effective_spindle_count
# For web apps: use pgbouncer in transaction mode for many short-lived connections
```

## Vacuum and Maintenance

```sql
-- PostgreSQL accumulates dead tuples — autovacuum handles this automatically
-- Force vacuum for tables with many updates/deletes:
VACUUM ANALYZE orders;

-- Full vacuum (exclusive lock — use with caution):
VACUUM FULL ANALYZE orders;  -- Reclaims disk space but locks table

-- Update statistics for query planner:
ANALYZE orders;

-- Monitor bloat:
SELECT schemaname, tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS total_size,
    pg_size_pretty(pg_relation_size(schemaname||'.'||tablename)) AS table_size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

## Partitioning for Large Tables

```sql
-- Range partitioning by date for time-series tables
CREATE TABLE events (
    event_id UUID,
    user_id TEXT,
    event_type TEXT,
    created_at TIMESTAMP NOT NULL
) PARTITION BY RANGE (created_at);

CREATE TABLE events_2026_q1 PARTITION OF events
    FOR VALUES FROM ('2026-01-01') TO ('2026-04-01');

CREATE TABLE events_2026_q2 PARTITION OF events
    FOR VALUES FROM ('2026-04-01') TO ('2026-07-01');

-- Create indexes on each partition
CREATE INDEX ON events_2026_q1 (user_id, created_at);
CREATE INDEX ON events_2026_q2 (user_id, created_at);
-- Queries filtering on created_at will only scan relevant partitions
```
