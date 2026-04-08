---
name: System Design Interview
description: Load estimation, database selection, caching layers, trade-off analysis
version: "1.0.0"
author: ROOT
tags: [architecture, system-design, interview, estimation, trade-offs, capacity-planning]
platforms: [all]
---

# System Design Interview

Framework for approaching system design problems with structured analysis and clear trade-off reasoning.

## Step 1: Requirements Clarification

### Questions to Ask
- **Functional**: What are the core features? What can be deferred to v2?
- **Scale**: How many users? Reads per second? Writes per second? Data growth rate?
- **Performance**: Latency requirements? (P99 < 200ms for reads?)
- **Availability**: SLA target? (99.9% = 8.7 hours downtime/year, 99.99% = 52 minutes/year)
- **Consistency**: Strong consistency required? Or eventual consistency acceptable?
- **Constraints**: Budget, team size, existing infrastructure, regulatory

### Write Down Assumptions
```
Users: 10M monthly active, 1M daily active
Read:Write ratio: 100:1
Average object size: 1KB
Data retention: 5 years
Peak traffic: 3x average (evenings)
```

## Step 2: Back-of-Envelope Estimation

### Quick Math Templates
```
Requests per second:
  1M DAU × 10 actions/day = 10M requests/day
  10M / 86,400 seconds = ~115 requests/second average
  Peak: 115 × 3 = ~350 requests/second

Storage:
  1M new records/day × 1KB each = 1GB/day
  5 years = 1GB × 365 × 5 = ~1.8TB total

Bandwidth:
  350 RPS × 1KB = 350KB/s = ~2.8 Mbps (trivial)

Memory for caching:
  Cache top 20% of data: 1.8TB × 0.2 = 360GB
  Daily active data: 1GB (easily fits in Redis)
```

### Useful Constants
| Metric | Value |
|--------|-------|
| Seconds in a day | 86,400 (~100K) |
| L1 cache reference | 0.5 ns |
| RAM reference | 100 ns |
| SSD read | 16 us |
| HDD seek | 4 ms |
| Round trip within datacenter | 0.5 ms |
| Round trip cross-continent | 150 ms |

## Step 3: Database Selection

### Decision Matrix
| Requirement | Best Choice | Reasoning |
|------------|-------------|-----------|
| Relational data, transactions | PostgreSQL | ACID, mature, extensible |
| Document storage, flexible schema | MongoDB | Schema evolution, nested documents |
| Key-value, high throughput | Redis, DynamoDB | Sub-millisecond reads, horizontal scale |
| Time series | TimescaleDB, InfluxDB | Optimized for time-range queries, downsampling |
| Graph relationships | Neo4j, Neptune | Efficient traversals, relationship-first |
| Full-text search | Elasticsearch, Meilisearch | Inverted index, relevance scoring |
| Wide column, massive scale | Cassandra, ScyllaDB | Linear horizontal scaling, tunable consistency |
| Embedded, single-server | SQLite | Zero config, single file, WAL mode |

### Polyglot Persistence
- Use different databases for different access patterns within the same system
- Example: PostgreSQL for orders + Redis for sessions + Elasticsearch for search
- Trade-off: operational complexity increases with each database technology

## Step 4: High-Level Architecture

### Standard Web Application Template
```
Clients → CDN → Load Balancer → API Servers (stateless, horizontal)
                                     │
                         ┌───────────┼───────────┐
                         ▼           ▼           ▼
                     Cache (Redis)  Database   Message Queue
                                   (Primary)     │
                                      │          ▼
                                   Replicas   Workers
```

### Component Responsibilities
- **Load Balancer**: Distribute traffic, health checks, SSL termination
- **API Servers**: Stateless request handling (scale horizontally)
- **Cache**: Reduce database load for hot data (TTL-based invalidation)
- **Database**: Source of truth (primary for writes, replicas for reads)
- **Message Queue**: Decouple async work (email, notifications, processing)
- **Workers**: Process background jobs from queue

## Step 5: Deep Dives and Trade-offs

### Common Trade-offs
| Decision | Option A | Option B | Deciding Factor |
|----------|---------|---------|----------------|
| Consistency vs Availability | Strong consistency (CP) | High availability (AP) | CAP: what fails during network partition? |
| SQL vs NoSQL | Structured, joins, ACID | Flexible schema, horizontal scale | Data model complexity, scale requirements |
| Push vs Pull | Real-time, higher server cost | Polling, simpler, higher latency | Freshness requirement, client count |
| Monolith vs Microservices | Simple, fast, coupled | Complex, independent, resilient | Team size, deployment frequency |
| Cache-aside vs Write-through | Lower write latency | Stronger consistency | Write frequency, consistency needs |

### Scaling Checklist
1. Identify the bottleneck (CPU? Memory? I/O? Network?)
2. Can you cache it? (Fastest fix for read-heavy workloads)
3. Can you shard it? (For write-heavy workloads)
4. Can you make it async? (Move work off the critical path)
5. Can you simplify it? (Reduce payload size, eliminate unnecessary joins)

## Step 6: Operational Considerations

### Monitoring
- The Four Golden Signals: latency, traffic, errors, saturation
- Per-service dashboards: P50/P95/P99 latency, error rate, throughput
- Alerting: alert on symptoms (high latency), not causes (high CPU)

### Failure Modes
- What happens when the database is down? (Serve from cache, return degraded response)
- What happens when a downstream service is slow? (Circuit breaker, timeout, fallback)
- What happens during deployment? (Rolling deployment, zero-downtime, canary)
- What happens when traffic spikes 10x? (Auto-scaling, rate limiting, graceful degradation)
