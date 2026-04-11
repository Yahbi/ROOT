---
name: Batch Processing
description: Design and optimize large-scale batch data processing jobs with Spark, dbt, and SQL engines
category: data-engineering
difficulty: intermediate
version: "1.0.0"
author: ROOT
tags: [data-engineering, batch-processing, spark, dbt, sql, big-data, distributed-computing]
platforms: [all]
---

# Batch Processing

Build efficient, reliable batch jobs that process large volumes of data on schedule with predictable performance.

## When to Use Batch vs Streaming

| Criteria | Batch | Streaming |
|----------|-------|-----------|
| Latency requirement | Minutes to hours acceptable | Seconds or less required |
| Data volume | High — GBs to TBs per run | Continuous, lower per-event volume |
| Complexity | Complex joins, aggregations | Simple per-event logic |
| Cost | Lower (process once) | Higher (always-on infrastructure) |
| Correctness | Easier (bounded dataset) | Harder (ordering, late data) |

## Apache Spark Batch Processing

### Core Concepts
- **RDD (Resilient Distributed Dataset)**: Low-level, avoid unless necessary
- **DataFrame**: Columnar, optimized via Catalyst; use this always
- **Dataset**: Typed DataFrame (Scala/Java only); type-safe but verbose
- **Partition**: Unit of parallelism — each executor processes one partition at a time

### Spark Job Anatomy
```python
from pyspark.sql import SparkSession
from pyspark.sql import functions as F

spark = SparkSession.builder \
    .appName("DailyRevenueCalculation") \
    .config("spark.sql.shuffle.partitions", "200")  \   # Match cluster cores
    .config("spark.sql.adaptive.enabled", "true") \     # Enable AQE
    .getOrCreate()

# Read
orders = spark.read.parquet("s3://data-lake/cleansed/orders/date=2024-01-15")
products = spark.read.parquet("s3://data-lake/curated/dim_product")

# Transform
revenue = (
    orders
    .filter(F.col("status") == "paid")
    .join(F.broadcast(products), "product_id")       # Broadcast small table
    .groupBy("category", "region")
    .agg(
        F.sum("amount").alias("gross_revenue"),
        F.countDistinct("order_id").alias("order_count"),
        F.avg("amount").alias("avg_order_value"),
    )
    .withColumn("revenue_per_order", F.col("gross_revenue") / F.col("order_count"))
)

# Write
(revenue.write
    .mode("overwrite")
    .partitionBy("region")
    .parquet("s3://data-lake/curated/revenue_by_category/date=2024-01-15"))
```

### Performance Tuning

#### Shuffle Tuning
```python
# Rule of thumb: ~128MB per partition after shuffle
# If output is 25.6 GB: 25600 / 128 = 200 partitions
spark.conf.set("spark.sql.shuffle.partitions", "200")

# Adaptive Query Execution (Spark 3.x): automatically coalesces partitions
spark.conf.set("spark.sql.adaptive.enabled", "true")
spark.conf.set("spark.sql.adaptive.coalescePartitions.enabled", "true")
```

#### Join Optimization
```python
# Broadcast join: broadcast table < 10MB (auto) or < spark.sql.autoBroadcastJoinThreshold
small_df = spark.read.parquet("s3://data-lake/curated/country_codes")   # 1MB
result = large_df.join(F.broadcast(small_df), "country_code")

# Salting for skewed joins
from pyspark.sql.functions import rand, floor
large_skewed = large_skewed.withColumn("salt", (floor(rand() * 10)).cast("string"))
large_skewed = large_skewed.withColumn("salted_key", F.concat("key", F.lit("_"), "salt"))
```

#### Caching Strategy
```python
# Cache when DataFrame is reused multiple times
dimension_tables = spark.read.parquet("s3://data-lake/curated/dim_product")
dimension_tables.cache()
dimension_tables.count()   # Force materialization before loop

# Use MEMORY_AND_DISK for large DataFrames (avoids OOM)
from pyspark import StorageLevel
large_df.persist(StorageLevel.MEMORY_AND_DISK)
```

