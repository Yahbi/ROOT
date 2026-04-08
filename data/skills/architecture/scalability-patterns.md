---
name: Scalability Patterns
description: Horizontal/vertical scaling, sharding, read replicas, CQRS, denormalization
version: "1.0.0"
author: ROOT
tags: [architecture, scalability, sharding, read-replicas, CQRS, denormalization]
platforms: [all]
---

# Scalability Patterns

Design systems that handle increasing load gracefully through proven scaling strategies.

## Scaling Dimensions

### Vertical vs Horizontal
| Dimension | Method | Limit | Cost Curve |
|-----------|--------|-------|------------|
| Vertical (scale up) | Bigger machine: more CPU, RAM, SSD | Hardware ceiling (~256 cores, 24TB RAM) | Exponential |
| Horizontal (scale out) | More machines behind load balancer | Practically unlimited | Linear |

### Decision Framework
- **Start vertical**: Simpler architecture, no distributed system complexity
- **Go horizontal when**: Single machine cannot handle load, need fault tolerance, need geographic distribution
- **Hybrid**: Vertical for databases (fewer, larger nodes), horizontal for stateless services

## Database Sharding

### Sharding Strategies
```
Hash-based:  shard_id = hash(user_id) % num_shards
Range-based: shard_1 = users A-M, shard_2 = users N-Z
Directory:   lookup table maps entity → shard
```

### When to Shard
- Single database exceeds read/write capacity (after exhausting indexes, caching, read replicas)
- Table size makes maintenance operations impractical (VACUUM, ALTER TABLE take hours)
- Typical trigger: > 1TB database or > 10,000 writes/second sustained

### Sharding Challenges
| Challenge | Mitigation |
|-----------|------------|
| Cross-shard queries | Denormalize data so most queries hit one shard |
| Cross-shard transactions | Avoid; use saga pattern for multi-shard operations |
| Rebalancing | Use consistent hashing (add shards without reshuffling everything) |
| Hotspots | Monitor per-shard load; split hot shards |
| Schema migrations | Must coordinate across all shards simultaneously |

### Consistent Hashing
```python
# Adding a 4th shard only moves ~25% of keys (vs 75% with modular hashing)
import hashlib

class ConsistentHash:
    def __init__(self, nodes, virtual_nodes=150):
        self.ring = {}
        for node in nodes:
            for i in range(virtual_nodes):
                key = hashlib.md5(f"{node}:{i}".encode()).hexdigest()
                self.ring[key] = node

    def get_node(self, key: str) -> str:
        hashed = hashlib.md5(key.encode()).hexdigest()
        sorted_keys = sorted(self.ring.keys())
        for ring_key in sorted_keys:
            if hashed <= ring_key:
                return self.ring[ring_key]
        return self.ring[sorted_keys[0]]
```

## Read Replicas

### Architecture
```
Writes → Primary DB (single node)
Reads  → Read Replicas (N nodes, async replication)
```

### Implementation Guidelines
- Route all writes to primary, reads to replicas (application-level or proxy-level routing)
- Replication lag: typically < 1 second, but plan for worst case
- Read-your-writes: after a write, read from primary for that user's session (for N seconds)
- Failover: promote replica to primary if primary fails (automatic with Patroni, RDS Multi-AZ)
- Replica count: 1-2 for most workloads, 5+ for read-heavy analytics

### Replication Lag Monitoring
```sql
-- PostgreSQL: check replication lag on replica
SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;
-- Alert if lag > 5 seconds
```

## Denormalization

### Trade-offs
| Normalized (3NF) | Denormalized |
|-------------------|-------------|
| No data duplication | Duplicated data |
| Complex joins for reads | Single table reads |
| Simple writes | Complex writes (update all copies) |
| Strong consistency | Eventual consistency possible |
| Good for OLTP | Good for OLAP and read-heavy |

### Common Denormalization Patterns
```sql
-- Materialized view: precomputed join, refreshed periodically
CREATE MATERIALIZED VIEW order_summary AS
  SELECT o.id, o.created_at, u.name AS customer_name,
         SUM(ol.quantity * ol.price) AS total
  FROM orders o
  JOIN users u ON o.user_id = u.id
  JOIN order_lines ol ON ol.order_id = o.id
  GROUP BY o.id, o.created_at, u.name;

-- Refresh on schedule or trigger
REFRESH MATERIALIZED VIEW CONCURRENTLY order_summary;
```

### Embedding Related Data
- Store frequently accessed related data together (e.g., user name in order record)
- Update embedded copies via events (user renamed -> update all orders with that user)
- Accept staleness for display fields (user name in old orders does not need to update)

## Caching as a Scaling Tool

### Cache Placement
```
Client → CDN Cache → API Gateway Cache → Application Cache (Redis) → Database
```

### Cache Hit Rate Impact
| Hit Rate | Effective Load on DB |
|----------|---------------------|
| 0% | 100% (no caching) |
| 50% | 50% |
| 90% | 10% |
| 99% | 1% (most reads from cache) |

### Cache Warming
- Pre-populate cache at startup for known hot data (top 1000 products, active users)
- Use background jobs to refresh cache before TTL expires (avoid thundering herd)
- Monitor cache hit rate: < 80% indicates wrong cache keys or too-short TTL
