---
name: Data Lake Architecture
description: Design and implement multi-zone data lake architectures with Delta Lake, Iceberg, and cloud storage
version: "1.0.0"
author: ROOT
tags: [data-engineering, data-lake, Delta-Lake, Iceberg, S3, architecture]
platforms: [all]
difficulty: advanced
---

# Data Lake Architecture

Design a layered data lake that balances raw data preservation with analytical
performance through medallion architecture and open table formats.

## Medallion Architecture (Bronze/Silver/Gold)

```
Raw Data Sources → Bronze (Raw) → Silver (Cleaned) → Gold (Business-Ready)
                   (append only)   (deduplicated)     (aggregated, modeled)
                   S3/GCS          Delta/Iceberg       Delta/Iceberg
```

### Bronze Layer (Raw)
- **Purpose**: Immutable copy of source data as received
- **Format**: Raw files (JSON, CSV, Parquet) or Delta Lake append-only
- **Retention**: 7-10 years (regulatory compliance, debugging)
- **Transformations**: None — only add ingestion metadata
- **Access**: Restricted to data engineers and pipeline processes

### Silver Layer (Cleaned/Deduplicated)
- **Purpose**: Clean, deduplicated, schema-enforced data
- **Format**: Delta Lake or Apache Iceberg
- **Transformations**: Type casting, deduplication, null handling, PII masking
- **Retention**: 3-7 years
- **Access**: Data engineers and data scientists

### Gold Layer (Business-Ready)
- **Purpose**: Aggregated, business-logic applied, ready for consumption
- **Format**: Delta Lake with Z-ordering for query performance
- **Transformations**: Joins, aggregations, derived metrics, SCD handling
- **Retention**: 1-3 years (usually rebuilt from silver)
- **Access**: All teams including BI and business users

## Delta Lake Implementation

```python
from delta import DeltaTable
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .appName("DataLake") \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

# Bronze: Append raw events
def ingest_to_bronze(raw_df, table_path: str):
    raw_df \
        .withColumn("_ingestion_timestamp", current_timestamp()) \
        .withColumn("_source", lit("orders_api")) \
        .write \
        .format("delta") \
        .mode("append") \
        .partitionBy("year", "month", "day") \
        .save(table_path)

# Silver: Merge (upsert) cleaned data
def update_silver(clean_df, silver_path: str, merge_key: str):
    if DeltaTable.isDeltaTable(spark, silver_path):
        silver = DeltaTable.forPath(spark, silver_path)
        silver.alias("silver").merge(
            clean_df.alias("updates"),
            f"silver.{merge_key} = updates.{merge_key}"
        ).whenMatchedUpdateAll() \
         .whenNotMatchedInsertAll() \
         .execute()
    else:
        clean_df.write.format("delta").mode("overwrite").save(silver_path)

# Gold: Aggregated metrics table
def build_gold_table(silver_path: str, gold_path: str):
    silver_df = spark.read.format("delta").load(silver_path)
    gold_df = silver_df \
        .groupBy("customer_id", "date_trunc('month', created_at)") \
        .agg(
            count("order_id").alias("monthly_orders"),
            sum("total_amount").alias("monthly_revenue"),
            avg("total_amount").alias("avg_order_value")
        )
    gold_df.write.format("delta").mode("overwrite").save(gold_path)
```

## Apache Iceberg (Alternative to Delta Lake)

```python
# Iceberg — better for multi-engine compatibility (Spark + Flink + Trino)
spark.sql("""
    CREATE TABLE catalog.db.orders (
        order_id STRING,
        customer_id STRING,
        total_amount DOUBLE,
        created_at TIMESTAMP
    ) USING iceberg
    PARTITIONED BY (days(created_at))
    TBLPROPERTIES (
        'write.target-file-size-bytes' = '134217728',  -- 128MB target file size
        'write.distribution-mode' = 'hash',
        'history.expire.max-snapshot-age-ms' = '604800000'  -- 7-day snapshot retention
    )
""")

# Time travel query
spark.read \
    .format("iceberg") \
    .option("as-of-timestamp", "2026-01-01T00:00:00") \
    .load("catalog.db.orders")

# Schema evolution (additive changes are backward compatible)
spark.sql("ALTER TABLE catalog.db.orders ADD COLUMN promo_code STRING")
```

## Partitioning Strategy

```python
# Partition selection based on query patterns
PARTITIONING_GUIDE = {
    "time-series data": "PARTITION BY (year, month, day) or PARTITION BY days(timestamp)",
    "customer data": "PARTITION BY (region) — limit cardinality to < 10k partitions",
    "product catalog": "PARTITION BY (category) — low cardinality, high filter reuse",
    "event logs": "PARTITION BY (event_type, date) — double partition for common queries"
}

# Anti-patterns to avoid:
PARTITION_ANTIPATTERNS = [
    "Partition by high-cardinality column (e.g., user_id) → millions of small files",
    "Partition by frequently updated column → constant partition scans",
    "No partition at all on large tables → full table scans",
    "Too many partition columns → partition pruning becomes complex"
]
```

## File Size Optimization

```python
# Compact small files (the small file problem kills query performance)
def compact_delta_table(table_path: str, target_file_size_mb: int = 128):
    delta_table = DeltaTable.forPath(spark, table_path)
    delta_table.optimize().executeCompaction()

    # Z-Order for co-locating related data on disk
    delta_table.optimize().executeZOrderBy("customer_id", "created_at")

# Schedule compaction:
# - Run after every 10 streaming micro-batches
# - Or daily during low-traffic periods
```

## Data Lake Governance

### Access Control
```python
# S3 bucket policy — zone-based access control
BUCKET_POLICIES = {
    "s3://datalake-bronze/": {
        "read": ["data-engineering", "data-pipelines"],
        "write": ["data-pipelines"]
    },
    "s3://datalake-silver/": {
        "read": ["data-engineering", "data-science", "analytics"],
        "write": ["data-engineering"]
    },
    "s3://datalake-gold/": {
        "read": ["all-teams"],
        "write": ["data-engineering", "analytics"]
    }
}
```

### Data Catalog
```python
# Register tables in Glue/Hive Metastore for discovery
import boto3

glue = boto3.client("glue")

def register_table_in_catalog(table_name: str, s3_path: str, schema: list):
    glue.create_table(
        DatabaseName="datalake_gold",
        TableInput={
            "Name": table_name,
            "Description": "Gold layer - daily customer metrics",
            "StorageDescriptor": {
                "Location": s3_path,
                "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
                "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
                "Columns": schema,
            },
            "Parameters": {"classification": "parquet", "delta_table": "true"}
        }
    )
```

## Cost Optimization

| Strategy | Implementation | Savings |
|----------|---------------|---------|
| S3 storage tiers | Move bronze > 30 days to S3-IA | 40-50% storage cost |
| Parquet compression | Use ZSTD or Snappy | 60-80% vs. CSV |
| Partition pruning | Always filter on partition columns | 80-99% less data scanned |
| File compaction | Merge small files into 128MB targets | 10-50x query speedup |
| Caching | Cache gold layer in memory for BI tools | 5-20x query speedup |
