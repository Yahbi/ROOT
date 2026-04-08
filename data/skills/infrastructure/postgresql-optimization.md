---
name: PostgreSQL Optimization
description: Connection pooling, EXPLAIN ANALYZE, index strategies, vacuum, partitioning
version: "1.0.0"
author: ROOT
tags: [infrastructure, postgresql, database, performance, indexing, vacuum]
platforms: [all]
---

# PostgreSQL Optimization

Tune PostgreSQL for production workloads with evidence-based configuration and query analysis.

## Connection Pooling

### PgBouncer Configuration
```ini
[pgbouncer]
pool_mode = transaction          # Release conn after each transaction (best for web apps)
max_client_conn = 1000           # Total client connections accepted
default_pool_size = 25           # Connections per user/database pair
reserve_pool_size = 5            # Extra connections for burst traffic
reserve_pool_timeout = 3         # Seconds before using reserve pool
server_idle_timeout = 300        # Close idle server connections after 5min
```

### Pool Sizing Formula
- Optimal connections = `(core_count * 2) + effective_spindle_count`
- For SSD: typically 20-50 connections per database server
- More connections != more throughput (context switching overhead increases)
- Monitor `pg_stat_activity` for connection state distribution

## Query Analysis with EXPLAIN ANALYZE

### Reading Execution Plans
```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT u.name, COUNT(o.id)
FROM users u JOIN orders o ON o.user_id = u.id
WHERE u.created_at > '2025-01-01'
GROUP BY u.name;
```

### Key Metrics to Watch
| Metric | Problem Indicator | Fix |
|--------|------------------|-----|
| Seq Scan on large table | Missing index | Add targeted index |
| Nested Loop with high rows | Bad join strategy | Ensure join columns indexed, check stats |
| Sort with `external merge` | Insufficient `work_mem` | Increase `work_mem` for session or globally |
| Buffers: shared read (high) | Data not cached | Increase `shared_buffers` or add index |
| Actual rows >> estimated rows | Stale statistics | Run `ANALYZE` on the table |

## Index Strategies

### Index Types and When to Use Them
```sql
-- B-tree (default): equality and range queries
CREATE INDEX idx_users_email ON users(email);

-- Partial index: only index rows matching a condition (smaller, faster)
CREATE INDEX idx_orders_pending ON orders(created_at) WHERE status = 'pending';

-- Composite index: multi-column (leftmost prefix rule applies)
CREATE INDEX idx_orders_user_date ON orders(user_id, created_at DESC);

-- GIN index: full-text search, JSONB containment, array overlap
CREATE INDEX idx_docs_content ON documents USING gin(to_tsvector('english', content));

-- BRIN index: very large tables with naturally ordered data (timestamps)
CREATE INDEX idx_logs_ts ON event_logs USING brin(created_at);
```

### Index Maintenance
- Identify unused indexes: `SELECT * FROM pg_stat_user_indexes WHERE idx_scan = 0;`
- Rebuild bloated indexes: `REINDEX CONCURRENTLY INDEX idx_name;`
- Monitor index size vs table size ratio (indexes > table size = likely over-indexed)

## VACUUM and Maintenance

### Autovacuum Tuning
```sql
-- Per-table tuning for high-write tables
ALTER TABLE events SET (
    autovacuum_vacuum_scale_factor = 0.01,   -- Vacuum after 1% dead rows (default 20%)
    autovacuum_analyze_scale_factor = 0.005,  -- Analyze after 0.5% changes
    autovacuum_vacuum_cost_delay = 2          -- Less throttling (default 20ms)
);
```

### Monitoring Dead Tuples
```sql
SELECT schemaname, relname, n_dead_tup, n_live_tup,
       round(n_dead_tup::numeric / NULLIF(n_live_tup, 0) * 100, 2) AS dead_pct
FROM pg_stat_user_tables
ORDER BY n_dead_tup DESC LIMIT 10;
```

## Table Partitioning

### When to Partition
- Tables exceeding 100M rows where queries filter on a predictable column
- Time-series data with clear retention policies (drop old partitions instead of DELETE)
- Tables where VACUUM struggles to keep up with write volume

### Declarative Partitioning
```sql
CREATE TABLE events (
    id bigint GENERATED ALWAYS AS IDENTITY,
    event_type text, payload jsonb, created_at timestamptz
) PARTITION BY RANGE (created_at);

CREATE TABLE events_2025_q1 PARTITION OF events
    FOR VALUES FROM ('2025-01-01') TO ('2025-04-01');

-- Detach and drop old partitions for instant cleanup
ALTER TABLE events DETACH PARTITION events_2024_q1;
DROP TABLE events_2024_q1;
```
