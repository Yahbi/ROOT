---
name: ETL Pipeline Design
description: Design, build, and operate Extract-Transform-Load pipelines for reliable data movement
category: data-engineering
difficulty: intermediate
version: "1.0.0"
author: ROOT
tags: [data-engineering, etl, pipeline, data-integration, airflow, spark]
platforms: [all]
---

# ETL Pipeline Design

Build robust, scalable, and maintainable pipelines that move and transform data reliably across systems.

## Core ETL Concepts

### Extract Phase
- **Full extraction**: Read entire source dataset — simple but expensive; use for small tables or initial loads
- **Incremental extraction**: Pull only new/changed records using watermark columns (`updated_at`, sequence IDs, CDC logs)
- **Delta extraction**: Compare source and destination checksums or row hashes for change detection
- Source types: RDBMS, REST APIs, file systems (S3, GCS, SFTP), message queues, SaaS platforms

### Transform Phase
- **Cleaning**: Null handling, deduplication, type coercion, encoding normalization (UTF-8)
- **Standardization**: Date formats (ISO 8601), phone/address normalization, currency unification
- **Enrichment**: Joining reference data, geocoding addresses, currency conversion, classification tagging
- **Aggregation**: Pre-compute metrics (daily totals, rolling averages) for downstream query performance
- **Validation**: Schema enforcement, referential integrity checks, business rule assertions

### Load Phase
- **Full load**: Truncate-and-insert — simple, deterministic, costly for large tables
- **Incremental load**: INSERT only new rows using unique keys; risk of duplicates without upsert
- **Upsert (Merge)**: INSERT on new key, UPDATE on existing — gold standard for most pipelines
- **Append-only**: For event streams where history matters; partition by date for query efficiency

## Pipeline Architecture Patterns

### Lambda Architecture
```
Raw Events ──┬── Speed Layer (stream) ──► Serving Layer
             └── Batch Layer (Spark)  ──► Serving Layer
```
- Speed layer provides low-latency approximate results
- Batch layer periodically reconciles for accuracy
- Complexity: two codepaths to maintain; prefer Kappa when stream-only is feasible

### Kappa Architecture
```
Raw Events ── Stream Processor (Flink/Kafka Streams) ── Serving Layer
```
- Single codebase handles both real-time and historical reprocessing
- Reprocess by replaying from Kafka topic beginning
- Simpler to operate; requires a replayable log (Kafka with sufficient retention)

### Medallion Architecture (Delta Lake / Databricks)
| Layer | Alias | Contents |
|-------|-------|----------|
| Bronze | Raw | Unmodified source data, landed as-is |
| Silver | Cleansed | Deduplicated, typed, validated |
| Gold | Aggregated | Business-ready aggregates, metrics, dimensions |

## Orchestration with Apache Airflow

### DAG Design Principles
```python
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

default_args = {
    "owner": "data-engineering",
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "email_on_failure": True,
}

with DAG(
    dag_id="orders_etl",
    schedule_interval="0 3 * * *",   # 3 AM daily
    start_date=datetime(2024, 1, 1),
    catchup=False,                    # Avoid backfill surprise
    max_active_runs=1,                # Prevent concurrent executions
    default_args=default_args,
) as dag:
    extract = PythonOperator(task_id="extract", python_callable=extract_orders)
    transform = PythonOperator(task_id="transform", python_callable=transform_orders)
    load = PythonOperator(task_id="load", python_callable=load_orders)
    extract >> transform >> load
```

### Idempotency Requirements
- Every pipeline run with the same inputs must produce identical outputs
- Use logical date as partition key, not `datetime.now()`
- Clear target partition before writing: delete `WHERE date = {{ ds }}`
- Store run metadata (rows processed, hash of source) for reconciliation

## Data Quality Checks

### In-Pipeline Assertions
```python
def validate_transform(df):
    assert df["user_id"].notna().all(), "Null user_ids found"
    assert (df["amount"] >= 0).all(), "Negative amounts found"
    assert df["order_date"].between("2020-01-01", "2030-12-31").all(), "Dates out of range"
    assert df.duplicated("order_id").sum() == 0, "Duplicate order_ids"
    return df
```

### Row Count Reconciliation
- Source count vs target count (allow 0% variance for deterministic pipelines)
- For incremental: compare today's extracted row count to 7-day average ± 2 standard deviations
- Alert on anomalies rather than failing — sometimes source data is genuinely sparse

## Performance Optimization

| Technique | When to Use | Impact |
|-----------|------------|--------|
| Partition pruning | Date-range queries on large tables | 10-100x read speedup |
| Columnar storage (Parquet) | Analytical workloads | 3-10x compression + faster reads |
| Broadcast joins | One table < 1 GB | Eliminates shuffle in Spark |
| Incremental over full | Source > 1M rows | Linear vs constant time |
| Parallelism tuning | Spark shuffle partitions | Match to cluster core count |

## Error Handling & Recovery

- **Dead letter queue**: Failed records written to separate table for investigation
- **Partial failure handling**: Process in chunks; commit successfully transformed chunks
- **Checkpoint resumption**: Save last successful watermark — restart from checkpoint, not zero
- **Retry with backoff**: Transient network errors should retry; schema errors should alert immediately

## Monitoring Checklist

- [ ] Pipeline duration tracked and alerted if > 2x median
- [ ] Row count reconciliation with source
- [ ] Data freshness check: last successful run timestamp < SLA threshold
- [ ] Failed DAG runs trigger PagerDuty/Slack alert
- [ ] Cost tracking: compute cost per pipeline run
