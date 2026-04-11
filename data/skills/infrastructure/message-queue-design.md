---
name: Message Queue Design
description: NATS vs Kafka vs Redis Streams, consumer groups, DLQ, backpressure
version: "1.0.0"
author: ROOT
tags: [infrastructure, message-queue, kafka, nats, redis-streams, DLQ, backpressure]
platforms: [all]
---

# Message Queue Design

Choose and configure the right message queue for your throughput, durability, and latency requirements.

## Queue Selection

### Comparison Matrix
| Feature | NATS JetStream | Kafka | Redis Streams |
|---------|---------------|-------|---------------|
| Latency | Sub-millisecond | Low milliseconds | Sub-millisecond |
| Throughput | 100K+ msg/s | 1M+ msg/s | 500K+ msg/s |
| Durability | Configurable (memory/file) | Disk-first, replicated | AOF/RDB persistence |
| Ordering | Per-subject | Per-partition | Per-stream |
| Operational complexity | Low (single binary) | High (ZooKeeper/KRaft) | Low (existing Redis) |
| Consumer groups | Yes (pull-based) | Yes (partition-based) | Yes (XREADGROUP) |
| Best for | Microservices, request-reply | Event sourcing, high-volume logs | Simple queues, already using Redis |

### Decision Criteria
- **Already running Redis?** Use Redis Streams for simple task queues (avoid new infra)
- **Need request-reply pattern?** NATS excels at this natively
- **Processing millions of events with replay?** Kafka is the standard
- **Single-server deployment?** Redis Streams or embedded NATS
- **Need exactly-once semantics?** Kafka with idempotent producers; others need application-level dedup

## Consumer Groups

### Kafka Consumer Groups
```python
# Each consumer in a group gets a subset of partitions (parallel processing)
consumer = KafkaConsumer(
    'orders',
    group_id='order-processors',
    auto_offset_reset='earliest',
    enable_auto_commit=False,  # Manual commit for at-least-once
    max_poll_records=100
)
for message in consumer:
    process(message)
    consumer.commit()  # Commit after successful processing
```

### Scaling Rules
- Kafka: max consumers per group = number of partitions (create enough partitions upfront)
- Redis Streams: any number of consumers per group (messages distributed round-robin)
- NATS: pull subscribers with configurable batch sizes

## Dead Letter Queues (DLQ)

### DLQ Pattern
```
Main Queue → Consumer → Process
                ↓ (failure after N retries)
           Dead Letter Queue → Alert → Manual review/replay
```

### Implementation Guidelines
- Set max retry count (typically 3-5) before routing to DLQ
- Include original message, error details, retry count, and timestamp in DLQ entry
- Monitor DLQ size: growing DLQ = systemic problem, not transient failure
- Build a replay mechanism: ability to re-inject DLQ messages after the fix is deployed
- DLQ retention should be longer than main queue (30-90 days)

### Retry Strategy
```python
def process_with_retry(message, max_retries=3):
    for attempt in range(max_retries):
        try:
            process(message)
            return  # Success
        except TransientError:
            wait = min(2 ** attempt, 30)  # Exponential backoff, max 30s
            time.sleep(wait)
        except PermanentError:
            send_to_dlq(message, reason="permanent_failure")
            return
    send_to_dlq(message, reason=f"max_retries_exceeded_{max_retries}")
```

## Backpressure

### Detection Signals
| Signal | Threshold | Action |
|--------|-----------|--------|
| Consumer lag | > 10,000 messages | Scale consumers horizontally |
| Processing latency | > P99 SLA | Check downstream dependencies |
| Queue depth | > 1 hour of production | Enable backpressure on producers |
| Memory usage | > 80% of queue memory | Drop low-priority messages or pause producers |

### Backpressure Strategies
- **Producer-side**: Block or return error when queue is full (TCP backpressure for NATS)
- **Consumer-side**: Use `max_poll_records` to limit batch size per consumer
- **Tiered priority**: Separate high/low priority into different queues; shed low-priority first
- **Adaptive rate**: Producers measure consumer lag and throttle send rate dynamically

## Message Design

### Message Schema Best Practices
```json
{
  "id": "uuid-v4",
  "type": "order.created",
  "source": "order-service",
  "timestamp": "2025-01-15T10:30:00Z",
  "data": { "order_id": "12345", "amount": 99.99 },
  "metadata": { "correlation_id": "req-abc", "version": 1 }
}
```

- Always include a unique message ID (for deduplication)
- Include correlation ID for distributed tracing
- Version your message schema (consumers must handle old versions)
- Keep messages small (< 1MB); store large payloads in object storage and reference by URL
