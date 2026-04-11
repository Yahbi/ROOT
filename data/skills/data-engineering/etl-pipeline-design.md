---
name: ETL Pipeline Design
description: Design reliable, scalable Extract-Transform-Load pipelines for data warehouse ingestion
version: "1.0.0"
author: ROOT
tags: [data-engineering, ETL, pipeline, data-warehouse, dbt, airflow]
platforms: [all]
difficulty: intermediate
---

# ETL Pipeline Design

Build reliable data pipelines that move data from source systems to analytical
destinations with proper error handling, monitoring, and lineage tracking.

## ETL vs. ELT

```
ETL (Traditional):  Extract → Transform → Load
  - Transform before loading
  - Good for: limited destination compute, sensitive data masking in transit

ELT (Modern):       Extract → Load → Transform
  - Load raw data first, transform in warehouse
  - Preferred for cloud data warehouses (BigQuery, Snowflake), dbt workflows
```

## Extract Layer

```python
from typing import Iterator
import pandas as pd

class DataExtractor:
    def extract_from_postgres(self, connection_string: str, query: str,
                               chunk_size: int = 10000) -> Iterator[pd.DataFrame]:
        """Extract data in chunks to handle large datasets."""
        engine = create_engine(connection_string)
        for chunk in pd.read_sql(query, engine, chunksize=chunk_size):
            yield chunk

    def extract_from_api(self, base_url: str, endpoint: str,
                          date_from: str, date_to: str) -> list:
        """Extract from REST API with pagination handling."""
        records = []
        page = 1
        while True:
            response = requests.get(
                f"{base_url}/{endpoint}",
                params={"from": date_from, "to": date_to, "page": page, "limit": 100},
                headers={"Authorization": f"Bearer {API_KEY}"}
            )
            data = response.json()
            records.extend(data["items"])
            if not data.get("has_more"):
                break
            page += 1
        return records
```

## Transform Layer

```python
class DataTransformer:
    def clean_and_validate(self, df: pd.DataFrame, schema: dict) -> tuple:
        """Clean data and validate against schema."""
        issues = {"missing": [], "type_errors": [], "duplicates": 0}

        for col, config in schema.items():
            if col not in df.columns:
                issues["missing"].append(col)
                continue

            try:
                df[col] = df[col].astype(config["type"])
            except (ValueError, TypeError):
                issues["type_errors"].append(col)

            if "default" in config:
                df[col] = df[col].fillna(config["default"])

        before = len(df)
        df = df.drop_duplicates(subset=schema.get("unique_keys", df.columns.tolist()))
        issues["duplicates"] = before - len(df)

        return df, issues
```

## dbt Transformation

```sql
-- models/staging/stg_orders.sql
{{ config(
    materialized='incremental',
    unique_key='order_id',
    on_schema_change='append_new_columns'
) }}

WITH source AS (
    SELECT * FROM {{ source('raw', 'orders') }}
    {% if is_incremental() %}
    WHERE updated_at > (SELECT MAX(updated_at) FROM {{ this }})
    {% endif %}
),

cleaned AS (
    SELECT
        order_id,
        customer_id,
        TRIM(LOWER(status)) AS status,
        CAST(total_amount AS NUMERIC) AS total_amount_usd,
        CAST(created_at AS TIMESTAMP) AS created_at,
        CAST(updated_at AS TIMESTAMP) AS updated_at
    FROM source
    WHERE order_id IS NOT NULL
      AND total_amount > 0
),

deduped AS (
    SELECT *
    FROM cleaned
    QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC) = 1
)

SELECT * FROM deduped
```

## Error Handling and Retry

```python
import time
from functools import wraps

def with_retry(max_attempts: int = 3, backoff_factor: float = 2.0):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except (ConnectionError, TimeoutError) as e:
                    last_error = e
                    wait = backoff_factor ** attempt
                    print(f"Attempt {attempt+1} failed: {e}. Retrying in {wait}s...")
                    time.sleep(wait)
                except Exception as e:
                    raise e  # Non-retryable — fail immediately
            raise last_error
        return wrapper
    return decorator
```

## Monitoring

```python
class PipelineMonitor:
    def __init__(self, pipeline_name: str):
        self.pipeline_name = pipeline_name
        self.start_time = datetime.now()
        self.metrics = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = (datetime.now() - self.start_time).seconds
        success = exc_type is None
        self.log_run(success=success, duration_seconds=duration,
                     error=str(exc_val) if exc_val else None, metrics=self.metrics)
        if not success:
            alert_on_failure(pipeline=self.pipeline_name, error=str(exc_val))

# Usage:
with PipelineMonitor("orders_etl") as monitor:
    df = extract_orders()
    monitor.metrics["rows_extracted"] = len(df)
    df = transform_orders(df)
    load_to_warehouse(df)
    monitor.metrics["rows_loaded"] = len(df)
```

## Pipeline Checklist

- [ ] Idempotent: running twice does not duplicate data
- [ ] Incremental: only processes new/changed records
- [ ] Retry logic on transient failures
- [ ] Data quality checks at source and destination
- [ ] Schema evolution handled (new columns do not break pipeline)
- [ ] Monitoring and alerting on failures
- [ ] Lineage tracking (what data came from where)
- [ ] Rollback capability for bad data loads
- [ ] Documented SLAs (when pipeline must complete)
