---
name: Change Data Capture
description: Capture and stream database changes in real-time using CDC patterns, Debezium, and log-based replication
category: data-engineering
difficulty: advanced
version: "1.0.0"
author: ROOT
tags: [data-engineering, cdc, debezium, kafka, replication, postgres, mysql, real-time]
platforms: [all]
---

# Change Data Capture (CDC)

Capture database changes (INSERT, UPDATE, DELETE) in real-time and stream them to downstream systems without impacting the source database.

## CDC Approaches

| Approach | How | Pros | Cons |
|----------|-----|------|------|
| **Log-based** | Read database write-ahead log (WAL/binlog) | Zero impact on source, captures deletes | Requires DB replication slot/privileges |
| **Trigger-based** | DB triggers write changes to audit table | Works on any DB version | Performance impact on source, misses DDL |
| **Query-based** | Poll `WHERE updated_at > last_watermark` | Simple, no special privileges | Misses hard deletes, polling lag |
| **Dual-write** | Application writes to both DB and message bus | Full control | Risk of inconsistency if one write fails |

## Log-Based CDC with Debezium

### Architecture
```
PostgreSQL WAL
     ↓
Debezium Connector (Kafka Connect)
     ↓
Kafka Topic: postgres.public.orders
     ↓
Consumers: DWH loader, search index, cache invalidator
```

### Debezium PostgreSQL Connector Configuration
```json
{
  "name": "postgres-orders-cdc",
  "config": {
    "connector.class": "io.debezium.connector.postgresql.PostgresConnector",
    "database.hostname": "postgres.internal",
    "database.port": "5432",
    "database.user": "debezium_user",
    "database.password": "${file:/kafka/secrets/creds.properties:password}",
    "database.dbname": "production",
    "database.server.name": "postgres",
    "plugin.name": "pgoutput",
    "table.include.list": "public.orders,public.users,public.payments",
    "publication.name": "debezium_pub",
    "slot.name": "debezium_slot",

    "heartbeat.interval.ms": "10000",
    "tombstones.on.delete": "true",

    "transforms": "unwrap",
    "transforms.unwrap.type": "io.debezium.transforms.ExtractNewRecordState",
    "transforms.unwrap.delete.handling.mode": "rewrite",
    "transforms.unwrap.drop.tombstones": "false",

    "key.converter": "io.confluent.kafka.serializers.KafkaAvroSerializer",
    "value.converter": "io.confluent.kafka.serializers.KafkaAvroSerializer",
    "key.converter.schema.registry.url": "http://schema-registry:8081",
    "value.converter.schema.registry.url": "http://schema-registry:8081"
  }
}
```

### PostgreSQL Setup for CDC
```sql
-- 1. Set replication level (requires restart)
-- In postgresql.conf:
-- wal_level = logical
-- max_replication_slots = 5
-- max_wal_senders = 5

-- 2. Create dedicated replication user
CREATE USER debezium_user WITH REPLICATION LOGIN PASSWORD 'secure_password';
GRANT SELECT ON ALL TABLES IN SCHEMA public TO debezium_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO debezium_user;

-- 3. Create publication for tables to capture
CREATE PUBLICATION debezium_pub FOR TABLE orders, users, payments;

-- 4. Verify replication slot (created by Debezium automatically)
SELECT * FROM pg_replication_slots WHERE slot_name = 'debezium_slot';
```

### MySQL/MariaDB Connector
```json
{
  "name": "mysql-cdc",
  "config": {
    "connector.class": "io.debezium.connector.mysql.MySqlConnector",
    "database.hostname": "mysql.internal",
    "database.port": "3306",
    "database.user": "debezium",
    "database.password": "${file:/kafka/secrets/mysql.properties:password}",
    "database.server.id": "184054",
    "database.server.name": "mysql",
    "database.include.list": "production",
    "table.include.list": "production.orders,production.users",
    "database.history.kafka.topic": "schema-changes.production",
    "database.history.kafka.bootstrap.servers": "kafka1:9092"
  }
}
```

## CDC Event Structure

### Debezium Event (Unwrapped with ExtractNewRecordState)
```json
{
  "__op": "u",             // c=create, u=update, d=delete, r=read (snapshot)
  "__source_ts_ms": 1705276800000,
  "__table": "orders",
  "__lsn": 12345678,       // Log sequence number (PostgreSQL)
  "order_id": "ord_abc123",
  "status": "paid",        // Current value (after image)
  "amount": 99.99,
  "__deleted": false
}
```