### Reading Data Efficiently
```python
# Predicate pushdown: filter at read time
orders = spark.read.parquet("s3://data-lake/cleansed/orders") \
    .filter("date = '2024-01-15' AND status = 'paid'")   # Pushed to Parquet reader

# Partition pruning: specify partition in path
orders_today = spark.read.parquet("s3://data-lake/cleansed/orders/date=2024-01-15")

# Select only needed columns
slim_orders = orders.select("order_id", "user_id", "amount", "product_id")
```

## dbt Batch Modeling

### Incremental Model
```sql
-- models/marts/fct_daily_revenue.sql
{{ config(
    materialized='incremental',
    unique_key='date_key || "_" || category',
    incremental_strategy='merge',
    on_schema_change='sync_all_columns'
) }}

SELECT
    TO_CHAR(order_date, 'YYYYMMDD') AS date_key,
    category,
    SUM(amount) AS gross_revenue,
    COUNT(DISTINCT order_id) AS order_count
FROM {{ ref('stg_orders') }}
{% if is_incremental() %}
WHERE order_date >= (SELECT MAX(order_date) FROM {{ this }}) - INTERVAL '3 days'
{% endif %}
GROUP BY 1, 2
```

### Model Optimization Tips
- Use `incremental` materialization for large tables that grow over time
- Use `table` for dimension tables that are fully refreshed
- Use `view` for staging layers — avoid storing duplicate data
- `partition_by` + `cluster_by` in BigQuery for large mart tables

## SQL Engine Optimization (BigQuery, Snowflake, Redshift)

### BigQuery
```sql
-- Partition by date for time-range queries
CREATE TABLE orders PARTITION BY DATE(created_at)
CLUSTER BY user_id, status;

-- Use approximate functions for large datasets
SELECT APPROX_COUNT_DISTINCT(user_id) FROM orders;   -- 1-2% error, 100x faster
SELECT APPROX_TOP_COUNT(product_id, 10) FROM orders;  -- Top 10 by count, approximate
```

### Snowflake
```sql
-- Virtual warehouses: suspend when idle to save cost
ALTER WAREHOUSE batch_wh SET AUTO_SUSPEND = 60;

-- Clustering for skewed partitions
ALTER TABLE orders CLUSTER BY (DATE_TRUNC('DAY', created_at), status);

-- Result caching: identical queries within 24h return cached results for free
```

## Job Scheduling & Orchestration

### Airflow Batch DAG Pattern
```python
with DAG("daily_revenue", schedule_interval="0 4 * * *", catchup=False) as dag:

    wait_for_source = ExternalTaskSensor(
        task_id="wait_for_orders_etl",
        external_dag_id="orders_etl",
        external_task_id="load",
        timeout=3600,
    )

    run_spark = SparkSubmitOperator(
        task_id="compute_revenue",
        application="jobs/daily_revenue.py",
        conf={"spark.executor.instances": "10"},
    )

    run_dbt = BashOperator(
        task_id="dbt_marts",
        bash_command="dbt run --models tag:daily --profiles-dir /etc/dbt",
    )

    validate = PythonOperator(task_id="validate", python_callable=run_dq_checks)

    wait_for_source >> run_spark >> run_dbt >> validate
```

## Common Anti-Patterns

| Anti-Pattern | Problem | Fix |
|-------------|---------|-----|
| `collect()` on large DataFrame | OOM on driver | Use distributed write, never collect |
| `UDF` for simple operations | 10-100x slower than native functions | Use `pyspark.sql.functions` |
| Processing full history daily | Linear cost growth | Incremental with watermark |
| No schema enforcement | Silent data corruption | Define and validate schema at read |
| Single giant SQL query | Hard to debug/optimize | Break into stages, materialize intermediates |

## Monitoring Batch Jobs

- Track: job duration, rows read/written, cost per run, failure count
- Alert on: job exceeding 2x median duration, row count anomalies, cost spikes
- Store job metadata: `(job_id, dag_id, run_date, start, end, status, rows, cost)`
- Retain logs for 30 days minimum for debugging failed runs
