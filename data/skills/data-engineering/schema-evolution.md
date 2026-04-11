---
name: Schema Evolution
description: Manage backward and forward compatible schema changes in databases, APIs, and data pipelines
category: data-engineering
difficulty: intermediate
version: "1.0.0"
author: ROOT
tags: [data-engineering, schema-evolution, backward-compatibility, avro, protobuf, migrations, api-versioning]
platforms: [all]
---

# Schema Evolution

Safely change data structures over time without breaking upstream producers or downstream consumers.

## Compatibility Models

| Type | Definition | Example Safe Change |
|------|-----------|-------------------|
| **Backward compatible** | New schema can read old data | Add optional field with default |
| **Forward compatible** | Old schema can read new data | Remove optional field |
| **Full compatible** | Both directions safe | Rename field with alias |
| **Breaking** | Neither direction safe | Change field type, remove required field |

## Safe vs Breaking Changes

### Safe (Non-Breaking) Changes
- Add an optional field with a default value
- Add a new enum value (with caution in forward compat scenarios)
- Add a new table or column (SQL)
- Expand a varchar length (e.g., VARCHAR(100) → VARCHAR(500))
- Add a nullable column (SQL)

### Breaking Changes
- Remove a field that consumers depend on
- Rename a field without providing an alias
- Change a field's data type (e.g., INT → STRING)
- Change a field from optional to required
- Reduce varchar length (SQL) — may truncate existing data
- Remove an enum value

## Avro Schema Evolution

### Schema with Defaults
```json
{
  "type": "record",
  "name": "Order",
  "fields": [
    {"name": "order_id", "type": "string"},
    {"name": "amount",   "type": "double"},
    {"name": "currency", "type": "string", "default": "USD"},
    {"name": "status",   "type": "string", "default": "pending"}
  ]
}
```

### Adding a Field (Backward Compatible)
```json
// v2: add optional region field with default
{"name": "region", "type": ["null", "string"], "default": null}
```
- Old consumers reading v2 data: ignore unknown field
- New consumers reading v1 data: use default value (`null`)

### Using Schema Registry (Confluent)
```python
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroSerializer

registry = SchemaRegistryClient({"url": "http://schema-registry:8081"})

# Register schema — will fail if not compatible with configured compatibility level
registry.register_schema("orders-value", Schema(order_schema_v2_json, "AVRO"))

# Set compatibility level per subject
registry.update_compatibility("BACKWARD", "orders-value")
```

### Compatibility Levels in Schema Registry
| Level | Who Can Read What |
|-------|------------------|
| `NONE` | No compatibility enforced |
| `BACKWARD` | New schema reads data written by old schema |
| `FORWARD` | Old schema reads data written by new schema |
| `FULL` | Both directions |
| `BACKWARD_TRANSITIVE` | New schema reads data written by ALL previous versions |

## Protocol Buffers (Protobuf) Evolution

### Safe Protobuf Practices
```proto
// v1
message Order {
  string order_id = 1;
  double amount   = 2;
  string status   = 3;
}

// v2 — SAFE: add new optional field with new field number
message Order {
  string order_id = 1;
  double amount   = 2;
  string status   = 3;
  string region   = 4;     // New field — old parsers ignore it
}
```

### Protobuf Rules
- Never reuse field numbers — they identify fields in wire format, not names
- Use `reserved` for removed fields/numbers to prevent accidental reuse
- Never change field types — binary wire format will be corrupted

```proto
message Order {
  reserved 5, 6;              // Field numbers 5 and 6 are retired
  reserved "old_field_name";  // Field name is retired
  string order_id = 1;
  double amount   = 2;
}
```

## SQL Database Migrations

### Migration Strategy
```sql
-- Pattern: additive first, then remove in future version
-- Phase 1: Add new column (non-breaking)
ALTER TABLE orders ADD COLUMN currency VARCHAR(3) DEFAULT 'USD';

-- Phase 2: Backfill (run during low-traffic window)
UPDATE orders SET currency = 'USD' WHERE currency IS NULL;

-- Phase 3: Add NOT NULL constraint (after confirming no nulls)
ALTER TABLE orders ALTER COLUMN currency SET NOT NULL;

-- Phase 4 (future release): Remove old column after verifying no consumers
ALTER TABLE orders DROP COLUMN old_currency_field;
```

### Zero-Downtime Column Rename
```sql
-- Step 1: Add new column with desired name
ALTER TABLE users ADD COLUMN full_name VARCHAR(200);

-- Step 2: Backfill from old column
UPDATE users SET full_name = name WHERE full_name IS NULL;

-- Step 3: Dual-write in application (write to both columns)
-- Step 4: Migrate all reads to new column name
-- Step 5: Drop old column (separate deployment)
ALTER TABLE users DROP COLUMN name;
```

### Migration Tools

| Tool | Language | Features |
|------|---------|---------|
| Alembic | Python | SQLAlchemy-native, auto-generation |
| Flyway | JVM/CLI | Version-based, widely adopted |
| Liquibase | JVM | XML/YAML/JSON format, rollback support |
| Golang Migrate | Go | Multi-DB, simple CLI |
| dbt | SQL | `run_query` hooks for DDL |

## dbt Schema Change Handling

### on_schema_change Strategies
```sql
{{ config(
    materialized='incremental',
    on_schema_change='sync_all_columns'   -- Options: ignore, fail, append_new_columns, sync_all_columns
) }}
```

| Strategy | Behavior |
|----------|---------|
| `ignore` | No action — new columns in source won't appear in target |
| `fail` | Pipeline fails on schema mismatch — safest for critical tables |
| `append_new_columns` | Adds new columns, doesn't remove deleted ones |
| `sync_all_columns` | Adds new + removes deleted — most aggressive |

## API Schema Versioning

### URL Versioning
```
GET /api/v1/orders    # v1 schema
GET /api/v2/orders    # v2 schema (new fields, changed structure)
```

### Header Versioning
```http
GET /api/orders
Accept: application/vnd.api+json; version=2
```

### Deprecation Process
1. Announce deprecation date (minimum 6 months notice)
2. Add `Deprecation` and `Sunset` headers to old API responses
3. Monitor usage of old version; reach out to high-volume consumers
4. Sunset: return 410 Gone after sunset date

## Monitoring Schema Changes

- **Schema drift detection**: Compare current table schema to expected schema in catalog; alert on unexpected changes
- **Consumer compatibility check**: Before deploying new schema, validate all registered consumers can handle it
- **Column usage tracking**: Track which columns are actually queried — safe to deprecate unused ones
- **Migration duration tracking**: Alert if migration exceeds estimated duration (risk of table lock)

## Evolution Checklist

Before any schema change:
- [ ] Classify change as backward/forward/breaking
- [ ] Identify all producers and consumers of this schema
- [ ] Verify compatibility with Schema Registry (event schemas) or test suite (APIs)
- [ ] Write migration and rollback script
- [ ] Plan deployment order (usually: add field → deploy readers → deploy writers → verify → remove old field)
- [ ] Schedule maintenance window for breaking changes
- [ ] Update data catalog with new schema version