### Handling Deletes
```python
def process_cdc_event(event: dict):
    op = event.get("__op")

    if op == "c":   # Insert
        upsert_to_dwh(event)
    elif op == "u": # Update
        upsert_to_dwh(event)
    elif op == "d": # Delete
        if SOFT_DELETE:
            mark_deleted_in_dwh(event["order_id"])
        else:
            hard_delete_from_dwh(event["order_id"])
    elif op == "r": # Snapshot (initial load)
        upsert_to_dwh(event)
```

## Initial Snapshot Strategy

When Debezium first connects, it snapshots the entire table before switching to log-based capture:

1. **Default snapshot**: Acquires a table-level read lock; safe but blocks writes briefly
2. **`initial_only`**: Snapshot then stop — useful for one-time data migration
3. **`never`**: Skip snapshot — only capture changes going forward (risk: missing initial state)
4. **`exported`**: Uses exported transaction ID — no locking but requires specific DB support

### Custom Initial Load (Zero Downtime)
```python
# 1. Start Debezium with snapshot=never and record current LSN
lsn_at_cdc_start = get_current_pg_lsn()

# 2. Run parallel bulk export from source
bulk_export_to_target_table(limit_lsn=lsn_at_cdc_start)

# 3. Apply CDC events with LSN > lsn_at_cdc_start
# Debezium will filter events from before the slot was created
```

## Applying CDC to Data Warehouse

### Stream-to-DWH Pattern (Flink → Delta Lake)
```python
from pyspark.sql.functions import from_json, col, when

cdc_stream = (spark.readStream
    .format("kafka")
    .option("subscribe", "postgres.public.orders")
    .load()
    .select(from_json(col("value").cast("string"), cdc_schema).alias("cdc"))
    .select("cdc.*"))

def upsert_to_delta(batch_df, batch_id):
    from delta.tables import DeltaTable

    delta_table = DeltaTable.forPath(spark, "s3://data-lake/cleansed/orders")

    # Split deletes and upserts
    upserts = batch_df.filter(col("__deleted") == False)
    deletes = batch_df.filter(col("__deleted") == True)

    # Merge upserts
    delta_table.alias("t").merge(
        upserts.alias("s"), "t.order_id = s.order_id"
    ).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

    # Handle deletes (soft delete approach)
    delta_table.alias("t").merge(
        deletes.alias("s"), "t.order_id = s.order_id"
    ).whenMatchedUpdate(set={"is_deleted": "true", "deleted_at": "current_timestamp()"}).execute()

cdc_stream.writeStream \
    .foreachBatch(upsert_to_delta) \
    .option("checkpointLocation", "s3://checkpoints/orders-cdc") \
    .start()
```

## Operational Considerations

### Replication Slot Lag
- Monitor `pg_replication_slots.confirmed_flush_lsn` vs current WAL position
- High lag means Debezium isn't consuming fast enough — scale consumers or increase connector tasks
- Stale replication slot (connector crashed) blocks WAL cleanup — can fill disk
- Alert: replication lag > 10GB or slot is inactive for > 30 minutes

```sql
SELECT slot_name,
       pg_size_pretty(pg_wal_lsn_diff(pg_current_wal_lsn(), restart_lsn)) AS replication_lag,
       active,
       confirmed_flush_lsn
FROM pg_replication_slots;
```

### At-Least-Once Delivery and Idempotency
- CDC guarantees at-least-once delivery — consumers must be idempotent
- Use `MERGE` (upsert) not `INSERT` at the destination
- Track LSN or transaction ID to detect and skip duplicates

### Schema Changes (DDL)
- Debezium handles schema changes automatically for tables being captured
- Schema history stored in Kafka topic (`database.history.kafka.topic`)
- Consumers using Schema Registry receive updated schema versions automatically

## Monitoring Checklist

- [ ] Replication slot lag < configured threshold (e.g., 1 GB)
- [ ] Connector status = `RUNNING` (not `FAILED` or `PAUSED`)
- [ ] Consumer lag on CDC topic < 10,000 messages
- [ ] Event type distribution: watch for unusual spike in deletes (may indicate bug)
- [ ] Snapshot status: track snapshot progress for large tables
- [ ] DLQ (dead letter queue): monitor for events failing consumer processing
