---
name: Event-Driven Design
description: Event sourcing, CQRS, saga pattern, eventual consistency, idempotency
version: "1.0.0"
author: ROOT
tags: [architecture, event-driven, event-sourcing, CQRS, saga, idempotency]
platforms: [all]
---

# Event-Driven Design

Build systems where components communicate through events rather than direct calls, enabling loose coupling and auditability.

## Event Sourcing

### Core Concept
Instead of storing current state, store the sequence of events that produced it.

```python
# Traditional: store current state
{"order_id": "123", "status": "shipped", "amount": 99.99}

# Event sourced: store all events, derive current state
[
    {"type": "OrderCreated", "order_id": "123", "amount": 99.99, "ts": "10:00"},
    {"type": "PaymentReceived", "order_id": "123", "amount": 99.99, "ts": "10:01"},
    {"type": "OrderShipped", "order_id": "123", "tracking": "XYZ", "ts": "10:30"}
]
```

### When to Use Event Sourcing
- **Use when**: Full audit trail required, need to replay or reprocess history, complex business rules
- **Avoid when**: Simple CRUD, no compliance requirements, team unfamiliar with pattern
- Event store is append-only (events are immutable facts that already happened)
- Current state reconstructed by replaying events (use snapshots for performance)

### Snapshot Optimization
- Replaying thousands of events per entity is slow
- Take snapshots every N events (e.g., every 100)
- Reconstruct: load latest snapshot + replay events after snapshot
- Store snapshots separately from the event stream

## CQRS (Command Query Responsibility Segregation)

### Architecture
```
Write Side (Commands)           Read Side (Queries)
  ┌──────────┐                   ┌──────────────┐
  │ Command  │──→ Event Store ──→│ Read Model   │
  │ Handler  │    (source of     │ (denormalized,│
  └──────────┘     truth)        │  optimized)   │
                                 └──────────────┘
```

### Implementation Guidelines
- Write model: normalized, enforces business rules, validates commands
- Read model: denormalized, optimized for query patterns, eventually consistent
- Sync read model via event handlers (subscribe to event stream)
- Multiple read models for different query patterns (list view, detail view, search)

### When CQRS Adds Value
- Read and write workloads have very different scaling requirements
- Complex queries that join many tables (flatten into a single read model)
- Different teams own read vs write logic
- Overkill for simple applications with balanced read/write ratios

## Saga Pattern

### Orchestration vs Choreography
| Approach | Coordination | Pros | Cons |
|----------|-------------|------|------|
| Orchestration | Central saga coordinator | Clear flow, easy to debug | Single point of failure, coupling |
| Choreography | Each service reacts to events | Loose coupling, independent deployment | Hard to trace, implicit flow |

### Saga Compensation (Rollback)
```
Order Saga:
1. CreateOrder → success → 2. ReserveInventory → success → 3. ChargePayment → FAIL
   Compensate: ReleaseInventory → CancelOrder

Each step has a compensating action:
  CreateOrder        ↔  CancelOrder
  ReserveInventory   ↔  ReleaseInventory
  ChargePayment      ↔  RefundPayment
```

### Saga Design Rules
- Every forward action must have a compensating action
- Compensating actions must be idempotent (safe to retry)
- Store saga state persistently (survive process crashes)
- Set timeouts: if a step does not complete within N seconds, trigger compensation

## Eventual Consistency

### Handling in Practice
- **UI feedback**: Show "processing" state immediately, update when confirmed
- **Read-your-writes**: After a write, route reads to the write model temporarily
- **Conflict resolution**: Last-write-wins, merge strategies, or manual resolution
- **Convergence time**: Measure and set SLOs (e.g., "read model within 2 seconds of write")

### Consistency Boundaries
- Strong consistency within a single aggregate (one database transaction)
- Eventual consistency between aggregates (via events)
- Users expect consistency within their own session (read-your-writes)
- Users tolerate eventual consistency across different users' views

## Idempotency

### Why Idempotency Matters
- Networks are unreliable: messages can be delivered more than once
- Retries are essential for reliability but create duplicate processing risk
- Every event handler and API endpoint should be safe to call multiple times

### Implementation Patterns
```python
# Idempotency key: client sends a unique key, server deduplicates
async def process_payment(payment_id: str, idempotency_key: str):
    existing = await db.get("idempotency", idempotency_key)
    if existing:
        return existing  # Already processed, return cached result
    result = await charge_card(payment_id)
    await db.put("idempotency", idempotency_key, result, ttl=86400)
    return result
```

### Deduplication Strategies
- Store processed event IDs in a deduplication table (check before processing)
- Use database upserts: `INSERT ON CONFLICT DO NOTHING`
- Design operations to be naturally idempotent: `SET status = 'shipped'` (safe to repeat)
- TTL on dedup records: keep for 24-72 hours (long enough for all retries)
