---
name: Streaming Data Pipelines
description: Build real-time data processing pipelines using Kafka, Spark Streaming, and Flink
version: "1.0.0"
author: ROOT
tags: [data-engineering, streaming, kafka, spark, flink, real-time, event-driven]
platforms: [all]
difficulty: advanced
---

# Streaming Data Pipelines

Process data in real time as events are generated rather than in scheduled batches.
Use when: fraud detection, personalization, IoT, financial trading, live dashboards.

## Streaming Architecture Patterns

```
Event Sources → Message Broker → Stream Processor → Outputs
(apps, IoT)     (Kafka)          (Flink/Spark)      (DB, alerts, ML)

Lambda Architecture: Batch layer (accuracy) + Speed layer (freshness)
Kappa Architecture:  Stream layer only (simpler, preferred for new builds)
```

## Apache Kafka Setup

### Topic Configuration

```python
from kafka.admin import KafkaAdminClient, NewTopic

admin = KafkaAdminClient(bootstrap_servers="localhost:9092")

topic = NewTopic(
    name="user-events",
    num_partitions=12,     # Parallelism factor — scale consumers up to this count
    replication_factor=3,  # High availability — tolerate 2 broker failures
    topic_configs={
        "retention.ms": str(7 * 24 * 3600 * 1000),  # 7-day retention
        "compression.type": "lz4",                    # Fast compression
        "min.insync.replicas": "2",                   # Durability guarantee
    }
)
admin.create_topics([topic])
```

### Producer

```python
from kafka import KafkaProducer
import json

producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8"),
    acks="all",             # Wait for all replicas to acknowledge
    retries=3,
    compression_type="lz4"
)

def publish_event(topic: str, event: dict, partition_key: str = None):
    future = producer.send(
        topic=topic,
        value=event,
        key=partition_key,  # Same key always goes to same partition (ordering guarantee)
        timestamp_ms=int(datetime.now().timestamp() * 1000)
    )
    # Optionally wait for confirmation:
    # record_metadata = future.get(timeout=10)
    return future

# Usage
publish_event(
    topic="user-events",
    event={"user_id": "u123", "action": "purchase", "amount": 99.99,
           "timestamp": datetime.now().isoformat()},
    partition_key="u123"  # All events for u123 go to same partition → ordering
)

producer.flush()  # Wait for all buffered messages to be sent
```

### Consumer

```python
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    "user-events",
    bootstrap_servers="localhost:9092",
    group_id="fraud-detector",    # Consumer group for load balancing
    auto_offset_reset="earliest",  # Start from beginning if no committed offset
    enable_auto_commit=False,       # Manual commit for at-least-once guarantee
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    max_poll_records=500,
    session_timeout_ms=30000,
)

def process_events():
    for message_batch in consumer:
        process_single_message(message_batch.value)
        consumer.commit()  # Commit after successful processing

def batch_consumer():
    """Process messages in batches for efficiency."""
    while True:
        messages = consumer.poll(timeout_ms=1000, max_records=100)
        for partition, records in messages.items():
            batch = [r.value for r in records]
            process_batch(batch)
        consumer.commit()
```

## Spark Structured Streaming

```python
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json, window, sum as spark_sum
from pyspark.sql.types import StructType, StringType, DoubleType, TimestampType

spark = SparkSession.builder \
    .appName("UserEventStream") \
    .config("spark.streaming.stopGracefullyOnShutdown", "true") \
    .getOrCreate()

schema = StructType() \
    .add("user_id", StringType()) \
    .add("action", StringType()) \
    .add("amount", DoubleType()) \
    .add("timestamp", TimestampType())

# Read from Kafka
stream_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "user-events") \
    .option("startingOffsets", "latest") \
    .load()

# Parse JSON and apply transformations
events_df = stream_df \
    .select(from_json(col("value").cast("string"), schema).alias("data")) \
    .select("data.*") \
    .withWatermark("timestamp", "10 minutes")  # Late data tolerance

# Windowed aggregation — 5-minute rolling spend per user
spend_per_user = events_df \
    .filter(col("action") == "purchase") \
    .groupBy(window(col("timestamp"), "5 minutes"), col("user_id")) \
    .agg(spark_sum("amount").alias("total_spend_5min"))

# Write to Kafka (downstream processing)
query = spend_per_user.writeStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("topic", "user-spend-aggregates") \
    .option("checkpointLocation", "/tmp/spark-checkpoints/spend") \
    .outputMode("update") \
    .trigger(processingTime="30 seconds") \
    .start()

query.awaitTermination()
```

## Flink Stateful Processing

```python
# PyFlink for complex stateful event processing
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment

env = StreamExecutionEnvironment.get_execution_environment()
env.set_parallelism(4)
t_env = StreamTableEnvironment.create(env)

# Create Kafka source
t_env.execute_sql("""
    CREATE TABLE user_events (
        user_id STRING,
        action STRING,
        amount DOUBLE,
        event_time TIMESTAMP(3),
        WATERMARK FOR event_time AS event_time - INTERVAL '10' SECOND
    ) WITH (
        'connector' = 'kafka',
        'topic' = 'user-events',
        'properties.bootstrap.servers' = 'localhost:9092',
        'format' = 'json'
    )
""")

# Fraud detection: > $1000 in 10 minutes
t_env.execute_sql("""
    SELECT
        user_id,
        SUM(amount) AS total_spend,
        COUNT(*) AS transaction_count,
        TUMBLE_START(event_time, INTERVAL '10' MINUTE) AS window_start
    FROM user_events
    WHERE action = 'purchase'
    GROUP BY user_id, TUMBLE(event_time, INTERVAL '10' MINUTE)
    HAVING SUM(amount) > 1000
""")
```

## Delivery Guarantees

| Guarantee | Description | Use When |
|-----------|-------------|---------|
| At-most-once | Fire and forget — may lose messages | Metrics, logging |
| At-least-once | Retry on failure — may duplicate | Most business events |
| Exactly-once | Idempotent + transactional | Financial transactions |

```python
# Exactly-once with idempotent writes
def process_with_idempotency(event: dict, db_conn):
    """Upsert ensures exactly-once semantics even with at-least-once delivery."""
    db_conn.execute("""
        INSERT INTO processed_events (event_id, user_id, amount, processed_at)
        VALUES (%s, %s, %s, NOW())
        ON CONFLICT (event_id) DO NOTHING  -- Idempotent: duplicate events are no-ops
    """, (event["event_id"], event["user_id"], event["amount"]))
```

## Monitoring Streaming Pipelines

```python
STREAMING_METRICS = {
    "consumer_lag": "Messages in Kafka ahead of consumer — high lag = processing too slow",
    "throughput_eps": "Events per second — capacity headroom check",
    "processing_latency_p99": "End-to-end time from event to output — SLA check",
    "reprocessing_rate": "% of events processed more than once — data quality",
    "error_rate": "% of events that fail processing — alerting threshold",
}

# Alert thresholds:
ALERTS = {
    "consumer_lag_threshold": 50000,    # > 50k messages behind → scale consumers
    "processing_latency_sec": 30,       # > 30 seconds → pipeline stuck
    "error_rate_threshold": 0.01,       # > 1% errors → investigate immediately
}
```
