---
name: Streaming Architecture
description: Design and operate real-time data streaming systems with Kafka, Flink, and Spark Streaming
category: data-engineering
difficulty: advanced
version: "1.0.0"
author: ROOT
tags: [data-engineering, streaming, kafka, flink, spark-streaming, real-time, event-driven]
platforms: [all]
---

# Streaming Architecture

Build reliable, scalable, and low-latency systems for real-time data ingestion and processing.

## Core Streaming Concepts

### Event Fundamentals
- **Event**: Immutable record of something that happened — has a key, value, timestamp, and optional headers
- **Stream**: Unbounded sequence of events ordered by time
- **Topic**: Named log that stores events; partitioned for parallelism and scalability
- **Consumer group**: Set of consumers that collectively read all partitions of a topic

### Time Semantics
| Time Type | Definition | Use Case |
|-----------|-----------|----------|
| **Event time** | When the event actually occurred | Accurate business analytics |
| **Ingestion time** | When the event entered the pipeline | Simpler, less accurate |
| **Processing time** | When the event is processed | Lowest latency, highest inaccuracy |

### Watermarks
- Watermark = estimate of the maximum event time observed — events before watermark are "complete"
- Late arrivals: events with event time < watermark; handled by allowed lateness window
- Choosing watermark lag: too small = data loss; too large = increased latency

## Apache Kafka Architecture

### Topic Design
```
Topic: orders.created
  ├── Partition 0 (key: user_id % num_partitions)
  ├── Partition 1
  └── Partition 2

Retention: 7 days (or size-based for very high volume)
Replication factor: 3 (tolerate 1 broker failure)
Min ISR: 2 (require 2 replicas to acknowledge write)
```

### Producer Configuration
```python
from confluent_kafka import Producer

producer = Producer({
    "bootstrap.servers": "kafka1:9092,kafka2:9092,kafka3:9092",
    "acks": "all",                    # Wait for all ISR replicas
    "enable.idempotence": True,       # Exactly-once semantics
    "max.in.flight.requests.per.connection": 5,
    "compression.type": "snappy",     # Balance CPU vs network
    "linger.ms": 5,                   # Batch for 5ms to improve throughput
    "batch.size": 65536,              # 64KB batches
})

def delivery_report(err, msg):
    if err:
        log.error(f"Delivery failed: {err}")
    else:
        log.debug(f"Delivered to {msg.topic()} [{msg.partition()}] offset {msg.offset()}")

producer.produce("orders.created", key=user_id, value=order_json, callback=delivery_report)
producer.flush()
```

### Consumer Configuration
```python
from confluent_kafka import Consumer

consumer = Consumer({
    "bootstrap.servers": "kafka1:9092,kafka2:9092",
    "group.id": "order-processor",
    "auto.offset.reset": "earliest",
    "enable.auto.commit": False,       # Manual commit for at-least-once
    "max.poll.interval.ms": 300000,
    "session.timeout.ms": 30000,
})

consumer.subscribe(["orders.created"])
while True:
    msg = consumer.poll(timeout=1.0)
    if msg and not msg.error():
        process(msg)
        consumer.commit(asynchronous=False)   # Commit after successful processing
```

## Apache Flink — Stream Processing

### Windowing Strategies
```java
// Tumbling window: non-overlapping, fixed-size windows
stream
    .keyBy(Order::getUserId)
    .window(TumblingEventTimeWindows.of(Time.minutes(5)))
    .aggregate(new OrderCountAggregator());

// Sliding window: overlapping windows
stream
    .keyBy(Order::getUserId)
    .window(SlidingEventTimeWindows.of(Time.minutes(10), Time.minutes(5)))
    .aggregate(new RevenueAggregator());

// Session window: gap-based grouping
stream
    .keyBy(User::getId)
    .window(EventTimeSessionWindows.withGap(Time.minutes(30)))
    .aggregate(new SessionAggregator());
```

### Stateful Processing
- **Keyed state**: Scoped to a key — ValueState, ListState, MapState, AggregatingState
- **Operator state**: Scoped to an operator instance — used for source/sink coordination
- State is stored in RocksDB (large state) or heap (small state)
- Checkpoint state to S3/GCS for fault tolerance; restore from checkpoint on failure

### Exactly-Once End-to-End
```
Kafka Source → Flink (checkpointing + transactional state) → Kafka Sink
```
- Enable Flink checkpointing: `env.enableCheckpointing(60_000)` (every 60s)
- Use `KafkaSink` with `DeliveryGuarantee.EXACTLY_ONCE`
- Requires Kafka transactions (idempotent producer + transaction coordinator)

## Spark Structured Streaming

### Reading from Kafka
```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col

spark = SparkSession.builder.appName("OrderStream").getOrCreate()

raw_stream = (spark.readStream
    .format("kafka")
    .option("kafka.bootstrap.servers", "kafka1:9092")
    .option("subscribe", "orders.created")
    .option("startingOffsets", "earliest")
    .load())

orders = (raw_stream
    .select(from_json(col("value").cast("string"), order_schema).alias("order"))
    .select("order.*"))

# Windowed aggregation
from pyspark.sql.functions import window

revenue_by_hour = (orders
    .withWatermark("order_time", "10 minutes")
    .groupBy(window("order_time", "1 hour"), "product_category")
    .agg({"amount": "sum"}))

query = (revenue_by_hour.writeStream
    .outputMode("append")
    .format("delta")
    .option("checkpointLocation", "s3://bucket/checkpoints/revenue")
    .start("s3://bucket/delta/revenue_by_hour"))
```

## Delivery Guarantees

| Guarantee | How | Trade-off |
|-----------|-----|-----------|
| At-most-once | Fire and forget, no retry | Possible data loss |
| At-least-once | Retry until acknowledged, idempotent consumer | Possible duplicates |
| Exactly-once | Transactions + idempotent producer + transactional consumer | Highest latency/complexity |

## Topology Design Patterns

### Fan-Out Pattern
```
orders.created ──► inventory.reserve
                ──► notification.send
                ──► analytics.ingest
```
Multiple downstream consumers from one source topic — each consumer group processes independently.

### Enrichment Pattern
```
orders.created ──► [Flink: join with users table] ──► orders.enriched
```
Stream-table join: enrich events with reference data from a compacted topic or external store.

### CQRS with Event Sourcing
```
Commands ──► Command Handler ──► Events (Kafka) ──► Read Model Projections
```
Source of truth is the event log; materialized views built by replaying events.

## Monitoring & Alerting

| Metric | Alert Threshold | Tool |
|--------|----------------|------|
| Consumer lag | > 10,000 messages | Kafka Lag Exporter + Prometheus |
| Processing latency (p99) | > 5 seconds | Flink metrics |
| Checkpoint failure | Any failure | Flink dashboard |
| Topic disk usage | > 80% | Confluent Control Center |
| Producer error rate | > 0.1% | Kafka producer metrics |

## Operational Runbook

1. **Consumer lag spike**: Check consumer health, check for schema mismatch, scale consumers
2. **Processing exceptions**: Dead letter topic pattern — route failed records to `topic.DLQ`
3. **Checkpoint failure**: Check storage backend, reduce checkpoint interval, increase timeout
4. **Rebalance storm**: Tune `session.timeout.ms` and `heartbeat.interval.ms`; reduce consumer count per group
