---
name: SQL Optimization
description: Query planning, indexing strategies, EXPLAIN analysis, and common patterns
version: "1.0.0"
author: ROOT
tags: [data-analysis, SQL, optimization, indexing, query-planning]
platforms: [all]
---

# SQL Optimization

Write efficient queries and design indexes that keep databases fast at scale.

## Index Strategy

### When to Create Indexes
- Columns in WHERE clauses that filter large tables (> 10K rows)
- Columns used in JOIN conditions
- Columns used in ORDER BY (avoids filesort)
- Columns with high cardinality (unique values) benefit most

### Index Types
| Type | Use Case | Example |
|------|---------|---------|
| B-tree (default) | Equality, range, sorting | `CREATE INDEX idx_name ON users(email)` |
| Composite | Multi-column queries | `CREATE INDEX idx_name ON orders(user_id, created_at)` |
| Partial | Filter on common condition | `CREATE INDEX idx_name ON orders(status) WHERE status = 'active'` |
| Covering | Query answered entirely from index | Include all SELECT columns in index |
| FTS5 (SQLite) | Full-text search | `CREATE VIRTUAL TABLE docs USING fts5(title, body)` |

### Composite Index Rules
- Column order matters: put equality columns first, range columns last
- `INDEX(a, b, c)` supports queries on `(a)`, `(a, b)`, `(a, b, c)` — not `(b)` or `(c)` alone
- The "leftmost prefix" rule: index is used left-to-right

## EXPLAIN Analysis

### Reading EXPLAIN Output
- **Seq Scan** / **FULL TABLE SCAN**: No index used — add index if table is large
- **Index Scan**: Good — index is being used
- **Index Only Scan**: Best — query answered entirely from index
- **Sort**: If unexpected, consider adding index with ORDER BY columns
- **Nested Loop**: OK for small inner tables, expensive for large joins

### SQLite EXPLAIN
```sql
EXPLAIN QUERY PLAN SELECT * FROM users WHERE email = 'test@example.com';
-- Look for: SEARCH users USING INDEX idx_users_email
-- Bad: SCAN users (full table scan)
```

## Common Query Optimizations

### Avoid N+1 Queries
- Bad: Loop over users, query orders for each user (100 users = 101 queries)
- Good: Single JOIN or subquery (`SELECT * FROM orders WHERE user_id IN (...)`)

### Pagination
- **Offset pagination**: `LIMIT 20 OFFSET 100` — gets slower as offset grows
- **Cursor pagination**: `WHERE id > last_seen_id LIMIT 20` — consistent performance
- Always use cursor pagination for large datasets

### Batch Operations
- Insert: Use multi-row INSERT instead of one-at-a-time (`INSERT INTO t VALUES (...), (...), (...)`)
- Update: Batch updates with WHERE clause, not individual UPDATE per row
- Delete: Delete in chunks with LIMIT to avoid long locks

## Performance Checklist

- [ ] Every query hitting > 1K rows has appropriate indexes
- [ ] No SELECT * in production code (select only needed columns)
- [ ] EXPLAIN reviewed for all queries in hot paths
- [ ] N+1 queries eliminated (use JOINs or batch fetching)
- [ ] Pagination uses cursor-based approach for large tables
- [ ] Unused indexes removed (they slow down writes)
- [ ] Query performance monitored: log queries taking > 100ms
