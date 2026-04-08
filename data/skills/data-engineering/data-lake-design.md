---
name: Data Lake Design
description: Architecture, storage layout, access control, and governance for scalable data lakes
category: data-engineering
difficulty: advanced
version: "1.0.0"
author: ROOT
tags: [data-engineering, data-lake, s3, delta-lake, iceberg, storage, cloud]
platforms: [aws, gcp, azure]
---

# Data Lake Design

Build a scalable, governed, and queryable data lake that serves as the single source of truth for all raw and processed data.

## Data Lake vs Data Warehouse vs Lakehouse

| Aspect | Data Lake | Data Warehouse | Lakehouse |
|--------|-----------|---------------|-----------|
| Storage | Object store (S3, GCS, ADLS) | Proprietary (Redshift, Snowflake) | Object store + open table format |
| Schema | Schema-on-read | Schema-on-write | Both — enforced via table format |
| Cost | Very low | High | Low-medium |
| Query speed | Slow (no index) | Fast | Fast (with indexing) |
| Data types | Structured, semi, unstructured | Structured only | Structured + semi |
| Best for | Raw data storage, ML training | BI analytics | Modern unified platform |

## Storage Layer Architecture

### Zone Structure (Medallion)
```
s3://company-data-lake/
├── raw/                          # Bronze: exact copy of source, never modified
│   ├── source=postgres/
│   │   └── table=orders/
│   │       └── date=2024-01-15/
│   │           └── orders_20240115_143022.parquet
│   └── source=kafka/
│       └── topic=events/
│           └── year=2024/month=01/day=15/hour=14/
├── cleansed/                     # Silver: typed, deduplicated, validated
│   └── orders/
│       └── date=2024-01-15/
├── curated/                      # Gold: business-ready aggregates
│   └── revenue_by_day/
│       └── date=2024-01-15/
└── sandbox/                      # Analyst exploration, TTL 30 days
    └── analyst=john/
```

### File Format Selection
| Format | Use Case | Compression | Schema Evolution |
|--------|----------|-------------|-----------------|
| Parquet | Analytics (columnar reads) | Excellent (snappy) | Limited |
| ORC | Hive-centric workloads | Excellent (zlib) | Limited |
| Delta Lake | ACID transactions, time travel | Good | Full |
| Apache Iceberg | Multi-engine ACID, partition evolution | Good | Full |
| JSON/CSV | Raw ingestion, debugging | Poor | N/A |

## Open Table Formats

### Apache Iceberg
```python
from pyiceberg.catalog import load_catalog

catalog = load_catalog("glue", **{"type": "glue", "warehouse": "s3://data-lake/"})

# Create table with schema
from pyiceberg.schema import Schema
from pyiceberg.types import NestedField, StringType, LongType, TimestampType

schema = Schema(
    NestedField(1, "order_id", StringType(), required=True),
    NestedField(2, "user_id", LongType(), required=True),
    NestedField(3, "amount", LongType()),
    NestedField(4, "created_at", TimestampType()),
)

catalog.create_table("warehouse.orders", schema=schema,
                     partition_spec=PartitionSpec(PartitionField(4, 1001, DayTransform())))

# Time travel query
table = catalog.load_table("warehouse.orders")
snapshot = table.snapshot_by_timestamp(as_of_datetime=datetime(2024, 1, 1))
df = table.scan(snapshot_id=snapshot.snapshot_id).to_pandas()
```

### Delta Lake
```python
from delta.tables import DeltaTable
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .getOrCreate()

# Write with ACID guarantees
df.write.format("delta").mode("overwrite").save("s3://data-lake/cleansed/orders")

# Upsert (Merge)
delta_table = DeltaTable.forPath(spark, "s3://data-lake/cleansed/orders")
delta_table.alias("target").merge(
    updates.alias("source"),
    "target.order_id = source.order_id"
).whenMatchedUpdateAll().whenNotMatchedInsertAll().execute()

# Time travel
df_yesterday = spark.read.format("delta") \
    .option("timestampAsOf", "2024-01-14") \
    .load("s3://data-lake/cleansed/orders")

# Optimize (compaction + Z-order)
delta_table.optimize().zOrderBy("user_id", "created_at")
```

## Partitioning Strategy

### Partition Key Selection
- **High-cardinality keys** (user_id with 10M users): bad — creates too many small files
- **Time-based** (year/month/day): good for time-range queries; standard for most datasets
- **Categorical** (country, product_category with < 1000 values): good for filter-heavy workloads
- Avoid over-partitioning: target 100MB–1GB per partition file

### Small File Problem
- Caused by streaming ingestion or too-granular partitioning
- Solution: scheduled compaction job that rewrites small files into larger ones
- Delta Lake: `OPTIMIZE table` — merges files to target 1GB
- Iceberg: `rewrite_data_files` procedure

## Access Control & Security

### IAM Policy Design
```json
{
  "Effect": "Allow",
  "Action": ["s3:GetObject", "s3:ListBucket"],
  "Resource": [
    "arn:aws:s3:::data-lake/curated/*",
    "arn:aws:s3:::data-lake"
  ],
  "Condition": {
    "StringEquals": {"s3:prefix": ["curated/"]}
  }
}
```

### Lake Formation (AWS)
- Fine-grained column-level and row-level access control
- Grant permissions to IAM roles or users per database/table/column
- Data filters: row-level security by department or region

### Data Classification
| Classification | Zone | Access | Encryption |
|----------------|------|--------|-----------|
| Public | Curated | All authenticated users | AES-256 at rest |
| Internal | Cleansed | Data team + analysts | AES-256 + TLS |
| Confidential (PII) | Raw | Data engineering only | KMS customer-managed key |
| Restricted (financial) | Raw | Finance + Data Eng | KMS + CloudHSM |

## Data Catalog Integration

- Register all tables in AWS Glue Catalog / Apache Atlas / DataHub
- Auto-crawl new partitions on arrival using Glue Crawlers or custom registration
- Each table entry includes: schema, owner, data classification, update frequency, quality score
- Tag PII columns: `{ "tag": "PII", "type": "email" }` — enables automated masking

## Cost Optimization

| Technique | Savings | Trade-off |
|-----------|---------|-----------|
| Lifecycle policies (S3 IA → Glacier) | 60-80% on old raw data | Higher retrieval cost |
| Intelligent tiering | Automatic, 5-40% | Small monitoring fee |
| Columnar format (Parquet) vs CSV | 5-10x storage reduction | Processing required |
| Compaction (eliminate small files) | Reduces S3 API calls | Compute for compaction job |
| Delete unnecessary sandbox files | 100% for unused data | Policy enforcement needed |

## Monitoring & Governance

- **Storage growth**: Alert if daily growth exceeds 3x the 30-day average
- **Query performance**: P95 scan latency per table, track regression after ingestion
- **Data freshness**: Trigger alert if table's `max(ingestion_time)` exceeds SLA threshold
- **Cost attribution**: Tag all S3 resources by team; enable S3 Storage Lens
- **Orphan files**: Detect S3 files not registered in catalog — may be leftover from failed jobs
